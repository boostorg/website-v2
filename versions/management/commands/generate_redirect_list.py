import djclick as click
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Union
from versions.utils.common import load_json_dict

DEFAULT_REDIRECT_FORMAT = "BoostRedirectFormat"
REDIRECT_REGEX = r"location [=~] \^?(.+?)\$? \{ return 301 (.+?); \}"


class RedirectFormat:
    """Base class for handling redirect URL formatting."""

    def extract_source_pattern(self, source_url: str) -> str:
        """Extract the path pattern from source URL for grouping."""
        raise NotImplementedError

    def normalize_destination(self, destination: str) -> str:
        """Normalize destination for grouping purposes."""
        raise NotImplementedError

    def create_regex_source(self, source_url: str) -> str:
        """Convert source URL to regex pattern with version capture group."""
        raise NotImplementedError

    def create_regex_destination(self, destination: str) -> str:
        """Convert destination to use regex backreference."""
        raise NotImplementedError

    def can_merge_destinations(self, destinations: List[str]) -> bool:
        """Check if destinations can be merged."""
        raise NotImplementedError


class BoostRedirectFormat(RedirectFormat):
    """Handles Boost-specific redirect URL formatting."""

    def extract_source_pattern(self, source_url: str) -> str:
        """Extract path after version: /doc/libs/VERSION/path -> path"""
        match = re.search(r"/doc/libs/[^/]+/(.+?)(?:\$|$)", source_url)
        return match.group(1) if match else source_url

    def normalize_destination(self, destination: str) -> str:
        """Normalize destination by replacing version-specific parts."""
        return re.sub(r"boost-[\d\.]+", "boost-VERSION", destination)

    def create_regex_source(self, source_url: str) -> str:
        """Convert /doc/libs/VERSION/path to /doc/libs/([^/]+)/path"""
        return re.sub(r"/doc/libs/[^/]+/", "/doc/libs/([^/]+)/", source_url)

    def create_regex_destination(self, destination: str) -> str:
        """Convert boost-1.79.0 to boost-$1 in destination."""
        return re.sub(r"boost-[\d\.]+", "boost-$1", destination)

    def can_merge_destinations(self, destinations: List[str]) -> bool:
        """Check if destinations can be merged (only differ by version)."""
        if len(destinations) <= 1:
            return True

        # Normalize destinations by replacing versions
        normalized = [self.normalize_destination(dest) for dest in destinations]

        # All normalized destinations should be the same
        return len(set(normalized)) == 1


@dataclass
class ParsedRedirect:
    """Parsed redirect with extracted components."""

    original: str
    source_url: str
    destination: str
    formatter_type: str
    formatter: RedirectFormat
    path_pattern: str
    normalized_dest: str


def parse_redirects(
    redirects: List[str], known_redirect_map: Dict[str, Dict[str, str]]
) -> List[ParsedRedirect]:
    """Parse redirects once and extract all needed data."""
    parsed = []

    for redirect in redirects:
        source_match = re.search(REDIRECT_REGEX, redirect)
        if not source_match:
            continue

        source_url, destination = source_match.groups()

        # Get formatter type and instance
        formatter_type = known_redirect_map.get(source_url, {}).get(
            "redirect_format", DEFAULT_REDIRECT_FORMAT
        )
        formatter = get_formatter(formatter_type)

        # Extract pattern data
        path_pattern = formatter.extract_source_pattern(source_url)
        normalized_dest = formatter.normalize_destination(destination)

        parsed.append(
            ParsedRedirect(
                original=redirect,
                source_url=source_url,
                destination=destination,
                formatter_type=formatter_type,
                formatter=formatter,
                path_pattern=path_pattern,
                normalized_dest=normalized_dest,
            )
        )

    return parsed


def group_parsed_redirects(
    parsed_redirects: List[ParsedRedirect],
) -> Dict[str, Dict[str, List[ParsedRedirect]]]:
    """Group parsed redirects by formatter type and then by pattern."""
    groups = {}

    for parsed in parsed_redirects:
        if parsed.formatter_type not in groups:
            groups[parsed.formatter_type] = {}

        group_key = f"{parsed.path_pattern}::{parsed.normalized_dest}"
        if group_key not in groups[parsed.formatter_type]:
            groups[parsed.formatter_type][group_key] = []

        groups[parsed.formatter_type][group_key].append(parsed)

    return groups


def merge_redirect_group(group: List[ParsedRedirect]) -> List[str]:
    """Merge a group of parsed redirects or keep them separate."""
    if len(group) == 1:
        return [group[0].original]

    destinations = [parsed.destination for parsed in group]
    formatter = group[0].formatter

    if not formatter.can_merge_destinations(destinations):
        return [parsed.original for parsed in group]

    first = group[0]
    regex_source = formatter.create_regex_source(first.source_url)
    regex_destination = formatter.create_regex_destination(first.destination)
    merged = f"location ~ ^{regex_source}$ {{ return 301 {regex_destination}; }}"
    return [merged]


