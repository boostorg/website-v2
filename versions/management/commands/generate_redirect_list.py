import djclick as click
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Union, Optional
from versions.utils.common import (
    load_json_dict,
    load_json_list,
    version_sort_key,
    version_to_slug,
)

LOCATION_PATTERN = r"location [=~] \^?(.+?)\$? \{"  # Nginx location pattern for parsing


@dataclass
class RedirectData:
    """Represents a single redirect entry."""

    path: str
    source_url: str
    destination: str

    def extract_source_pattern(self) -> str:
        """Extract path after version: /doc/libs/VERSION/path -> path"""
        match = re.search(r"/doc/libs/[^/]+/(.+?)(?:\$|$)", self.source_url)
        return match.group(1) if match else self.source_url

    def get_version(self) -> Optional[str]:
        """Extract version from source URL."""
        match = re.search(r"/doc/libs/([^/]+)/", self.source_url)
        return match.group(1) if match else None

    def create_regex_source(self) -> str:
        """Convert /doc/libs/VERSION/path to /doc/libs/([^/]+)/path"""
        return re.sub(r"/doc/libs/[^/]+/", "/doc/libs/([^/]+)/", self.source_url)

    def create_regex_destination(self) -> str:
        """Convert boost-1.79.0 to boost-$1 in destination."""
        return re.sub(r"boost-[\d\.]+", "boost-$1", self.destination)

    def normalize_destination(self) -> str:
        """Normalize destination by replacing version-specific parts."""
        return re.sub(r"boost-[\d\.]+", "boost-VERSION", self.destination)


def destinations_differ_only_by_version(destinations: List[str]) -> bool:
    """Check if destinations can be merged (only differ by version)."""
    if len(destinations) <= 1:
        return True
    # Normalize destinations by replacing versions
    normalized = [
        re.sub(r"boost-[\d\.]+", "boost-VERSION", dest) for dest in destinations
    ]
    # All normalized destinations should be the same
    return len(set(normalized)) == 1


def create_path_alternation(suffixes: List[str]) -> str:
    """Create regex alternation pattern from suffixes."""
    return "(" + "|".join(sorted(set(suffixes))) + ")"


def create_version_alternation(versions: List[str]) -> str:
    """Create version pattern using alternation."""
    # versions are in slug format (e.g., "1_79_0")
    # Convert back to dot format for nginx patterns (e.g., "1.79.0")
    dot_versions = [v.replace("_", ".") for v in versions]
    return "(" + "|".join(sorted(dot_versions)) + ")"


def is_broken_through_latest_version(
    versions_with_path: List[str], all_versions: List[str]
) -> bool:
    """Check if path is broken through the latest version."""
    return versions_with_path and max(all_versions, key=version_sort_key) == max(
        versions_with_path, key=version_sort_key
    )


def determine_redirect_strategy(
    verified_data: List[Dict], exclude_set: set = None
) -> Dict[str, str]:
    """Determine version-specific vs consolidated redirect strategy for each path."""
    all_versions = [v.get("version", "") for v in verified_data]
    path_versions = defaultdict(list)

    # group paths by pattern and determine strategy in one pass
    for version_data in verified_data:
        version = version_data.get("version", "")
        for path, path_info in version_data.get("paths", {}).items():
            if should_create_redirect(path_info):
                source_url = create_source_url(version, path)
                if not (exclude_set and source_url in exclude_set):
                    path_versions[path].append(version)

    # determine strategy for each path
    return {
        path: (
            "consolidated"
            if any(
                [
                    not versions_with_path,
                    len(versions_with_path) == len(all_versions),
                    is_broken_through_latest_version(versions_with_path, all_versions),
                ]
            )
            else "version_specific"
        )
        for path, versions_with_path in path_versions.items()
    }


def group_redirects_for_backreference_consolidation(
    redirect_data: List[RedirectData],
) -> Dict[str, List[Tuple[str, str, RedirectData]]]:
    """Find redirects that share common base paths so we have efficient patterns.

    For example, these separate redirects:
      /doc/libs/1.79.0/libs/filesystem/v2/example
      /doc/libs/1.79.0/libs/filesystem/v2/src
      /doc/libs/1.80.0/libs/filesystem/v2/example
      /doc/libs/1.80.0/libs/filesystem/v2/src

    Can be grouped by base path 'libs/filesystem/v2' and consolidated into:
      /doc/libs/([^/]+)/libs/filesystem/v2/(example|src)
    """
    base_path_groups = defaultdict(list)

    for redirect in redirect_data:
        path_pattern = redirect.extract_source_pattern()

        path_parts = path_pattern.split("/")
        if len(path_parts) >= 2:
            base_path = "/".join(path_parts[:-1])
            suffix = path_parts[-1]

            version = redirect.get_version()
            if version:
                base_path_groups[base_path].append((suffix, version, redirect))

    return base_path_groups


