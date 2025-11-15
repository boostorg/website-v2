import json
from json.decoder import JSONDecodeError

import requests
import structlog
from bs4 import BeautifulSoup
from jsoncomment import JsonComment

from django.conf import settings

from core.asciidoc import convert_adoc_to_html
from core.boostrenderer import get_file_data, get_s3_client, does_s3_key_exist
from core.htmlhelper import modernize_release_notes
from core.models import RenderedContent

from .models import Version, VersionFile


logger = structlog.get_logger(__name__)
session = requests.Session()


def get_download_uris_for_release(
    release: str,
    subdir: str,
    file_extensions: list[str],
    file_name_excludes: list[str] = None,
) -> list[str]:
    """Get the download URIs for a Boost release from the Boost Archives."""
    file_name_excludes = file_name_excludes or []

    release_type = "beta" if "beta" in release else "release"
    release_path = f"{settings.ARCHIVES_URL}{release_type}/{release}/{subdir}/"

    try:
        resp = session.get(release_path)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(
            "get_archives_releases_list_error", exc_msg=str(e), url=release_path
        )
        raise

    soup = BeautifulSoup(resp.text, "html.parser")
    return [
        f"{release_path}{a.get('href')}"
        for a in soup.find_all("a")
        if a.get("href")
        and any(a.get("href").endswith(ext) for ext in file_extensions)
        and not any(exclude in a.get("href") for exclude in file_name_excludes)
    ]


def get_archives_download_uris_for_release(release: str = "1.81.0") -> list[str]:
    return get_download_uris_for_release(
        release=release,
        subdir="source",
        file_extensions=[".tar.bz2", ".tar.gz", ".7z", ".zip"],
        file_name_excludes=["_rc"],
    )


def get_binary_download_uris_for_release(release: str) -> list[str]:
    return get_download_uris_for_release(
        release=release,
        subdir="binaries",
        file_extensions=[".exe", ".7z"],
        file_name_excludes=["_rc"],
    )


def get_artifactory_download_uris_for_release(release: str = "1.81.0") -> list:
    """Get the download information for a Boost release from the Boost artifactory.

    Args:
        release (str): The Boost release to get download information for. Defaults to
            "1.81.0".

    Returns:
        list: A list of URLs to download the release data from.
    """
    file_extensions = [".tar.bz2", ".tar.gz", ".7z", ".zip"]

    beta = False

    if "beta" in release:
        beta = True
        release_path = f"{settings.ARTIFACTORY_URL}beta/{release}/source/"
    else:
        release_path = f"{settings.ARTIFACTORY_URL}release/{release}/source/"

    try:
        resp = session.get(release_path)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(
            "get_artifactory_releases_list_error", exc_msg=str(e), url=release_path
        )
        raise

    # Get the list of artifactory downloads for this release
    children = resp.json()["children"]
    base_uri = release_path.rstrip("/")
    uris = []
    for child in children:
        uri = child["uri"]

        # The directory may include the release candidates and beta releases; skip those
        # unless this is a beta release
        if any(
            [
                ("beta" in uri and not beta),
                ("rc" in uri),
                (uri.endswith(".json")),
            ]
        ):
            # go to next
            continue

        if any(uri.endswith(ext) for ext in file_extensions):
            uris.append(f"{base_uri}{uri}")

    return uris


def get_archives_download_data(url):
    """Get the download information for a Boost release from the Boost Archives."""

    # Append .json to the end of the URL to get the download information.
    json_url = f"{url}.json"

    try:
        resp = session.get(json_url)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error("get_archives_download_data_error", exc_msg=str(e), url=json_url)
        raise

    try:
        # Parse the JSON response, which sometimes has trailing commas.
        json_parser = JsonComment(json)
        resp_json = json_parser.loads(resp.text)

    except JSONDecodeError:
        logger.error("get_archives_download_data_error", url=json_url)
        raise ValueError(f"Invalid response from {json_url}")

    return {
        "url": url,
        "operating_system": "Unix" if ".tar" in url else "Windows",
        "checksum": resp_json["sha256"],
        "display_name": url.split("/")[-1],
    }


def get_binaries_download_data(url: str, checksums: dict) -> dict:
    filename = url.split("/")[-1]
    return {
        "url": url,
        "operating_system": "Windows (Bin)",
        "checksum": checksums[filename],
        "display_name": filename,
    }


def get_binary_checksums(url: str) -> dict:
    binaries_url = "/".join(url.split("/")[:-1])
    checksum_url = binaries_url + "/SHA256SUMS"
    try:
        resp = session.get(checksum_url)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error("get_binary_checksums", exc_msg=str(e), url=checksum_url)
        raise

    checksums = {}
    for line in resp.text.strip().splitlines():
        checksum, filename = line.split(maxsplit=1)
        checksums[filename] = checksum
    return checksums


def get_artifactory_download_data(url):
    """Get the download information for a Boost release from the Boost artifactory."""
    try:
        resp = session.get(url)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error("get_artifactory_releases_detail_error", exc_msg=str(e), url=url)
        raise

    if "downloadUri" not in resp.json() or "checksums" not in resp.json():
        logger.error("get_artifactory_releases_detail_error", url=url)
        raise ValueError(f"Invalid response from {url}")

    return {
        "url": resp.json().get("downloadUri"),
        "operating_system": "Unix" if ".tar" in url else "Windows",
        "checksum": resp.json()["checksums"]["sha256"],
        "display_name": url.split("/")[-1],
    }


