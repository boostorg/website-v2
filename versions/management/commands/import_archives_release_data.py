import djclick as click

import requests

from django.conf import settings

from versions.models import Version
from versions.releases import (
    get_archives_download_data,
    get_archives_download_uris_for_release,
    store_release_downloads_for_version,
    get_binaries_download_data,
    get_binary_checksums,
    get_binary_download_uris_for_release,
)


@click.command()
@click.option("--release", is_flag=False, help="Release name")
def command(release):
    """
    Import release data from the Boost artifactory.

    This command will import the release data from the Boost artifactory for the
    specified release. If no release is specified, it will import the release data
    for all releases included in Artifactory.
    """
    last_release = settings.MIN_ARCHIVES_RELEASE

    if release:
        versions = Version.objects.filter(name__icontains=release)
    else:
        versions = Version.objects.filter(name__gte=last_release)

    for v in versions:
        version_num = v.name.replace("boost-", "")
        try:
            archives_urls = get_archives_download_uris_for_release(version_num)
            binaries_urls = get_binary_download_uris_for_release(version_num)
            file_urls = archives_urls + binaries_urls
        except requests.exceptions.HTTPError:
            print(f"Skipping {version_num}, error retrieving release data")
            continue

        download_data = []
        checksums = dict()
        for url in file_urls:
            try:
                if "/binaries/" in url:
                    if not checksums:
                        checksums = get_binary_checksums(url)
                    data = get_binaries_download_data(url, checksums)
                else:
                    data = get_archives_download_data(url)
                download_data.append(data)
            except (requests.exceptions.HTTPError, ValueError):
                print(f"Skipping {url}; error retrieving download data")
                continue

            store_release_downloads_for_version(v, download_data)
            print(f"Stored download data for {v.name}")
