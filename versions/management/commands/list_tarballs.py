import djclick as click
import json
from packaging.version import parse as parse_version

from versions.models import Version


def parse_version_range(version_range):
    """Parse version range string into start and end versions.

    Formats supported:
    - "1.81.0" - single version
    - "1.79.0-1.81.0" - range from 1.79.0 to 1.81.0
    - "1.79.0+" - from 1.79.0 onwards
    """
    if not version_range:
        return None, None

    if "+" in version_range:
        start_version = version_range.replace("+", "").strip()
        return start_version, None
    elif "-" in version_range and not version_range.startswith("boost-"):
        parts = version_range.split("-", 1)
        if len(parts) == 2 and "." in parts[0] and "." in parts[1]:
            return parts[0].strip(), parts[1].strip()

    return version_range.strip(), version_range.strip()


def filter_versions_by_range(queryset, version_filter: str):
    """Filter queryset by version range."""
    if not version_filter:
        return queryset

    start_version, end_version = parse_version_range(version_filter)

    if not start_version:
        return queryset

    matching_versions = []
    for v in queryset:
        if v.cleaned_version_parts_int:
            try:
                v_version = ".".join(map(str, v.cleaned_version_parts_int[:3]))
                if parse_version(v_version) >= parse_version(start_version):
                    if end_version is None or parse_version(v_version) <= parse_version(
                        end_version
                    ):
                        matching_versions.append(v.id)
            except (ValueError, TypeError):
                # Skip versions that can't be parsed
                continue

    return queryset.filter(id__in=matching_versions)


def generate_tarball_filename(version_obj) -> str:
    """Generate tarball filename from version object."""
    # boost-1-73-0 -> 1.73.0/source/boost_1_73_0.tar.bz2
    short_version = version_obj.slug.replace("boost-", "").replace("-", ".")
    tarball_filename = (
        short_version + "/source/" + version_obj.slug.replace("-", "_") + ".tar.bz2"
    )
    return tarball_filename


def extract_tarball_data(versions_list: list) -> list:
    """Extract tarball data from sorted versions list."""
    return [
        {
            "version": version_obj.name,
            "slug": version_obj.slug,
            "tarball_filename": generate_tarball_filename(version_obj),
            "version_parts": version_obj.cleaned_version_parts_int,
        }
        for version_obj in versions_list
    ]


@click.command()
@click.option(
    "--version-filter",
    help="Single version (e.g., '1.81.0') or range (e.g., '1.79.0-1.81.0', '1.79.0+')",
)
def command(version_filter: str):
    """Extract tarball URLs from active versions.

    Queries active versions in the database and generates tarball URLs by converting
    slug values (replacing - with _ and appending .tar.bz2).
    Returns JSON with version information and tarball filenames.

    Examples:
      python manage.py list_tarballs --version-filter=1.81.0
      python manage.py list_tarballs --version-filter=1.79.0-1.81.0
      python manage.py list_tarballs --version-filter=1.79.0+
    """
    queryset = (
        Version.objects.minor_versions()
        .filter(slug__isnull=False, active=True)
        .exclude(slug="")
        .exclude(name__in=["master", "develop"])
        .order_by("-version_array", "-name")
    )
    queryset = filter_versions_by_range(queryset, version_filter)
    urls = extract_tarball_data(queryset)
    click.echo(json.dumps(urls, indent=2))
