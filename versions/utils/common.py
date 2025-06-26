import json
import os
from pathlib import Path
from typing import Dict, List, Any
import djclick as click


def load_json_list(json_file: str) -> List[Dict[str, Any]]:
    """Load and validate JSON file expecting a list of objects."""
    try:
        with open(json_file, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        click.echo(f"Error: JSON file '{json_file}' not found", err=True)
        return []
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON in file '{json_file}': {e}", err=True)
        return []

    if not isinstance(data, list):
        click.echo(
            "Error: JSON file should contain an array of version objects", err=True
        )
        return []

    return data


def load_json_dict(json_file: str) -> Dict[str, Any]:
    """Load and validate JSON file expecting a dictionary/object."""
    try:
        with open(json_file, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        click.echo(f"Error: JSON file '{json_file}' not found", err=True)
        return {}
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON in file '{json_file}': {e}", err=True)
        return {}

    if not isinstance(data, dict):
        click.echo("Error: JSON file should contain a dictionary/object", err=True)
        return {}

    return data


def has_index_files(directory: Path) -> bool:
    """Check if directory contains index.html or index.htm files."""
    index_files = ["index.html", "index.htm"]
    return any((directory / index_file).exists() for index_file in index_files)


def get_version_directory_from_tarball(
    version_data: Dict[str, Any], base_dir: str
) -> Path:
    """Get the directory path for a version by extracting from tarball filename."""
    tarball_file = os.path.basename(version_data.get("tarball_filename", ""))
    dir_name = os.path.splitext(os.path.splitext(tarball_file)[0])[0]  # Remove .tar.bz2
    return Path(base_dir) / dir_name


def version_sort_key(version: str) -> List[int]:
    """Extract version parts for sorting (e.g., 'boost-1.79.0' -> [1, 79, 0])."""
    return [int(x) for x in version.replace("boost-", "").replace("-", ".").split(".")]


def version_to_slug(version: str) -> str:
    """Convert version to URL slug format (e.g., 'boost-1.79.0' -> '1_79_0')."""
    return version.replace("boost-", "").replace("-", "_")