def can_safely_create_backreference_pattern(
    entries: List[Tuple[str, str, RedirectData]]
) -> bool:
    """Check if entries can be consolidated into a backreference pattern."""
    suffixes = {entry[0] for entry in entries}
    if len(suffixes) < 2:
        return False

    # Check if destinations follow suffix pattern
    for suffix, version, redirect in entries:
        if suffix not in redirect.destination:
            return False

    # check if all version/suffix combinations exist, only create backreference if every
    # version has every suffix
    versions = {entry[1] for entry in entries}
    version_suffix_combinations = {(entry[1], entry[0]) for entry in entries}

    # calculate expected combinations: every version should have every suffix
    expected_combinations = {
        (version, suffix) for version in versions for suffix in suffixes
    }

    # only allow backreference if all combinations exist
    return version_suffix_combinations == expected_combinations


def build_backreference_nginx_location(
    entries: List[Tuple[str, str, RedirectData]], base_path: str, strategy: str
) -> str:
    """Build nginx location block with backreference pattern from grouped entries."""
    suffixes = sorted({entry[0] for entry in entries})
    suffix_pattern = create_path_alternation(suffixes)

    # Create destination with $2 backreference
    sample_suffix, sample_version, sample_redirect = entries[0]
    regex_destination = sample_redirect.create_regex_destination()
    regex_destination = regex_destination.replace(sample_suffix, "$2")

    if strategy == "version_specific":
        version_groups = defaultdict(list)
        for suffix, version, redirect in entries:
            version_groups[version].append((suffix, redirect.destination))

        versions = [ver.replace("_", ".") for ver in version_groups.keys()]
        version_pattern = create_version_alternation(versions)
        return f"location ~ ^/doc/libs/{version_pattern}/{base_path}/{suffix_pattern}$ {{ return 301 {regex_destination}; }}"
    else:
        return f"location ~ ^/doc/libs/([^/]+)/{base_path}/{suffix_pattern}$ {{ return 301 {regex_destination}; }}"


def generate_backreference_nginx_locations(
    base_path_groups: Dict, path_strategy: Dict[str, str]
) -> Tuple[List[str], set]:
    """Transform grouped redirects into efficient nginx location blocks with backreferences.

    Takes groups like:
      'libs/filesystem/v2' -> [('example', '1.79.0', redirect1), ('src', '1.79.0', redirect2), ...]

    And creates nginx location blocks like:
      location ~ ^/doc/libs/([^/]+)/libs/filesystem/v2/(example|src)$ {
        return 301 https://github.com/boostorg/filesystem/tree/boost-$1/v2/$2;
      }

    $1 is the version, $2 is specific path suffix.
    Only creates these patterns when it's safe (all version/suffix combinations exist).
    """
    result = []
    processed_patterns = set()

    for base_path, entries in base_path_groups.items():
        if can_safely_create_backreference_pattern(entries):
            strategy = path_strategy.get(base_path, "consolidated")

            redirect = build_backreference_nginx_location(entries, base_path, strategy)
            result.append(redirect)

            # Mark patterns as processed
            for suffix, version, redirect_data in entries:
                processed_patterns.add(redirect_data.extract_source_pattern())

    return result, processed_patterns


def generate_standard_nginx_locations(
    redirect_data: List[RedirectData],
    processed_patterns: set,
    path_strategy: Dict[str, str],
) -> List[str]:
    """Generate nginx location blocks for patterns not using backreferences."""
    # Group remaining redirects by path pattern
    remaining_groups = defaultdict(list)
    for redirect in redirect_data:
        path_pattern = redirect.extract_source_pattern()
        if path_pattern not in processed_patterns:
            version = redirect.get_version()
            if version:
                remaining_groups[path_pattern].append((version, redirect))

    result = []
    for path_pattern, entries in remaining_groups.items():
        # Single redirect - create exact location match
        if len(entries) == 1:
            _, redirect = entries[0]
            result.append(
                create_redirect_line(redirect.source_url, redirect.destination)
            )
            continue

        # Multiple redirects - check if they can be consolidated
        destinations = [redirect.destination for _, redirect in entries]
        if not destinations_differ_only_by_version(destinations):
            # Different destinations - create individual redirects
            result.extend(
                create_redirect_line(redirect.source_url, redirect.destination)
                for _, redirect in entries
            )
            continue

        # Same destinations (differ only by version) - create consolidated pattern
        sample_redirect = entries[0][1]
        regex_source = sample_redirect.create_regex_source()
        regex_destination = sample_redirect.create_regex_destination()

        # Apply version-specific logic if needed
        strategy = path_strategy.get(path_pattern, "consolidated")
        if strategy == "version_specific":
            versions = [ver.replace("_", ".") for ver, _ in entries]
            version_pattern = create_version_alternation(versions)
            regex_source = re.sub(r"\(\[\^/\]\+\)", version_pattern, regex_source)

        result.append(
            f"location ~ ^{regex_source}$ {{ return 301 {regex_destination}; }}"
        )

    return result


