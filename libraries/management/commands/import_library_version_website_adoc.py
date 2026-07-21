import djclick as click

from django.conf import settings

from libraries.tasks import store_library_version_website_adoc
from versions.models import Version


@click.command()
@click.option(
    "--release",
    help="Boost version number (example: 1.81.0). A partial value processes all "
    "matching versions (example: '--release=1.7' processes 1.70.0, 1.71.0, ...).",
)
@click.option(
    "--new",
    default=True,
    type=click.BOOL,
    help="True (default): process the most recent version only. False: process all "
    "versions >= --min-version. Overridden by --release.",
)
@click.option(
    "--min-version",
    default=settings.MINIMUM_BOOST_VERSION,
    help="Minimum Boost version to process (default: settings.MINIMUM_BOOST_VERSION).",
)
def command(release: str, new: bool, min_version: str):
    """Fetch, parse, and store each library's meta/website.adoc for the targeted
    Boost versions.

    The most recent version is fetched from `develop` (freshest maintainer content,
    matching the daily task); older versions are fetched from their release tag (the
    frozen snapshot, matching release import). A repo without the file is left
    untouched.
    """
    # Order/compare on the numeric version_array so boost-1.100.0 > boost-1.71.0
    # (plain name ordering is lexicographic and breaks once minor/patch hits 100).
    min_version_parts = [int(part) for part in min_version.split(".")]
    version_qs = (
        Version.objects.with_partials()
        .active()
        .with_version_split()
        .filter(version_array__gte=min_version_parts)
    )
    most_recent = (
        version_qs.filter(beta=False, full_release=True)
        .order_by("-version_array")
        .first()
    )

    if release:
        versions = list(
            version_qs.filter(name__icontains=release).order_by("-version_array")
        )
    elif new:
        versions = [most_recent] if most_recent else []
    else:
        versions = list(version_qs.order_by("-version_array"))

    for version in versions:
        ref = "develop" if version == most_recent else version.name
        click.secho(f"Processing {version.name} (ref={ref})...", fg="green")
        store_library_version_website_adoc(version, ref=ref)

    click.secho("Finished importing website.adoc content.", fg="green")
