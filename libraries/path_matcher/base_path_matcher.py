import os.path
import re
from abc import ABCMeta, abstractmethod
from core.constants import BOOST_VERSION_REGEX
from core.models import RenderedContent
from libraries.models import PathType, LibraryVersion
from versions.models import Version
import structlog

logger = structlog.get_logger(__name__)


class BasePathMatcher(metaclass=ABCMeta):
    @property
    @abstractmethod
    def path_type(self) -> PathType:
        raise NotImplementedError

    @property
    @abstractmethod
    def determination_re(self):
        raise NotImplementedError

    def __init__(self, latest_library: LibraryVersion):
        breakpoint()
        self.latest_library_version = latest_library
        self.next: BasePathMatcher | None = None

    def set_next(self, next_matcher: "BasePathMatcher"):
        self.next = next_matcher

    # @abstractmethod
    # def determine_match(self, path: str) -> bool:
    #     """
    #     This method matches the path and handles or passes off to next if not a handler
    #     """
    #     raise NotImplementedError

    @abstractmethod
    def generate_latest_s3_path(
        self, path: str, library_name: str, content_path: str
    ) -> str:
        """
        Generates a string to match the s3/cache_key path
        returns something similar to:
            static_content_1_84_0/libs/algorithm/doc/html/index.html
            static_content_1_84_0/doc/html/accumulators.html


        """
        # static_content_subst_re = re.compile(
        #     rf"static_content_\2/libs/\g<library_name>/\g<content_path>"
        # )
        raise NotImplementedError

    def determine_match(self, path: str) -> PathType | None:
        if (details := self.get_group_items(path)) is not None:
            if self.confirm_path_exists(path, *details):
                return self.path_type
        if self.next:
            self.next.determine_match(path)
        else:
            raise ValueError(f"No redirect path match for {path=}")

    def get_group_items(self, path: str) -> tuple[str, str] | None:
        """
        returns tuple (library_name, content_path)
        """
        if src_match := self.determination_re.match(path):
            group_values = src_match.groupdict()
            library_name = group_values.get("library_name")
            content_path = group_values.get("content_path")
            # todo: do we need this all check? do we sometimes get a match where these
            #  aren't set
            if all([library_name, content_path]):
                return library_name, content_path
        return None

    def confirm_path_exists(
        self, path: str, library_name: str, content_path: str
    ) -> bool:
        s3_path = self.generate_latest_s3_path(path, library_name, content_path)
        if self.confirm_db_path_exists(s3_path) or self.confirm_s3_path_exists(s3_path):
            return True
        return False

    def confirm_s3_path_exists(self, path: str) -> bool:
        logger.debug(f"{path=}")
        return False

    def confirm_db_path_exists(self, path: str) -> bool:
        logger.debug(f"{path=}")
        if is_path := RenderedContent.objects.filter(cache_key=path).exists():
            logger.debug(f"{is_path=}")
            return True
        return True


class LibsPathMatcher(BasePathMatcher):
    determination_re = re.compile(
        rf"{BOOST_VERSION_REGEX}/libs/(?P<library_name>[\w]+)/(?P<content_path>\S+)"
    )
    path_type = PathType.LIB_IN_PATH

    def generate_latest_s3_path(self, path, library_name: str, content_path: str):
        latest_str = self.latest_library_version.version.stripped_boost_url_slug
        return os.path.sep.join(
            [f"static_content_{latest_str}", "libs", library_name, content_path]
        )


if __name__ == "__main__":
    test_path = "1_84_0/libs/algorithm/doc/html/index.html"
    matcher = LibsPathMatcher(Version.objects.most_recent())
    matcher.determine_match(test_path)
