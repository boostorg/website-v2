import djclick as click

import requests

from django.conf import settings

from versions.models import Version
from versions.releases import (
    get_artifactory_download_data,
    get_artifactory_downloads_for_release,
    store_release_downloads_for_version,
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
    last_release = settings.MIN_ARTIFACTORY_RELEASE

    if release:
        versions = Version.objects.filter(name__icontains=release)
    else:
        versions = Version.objects.filter(name__gte=last_release)

    for v in versions:
        version_num = v.name.replace("boost-", "")
        try:
            artifactory_data = get_artifactory_downloads_for_release(version_num)
        except requests.exceptions.HTTPError:
            print(f"Skipping {version_num}, error retrieving release data")
            continue

        download_data = []
        for d in artifactory_data:
            try:
                data = get_artifactory_download_data(d)
                download_data.append(data)
            except requests.exceptions.HTTPError:
                print(f"Skipping {d}, error retrieving download data")
                continue

            store_release_downloads_for_version(v, download_data)
            print(f"Stored download data for {v.name}")
