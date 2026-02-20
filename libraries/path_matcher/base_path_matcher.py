import re
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass

from botocore.client import BaseClient
from botocore.exceptions import ClientError
from django.conf import settings

from versions.models import Version
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PathSegments:
    library_name: str
    content_path: str


@dataclass
class PathMatchResult:
    is_direct_equivalent: bool
    latest_path: str
    matcher: str


class BasePathMatcher(metaclass=ABCMeta):
    """
    Extended class names should follow the format of "(FromDescription)To(ToDescription)(Exact|Index)Matcher".

    * ...Direct - should be used when we're going to return a direct matching file in the latest library docs
    * ...Fallback - should be used when we're going return an index.htm(l) file in the latest library docs or otherwise
        don't mind there being no exact match on the db/s3

    Operation:
        1. we check to see if the provided path matches the Extended class's path_re regex.
        2. if no regex match we move to the next matcher in the chain
        3. if regex matches we check the DB to see if a matching path is found and fallback to a checking S3 to see if
         it just hasn't been cached.
        4. if no match on db or s3 and the matcher is flagged as is_index_fallback=True we return that as a match
        5. otherwise we then move on to the next matcher in the chain

    class properties:
        has_equivalent: default false, set to true if this class provides a direct equivalent path and no path translation
            is needed
        is_index_fallback: default false, set to true if this matcher accepts that the path may not actually exist.
        path_re: returns a compiled regex() as documented on the property
    """

    has_equivalent: bool = False
    is_index_fallback: bool = False

    @property
    @abstractmethod
    def path_re(self) -> re.Pattern[str]:
        """
        returns a Pattern object with group names of 'library_name', 'content_path'
        e.g. re.compile(rf"{BOOST_VERSION_REGEX}/libs/(?P<library_name>[\w]+)/(?P<content_path>\S+)")
        All groups must be filled, don't necessarily need to be used in your generate_... methods.
        """
        raise NotImplementedError

    def __init__(self, latest_version: Version, s3_client: BaseClient):
        self.latest_version: Version = latest_version
        self.s3_client: BaseClient = s3_client
        self.next: BasePathMatcher | None = None
        self.latest_slug: str = self.latest_version.stripped_boost_url_slug

    def set_next(self, next_matcher: "BasePathMatcher"):
        self.next = next_matcher

    @abstractmethod
    def generate_latest_s3_path(self, path: str, segments: PathSegments) -> str:
        """
        Generates a string to match the s3/cache_key path which will be checked for existence,
        returns something similar to:
            static_content_1_84_0/libs/algorithm/doc/html/index.html
            static_content_1_84_0/doc/html/accumulators.html
        """
        raise NotImplementedError

    @abstractmethod
    def generate_latest_url(self, path_data: PathSegments) -> str:
        """returns the actual latest url the user should be presented with"""
        raise NotImplementedError

    def determine_match(self, path: str) -> PathMatchResult:
        if (details := self.get_group_items(path)) is not None:
            if self.confirm_path_exists(path, details) or self.is_index_fallback:
                logger.debug(f"regex match on {self.get_class_name()}")
                return self.get_result(details)

        logger.debug(f"no regex match determined on {self.get_class_name()}")
        if self.next:
            return self.next.determine_match(path)
        else:
            msg = f"No redirect path match for {path=}"
            logger.warning(msg)
            raise ValueError(msg)

    def get_group_items(self, path: str) -> PathSegments | None:
        """
        returns tuple (library_name, content_path)
        """
        if src_match := self.path_re.match(path):
            group_values = src_match.groupdict()
            library_name = group_values.get("library_name")
            content_path = group_values.get("content_path")
            if all([library_name, content_path]):
                return PathSegments(library_name, content_path)
        return None

    def confirm_path_exists(self, path: str, segments: PathSegments) -> bool:
        s3_path = self.generate_latest_s3_path(path, segments)
        logger.debug(f"{s3_path=}")
        return (
            self.confirm_db_path_exists(s3_path)
            or self.confirm_s3_path_exists(s3_path)
        )  # fmt: skip

    def confirm_s3_path_exists(self, path: str) -> bool:
        # s3 stored, e.g. archives/boost_1_90_0/doc/html/accumulators.html
        archive_key = path.replace("static_content_", "archives/boost_")
        logger.debug(f"Checking S3 for {path=} ~ {archive_key=} ")
        try:
            bucket_name = settings.STATIC_CONTENT_BUCKET_NAME
            self.s3_client.head_object(Bucket=bucket_name, Key=archive_key)
            logger.debug(f"S3 key exists: {path}")
            return True
        except ClientError:
            logger.debug(f"S3 key does not exist: {path}")
            return False

    @staticmethod
    def confirm_db_path_exists(path: str) -> bool:
        from core.models import RenderedContent

        logger.debug(f"{path=}")
        if is_path := RenderedContent.objects.filter(cache_key=path).exists():
            logger.debug(f"RenderedContent match {is_path=}")
            return True
        return False

    def get_class_name(self):
        return self.__class__.__name__

    def get_result(self, path_data: PathSegments) -> PathMatchResult:
        return PathMatchResult(
            self.has_equivalent,
            self.generate_latest_url(path_data),
            self.get_class_name(),
        )

    def handle(self, test_path: str) -> PathMatchResult:
        return self.determine_match(test_path)