def merge_version_patterns_optimized(
    redirects: List[str], known_redirect_map: Dict[str, Dict[str, str]]
) -> List[str]:
    """Optimized merge that parses redirects once and processes by formatter type."""
    parsed_redirects = parse_redirects(redirects, known_redirect_map)
    groups = group_parsed_redirects(parsed_redirects)
    merged = []
    for formatter_type, pattern_groups in groups.items():
        for group_key, group in pattern_groups.items():
            merged.extend(merge_redirect_group(group))

    return merged


def create_default_redirect_config() -> Dict[str, str]:
    """Create default redirect configuration object."""
    return {"destination": "", "redirect_format": DEFAULT_REDIRECT_FORMAT}


def get_formatter(format_type: str) -> RedirectFormat:
    """Get formatter instance based on format type."""
    if format_type == "BoostRedirectFormat":
        return BoostRedirectFormat()
    else:
        # Default to BoostRedirectFormat for unknown types
        return BoostRedirectFormat()


def should_create_redirect(path_info: Dict[str, Union[str, bool]]) -> bool:
    """Determine if a path should have a redirect created."""
    return path_info.get("is_directory", True) and not path_info.get("has_index", False)


def create_source_url(version: str, path: str) -> str:
    """Create source URL from version and path."""
    version_path = version.replace("boost-", "").replace("-", "_")
    return f"/doc/libs/{version_path}/{path}"


def create_redirect_line(source_url: str, destination: str) -> str:
    """Create nginx redirect line with exact location match."""
    return f"location = {source_url} {{ return 301 {destination}; }}"


def create_redirects_and_update_map(
    verified_data: List[Dict], known_redirect_map: Dict[str, Dict[str, str]]
) -> Tuple[List[str], Dict[str, Dict[str, str]]]:
    """Generate redirect lines from verified data and update redirect map."""
    redirects = []
    updated_redirect_map = known_redirect_map.copy()

    for version_data in verified_data:
        version = version_data.get("version", "unknown")
        paths = version_data.get("paths", {})

        for path, path_info in paths.items():
            if not should_create_redirect(path_info):
                continue
            source_url = create_source_url(version, path)
            destination = known_redirect_map.get(source_url, {}).get("destination", "")
            # Update redirect map data if not already present
            if source_url not in updated_redirect_map:
                updated_redirect_map[source_url] = create_default_redirect_config()

            redirect_line = create_redirect_line(source_url, destination)
            redirects.append(redirect_line)

    return redirects, updated_redirect_map


def save_updated_redirects(
    known_redirects_file: str, updated_redirect_map: Dict[str, Dict[str, str]]
) -> None:
    """Save updated redirect map to file if changes were made."""
    try:
        with open(known_redirects_file, "w") as f:
            json.dump(dict(sorted(updated_redirect_map.items())), f, indent=2)
    except Exception as e:
        click.echo(
            f"Warning: Could not update known redirects file {known_redirects_file}: {e}",
            err=True,
        )


def output_nginx_configuration(merged_redirects: List[str], output_file: str) -> None:
    """Output the nginx configuration."""
    with open(output_file, "w") as f:
        for redirect in sorted(merged_redirects):
            f.write(redirect + "\n")
    click.echo(f"Nginx configuration written to {output_file}")


@click.command()
@click.option(
    "--input-dir",
    required=True,
    help="Directory containing individual version verified paths JSON files",
)
@click.option(
    "--known-redirects",
    required=True,
    help="JSON file containing known redirect destinations",
)
@click.option(
    "--output-file", required=True, help="Output file for nginx redirect configuration"
)
def command(input_dir: str, known_redirects: str, output_file: str):
    """Generate nginx redirect configuration from verified paths data.

    Extracts paths that need redirects (directories without index files or non-existent files)
    and outputs them as nginx rewrite directives.

    Examples:
        python manage.py generate_redirect_list --input-dir=nginx_redirects_data --known-redirects=known_redirects.json --output-file=nginx_redirects.conf
    """
    verified_data = []
    input_path = Path(input_dir)

    if not input_path.exists():
        click.echo(f"Error: Input directory '{input_dir}' does not exist")
        return

    for json_path in input_path.glob("*_paths.json"):
        try:
            with open(json_path) as f:
                data = json.load(f)
                verified_data.extend(data if isinstance(data, list) else [data])
        except Exception as e:
            click.echo(f"Error loading {json_path}: {e}")
            continue

    if not verified_data:
        click.echo("No verified paths data found")
        return

    known_redirect_map = load_json_dict(known_redirects)
    redirects, updated_redirect_map = create_redirects_and_update_map(
        verified_data, known_redirect_map
    )

    if updated_redirect_map != known_redirect_map:
        save_updated_redirects(known_redirects, updated_redirect_map)

    merged_redirects = merge_version_patterns_optimized(redirects, known_redirect_map)
    output_nginx_configuration(merged_redirects, output_file)