def generate_consolidated_nginx_redirects(
    redirect_data: List[RedirectData],
    all_versions_data: List[Dict],
    exclude_set: set = None,
) -> List[str]:
    """Unified consolidation working directly with structured data."""
    path_strategy = determine_redirect_strategy(all_versions_data, exclude_set)

    # group redirects by base path for backreference detection
    base_path_groups = group_redirects_for_backreference_consolidation(redirect_data)
    # process backreference groups
    backreference_redirects, processed_patterns = (
        generate_backreference_nginx_locations(base_path_groups, path_strategy)
    )
    # process remaining patterns
    remaining_redirects = generate_standard_nginx_locations(
        redirect_data, processed_patterns, path_strategy
    )
    return backreference_redirects + remaining_redirects


def should_create_redirect(path_info: Dict[str, Union[str, bool]]) -> bool:
    """Determine if a path should have a redirect created."""
    return path_info.get("is_directory", True) and not path_info.get("has_index", False)


def create_source_url(version: str, path: str) -> str:
    """Create source URL from version and path."""
    return f"/doc/libs/{version_to_slug(version)}/{path}"


def create_redirect_line(source_url: str, destination: str) -> str:
    """Create nginx redirect line with exact location match."""
    return f"location = {source_url} {{ return 301 {destination}; }}"


def create_redirects_and_update_map(
    verified_data: List[Dict],
    known_redirect_map: Dict[str, str],
    exclude_set: set = None,
) -> Tuple[List[RedirectData], Dict[str, str]]:
    """Generate redirect data from verified data and update known_redirects map.

    Returns list of RedirectData objects.
    """
    redirect_data = []
    updated_redirect_map = known_redirect_map.copy()

    for version_data in verified_data:
        version = version_data.get("version", "unknown")
        paths = version_data.get("paths", {})

        for path, path_info in paths.items():
            if not should_create_redirect(path_info):
                continue
            source_url = create_source_url(version, path)
            if exclude_set and source_url in exclude_set:
                continue

            destination = known_redirect_map.get(source_url, "")

            if destination:  # Only include if we have a destination
                redirect_data.append(RedirectData(path, source_url, destination))
                # Add to updated map only when we have a destination
                updated_redirect_map[source_url] = destination

    return redirect_data, updated_redirect_map


def save_updated_redirects(
    known_redirects_file: str, updated_redirect_map: Dict[str, str]
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
@click.option(
    "--exclude-list",
    help="JSON file containing list of source URLs to exclude from redirects",
)
def command(input_dir: str, known_redirects: str, output_file: str, exclude_list: str):
    """Generate nginx redirect configuration from verified paths data.

    Extracts paths that need redirects (directories without index files or non-existent files)
    and outputs them as nginx rewrite directives.

    Examples:
        python manage.py generate_redirect_list --input-dir=nginx_redirects_data --known-redirects=known_redirects.json --output-file=nginx_redirects.conf
        python manage.py generate_redirect_list --input-dir=nginx_redirects_data --known-redirects=known_redirects.json --exclude-list=exclude.json --output-file=nginx_redirects.conf
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

    # Load exclude list if provided
    exclude_set = set()
    if exclude_list:
        exclude_data = load_json_list(exclude_list)
        exclude_set = set(exclude_data)
        click.echo(f"Loaded {len(exclude_set)} URLs to exclude")

    redirects, updated_redirect_map = create_redirects_and_update_map(
        verified_data, known_redirect_map, exclude_set
    )

    if updated_redirect_map != known_redirect_map:
        save_updated_redirects(known_redirects, updated_redirect_map)

    merged_redirects = generate_consolidated_nginx_redirects(
        redirects, verified_data, exclude_set
    )
    output_nginx_configuration(merged_redirects, output_file)