def get_release_notes_for_version_s3(version_pk):
    """Retrieve the adoc release notes from S3 and return the converted html string"""
    # TODO: this and the github function have duplication (including of this comment!),
    #  and are not extensible if we encounter additional filename patterns in the
    #  future; we should refactor.
    try:
        version = Version.objects.get(pk=version_pk)
    except Version.DoesNotExist:
        logger.info(
            "get_release_notes_for_version_s3_error_version_not_found",
            version_pk=version_pk,
        )
        raise
    # get_content_from_s3 only works for keys with matching keys
    # in the STATIC_CONTENT_MAPPING. Use get_file_data directly instead.
    # Note we are using the non-beta slug since release notes for beta
    # versions are named without beta suffix.
    filename = version.non_beta_slug.replace("-", "_")
    s3_client = get_s3_client()
    bucket_name = settings.STATIC_CONTENT_BUCKET_NAME

    primary_key = f"release-notes/master/{filename}.adoc"
    fallback_key = f"release-notes/master/{filename.rsplit('_', 1)[0] + '_x'}.adoc"

    response = None
    if does_s3_key_exist(s3_client, bucket_name, primary_key):
        response = get_file_data(s3_client, bucket_name, primary_key)
    elif does_s3_key_exist(s3_client, bucket_name, fallback_key):
        response = get_file_data(s3_client, bucket_name, fallback_key)
    else:
        logger.info(f"no release notes found for {filename=}")
    return response["content"].decode() if response else ""


def get_release_notes_for_version_github(version_pk):
    """Retrieve the release notes for a given version.

    We retrieve the rendered release notes for older versions.
    """
    # TODO: this and the S3 function have duplication (including of this comment!),
    #  and are not extensible if we encounter additional filename patterns in the
    #  future; we should refactor.
    try:
        version = Version.objects.get(pk=version_pk)
    except Version.DoesNotExist:
        logger.info(
            "get_release_notes_for_version_error_version_not_found",
            version_pk=version_pk,
        )
        raise
    base_url = (
        "https://raw.githubusercontent.com/boostorg/website/master/users/history/"
    )
    # Note we are using the non-beta slug since release notes for beta
    # versions are named without beta suffix.
    base_filename = (
        f"{version.non_beta_slug.replace('boost', 'version').replace('-', '_')}"
    )
    url = f"{base_url}{base_filename}.html"
    try:
        response = session.get(url)
        if response.status_code == 404:
            # Some beta release notes end in _x.html instead of _0.html; try that.
            fallback_filename = base_filename.rsplit("_", 1)[0] + "_x"
            fallback_url = f"{base_url}{fallback_filename}.html"
            response = session.get(fallback_url)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(
            "get_release_notes_for_version_http_error",
            exc_msg=str(e),
            url=fallback_url if "fallback_url" in locals() else url,
            version_pk=version_pk,
        )
        raise
    return response.content


def get_release_notes_for_version(version_pk):
    """Get the release notes content.

    Tries S3 first, and fallback to old github release notes if not found in S3.
    """
    content = get_release_notes_for_version_s3(version_pk)
    if content:
        processed_content = convert_adoc_to_html(content)
        content_type = "text/asciidoc"
    else:
        content = get_release_notes_for_version_github(version_pk)
        processed_content = process_release_notes(content)
        content_type = "text/html"
    return content, processed_content, content_type


def get_in_progress_release_notes():
    try:
        response = session.get(settings.RELEASE_NOTES_IN_PROGRESS_URL)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(
            "get_in_progress_release_notes_error",
            exc_msg=str(e),
            url=settings.RELEASE_NOTES_IN_PROGRESS_URL,
        )
        raise
    return response.content


def process_release_notes(content):
    stripped_content = modernize_release_notes(content)
    return stripped_content


def store_release_notes_for_version(version_pk):
    """Check S3 and then github for release notes and store them in RenderedContent."""
    # Get the version
    # todo: convert to task, remove the task that calls this, is redundant
    try:
        version = Version.objects.get(pk=version_pk)
    except Version.DoesNotExist:
        logger.info(f"store_release_notes version_not_found {version_pk=}")
        raise Version.DoesNotExist

    content, processed_content, content_type = get_release_notes_for_version(version_pk)

    # Save the result to the rendered content model with the version cache key
    rendered_content, _ = RenderedContent.objects.update_or_create(
        cache_key=version.release_notes_cache_key,
        defaults={
            "content_type": content_type,
            "content_original": content,
            "content_html": processed_content,
        },
    )
    logger.info(
        f"store_release_notes_for_version_success {rendered_content.id=} {version.name=}"
    )
    return rendered_content


def store_release_notes_for_in_progress():
    """Retrieve and store the release notes for a given version"""
    # Get the release notes content
    content = get_in_progress_release_notes()
    stripped_content = process_release_notes(content)

    # Save the result to the rendered content model with the key
    rendered_content, _ = RenderedContent.objects.update_or_create(
        cache_key=settings.RELEASE_NOTES_IN_PROGRESS_CACHE_KEY,
        defaults={
            "content_type": "text/html",
            "content_original": content,
            "content_html": stripped_content,
        },
    )
    logger.info(f"store_release_notes_in_progress_success {rendered_content.id=}")
    return rendered_content


def store_release_downloads_for_version(version, release_data):
    """Store the release download information for a Version instance.

    Args:
        version (Version): The Version instance to store the download information for.
        release_data (list): A list of dictionaries containing the download information
            for the release. Each dictionary contains the following keys:
            - url (str): The URL to download the release from.
            - operating_system (str): The operating system the release is for.
            - checksum (str): The sha256 checksum for the release.
            - display_name (str): The name of the release file.
    """
    for data in release_data:
        logger.info(f"Storing download data for {version.name}: {data=}")
        VersionFile.objects.update_or_create(
            version=version,
            checksum=data["checksum"],
            defaults=dict(
                url=data["url"],
                operating_system=data["operating_system"],
                display_name=data["display_name"],
            ),
        )
