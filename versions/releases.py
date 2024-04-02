import json
from json.decoder import JSONDecodeError

import requests
import structlog
from bs4 import BeautifulSoup
from django.conf import settings
from jsoncomment import JsonComment

from core.htmlhelper import modernize_release_notes
from core.models import RenderedContent

from .models import Version, VersionFile


logger = structlog.get_logger(__name__)
session = requests.Session()


def get_archives_download_uris_for_release(release: str = "1.81.0") -> list:
    """Get the download information for a Boost release from the Boost Archives.

    Args:
        release (str): The Boost release to get download information for. Defaults to
            "1.81.0".

    Returns:
        list: A list of URLs to download the release data from.
    """
    file_extensions = [".tar.bz2", ".tar.gz", ".7z", ".zip"]
    file_name_excludes = ["_rc"]

    if "beta" in release:
        release_path = f"{settings.ARCHIVES_URL}beta/{release}/source/"
    else:
        release_path = f"{settings.ARCHIVES_URL}release/{release}/source/"

    try:
        resp = session.get(release_path)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(
            "get_archives_releases_list_error", exc_msg=str(e), url=release_path
        )
        raise

    # Get the list of archives downloads for this release
    soup = BeautifulSoup(resp.text, "html.parser")
    uris = []
    for a in soup.find_all("a"):
        uri = a.get("href")
        # Only include the download links with valid file extensions.
        if any(uri.endswith(ext) for ext in file_extensions):
            # Exclude release candidates
            if not any(exclude in uri for exclude in file_name_excludes):
                uris.append(f"{release_path}{uri}")

    return uris


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


def get_release_notes_for_version(version_pk):
    """Retrieve the release notes for a given version.

    We retrieve the rendered release notes for older versions.
    """
    try:
        version = Version.objects.get(pk=version_pk)
    except Version.DoesNotExist:
        logger.info(
            "get_release_notes_for_version_error_version_not_found",
            version_pk=version_pk,
        )
        raise Version.DoesNotExist
    base_url = (
        "https://raw.githubusercontent.com/boostorg/website/master/users/history/"
    )
    filename = f"{version.slug.replace('boost', 'version').replace('-', '_')}.html"
    url = f"{base_url}{filename}"
    try:
        response = session.get(url)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(
            "get_release_notes_for_version_http_error",
            exc_msg=str(e),
            url=url,
            version_pk=version_pk,
        )
        raise
    return response.content


def process_release_notes(content):
    stripped_content = modernize_release_notes(content)
    return stripped_content


def store_release_notes_for_version(version_pk):
    """Retrieve and store the release notes for a given version"""
    # Get the version
    try:
        version = Version.objects.get(pk=version_pk)
    except Version.DoesNotExist:
        logger.info(
            "store_release_notes_for_version_error_version_not_found",
            version_pk=version_pk,
        )
        raise Version.DoesNotExist

    # Get the release notes content
    content = get_release_notes_for_version(version_pk)
    stripped_content = process_release_notes(content)

    # Save the result to the rendered content model with the version cache key
    rendered_content, _ = RenderedContent.objects.update_or_create(
        cache_key=version.release_notes_cache_key,
        defaults={
            "content_type": "text/html",
            "content_original": content,
            "content_html": stripped_content,
        },
    )
    logger.info(
        "store_release_notes_for_version_success",
        rendered_content_pk=rendered_content.id,
        version_pk=version_pk,
    )
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
        VersionFile.objects.update_or_create(
            version=version,
            checksum=data["checksum"],
            defaults=dict(
                url=data["url"],
                operating_system=data["operating_system"],
                display_name=data["display_name"],
            ),
        )
