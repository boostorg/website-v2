import djclick as click

import requests

from django.conf import settings
import structlog

from versions.models import Version
from versions.releases import (
    get_archives_download_data,
    get_archives_download_uris_for_release,
    store_release_downloads_for_version,
    get_binaries_download_data,
    get_binary_checksums,
    get_binary_download_uris_for_release,
)
from structlog import get_logger

logger = get_logger(__name__)

logger = structlog.get_logger()


@click.command()
@click.option("--release", is_flag=False, help="Release name")
@click.option(
    "--new",
    default=True,
    type=click.BOOL,
    help="Choose the newest version only from the db. false downloads all",
)
def command(release: str, new: bool):
    """
    Import release data from the Boost artifactory.

    This command will import the release data from the Boost artifactory for the
    specified release. If no release is specified, it will import the release data
    for the most recent release included in Artifactory. If --new is set to False,
    it will import the release data for all releases that are greater than or equal to
    the minimum release defined in settings.MIN_ARCHIVES_RELEASE.
    """
    logger.info(f"import_archive_release_data {release=} {new=}")
    last_release = settings.MIN_ARCHIVES_RELEASE

    if release:
        name = f"boost-{release}" if release not in ["master", "develop"] else release
        versions = [Version.objects.with_partials().get(name=name)]
    elif new:
        # Include both the most recent full release and the most recent beta
        # (if one exists), so that a newly-imported beta is not silently
        # skipped just because `most_recent()` filters out betas.
        qs = Version.objects.with_partials()
        versions = [
            v for v in (qs.most_recent(), qs.most_recent_beta()) if v is not None
        ]
    else:
        versions = Version.objects.with_partials().filter(name__gte=last_release)
    logger.info(f"import_archive_release_data {versions=}")

    for v in versions:
        logger.info(f"Processing release {v.name=}")
        version_num = v.name.replace("boost-", "")
        try:
            archives_urls = get_archives_download_uris_for_release(version_num)
            binaries_urls = get_binary_download_uris_for_release(version_num)
            file_urls = archives_urls + binaries_urls
        except requests.exceptions.HTTPError:
            # Promoted from INFO to WARNING: an empty/missing archives listing
            # leaves the version with zero downloads, which previously looked
            # indistinguishable from a successful import in the logs.
            logger.warning(
                f"Skipping {version_num}, error retrieving release data "
                f"(archives listing unavailable)"
            )
            continue

        stored_count = 0
        download_data = []
        checksums = dict()
        for url in file_urls:
            logger.info(f"Processing {v.name=} {url=}")
            try:
                if "/binaries/" in url:
                    if not checksums:
                        checksums = get_binary_checksums(url)
                    data = get_binaries_download_data(url, checksums)
                else:
                    data = get_archives_download_data(url)
                download_data.append(data)
            except (requests.exceptions.HTTPError, ValueError):
                logger.warning(f"Skipping {url}; error retrieving download data")
                continue
            logger.info(f"Data for {v.name=} at {url=}: {download_data=}")
            store_release_downloads_for_version(v, download_data)
            stored_count += 1
            logger.info(f"Stored download data from {url=} for {v.name}")

        # Summary log so operators can tell at a glance whether anything was
        # actually imported for this version vs. silently zero.
        if stored_count == 0:
            logger.warning(
                f"import_archive_release_data {v.name=}: no download files "
                f"stored (listing returned {len(file_urls)} candidate URLs)"
            )
        else:
            logger.info(
                f"import_archive_release_data {v.name=}: stored "
                f"{stored_count} download file(s)"
            )
