import djclick as click
import json
from pathlib import Path
from typing import List, Dict, Any
from versions.utils.common import load_json_list, get_version_directory_from_tarball


def find_doc_files(directory: Path) -> List[str]:
    """Find all HTML and HTM files in the directory recursively."""
    files = []
    # Use glob pattern to match both .html and .htm files
    for file_path in directory.rglob("*.htm*"):
        relative_path = file_path.relative_to(directory)
        files.append(str(relative_path))
    return sorted(files)


def process_version_directory(
    version_dir: Path, version_info: Dict[str, Any]
) -> Dict[str, Any]:
    """Process a single version directory to find documentation files."""
    result = {
        "version": version_info["version"],
        "slug": version_info["slug"],
        "tarball_filename": version_info["tarball_filename"],
        "directory_exists": version_dir.exists(),
        "doc_files": [],
        "total_files": 0,
    }

    if version_dir.exists():
        result["doc_files"] = find_doc_files(version_dir)
        result["total_files"] = len(result["doc_files"])

    return result


@click.command()
@click.option(
    "--json-file", required=True, help="JSON file containing version information"
)
@click.option(
    "--base-dir",
    default="tarballs",
    help="Base directory containing extracted tarballs",
)
def command(json_file: str, base_dir: str):
    """Determine documentation files for versions by scanning extracted tarballs.

    Takes a JSON file with version information and scans the corresponding
    extracted directories to find HTML/HTM documentation files.

    Examples:
        python manage.py determine_version_docs_files --json-file=nginx_redirects_workspace/stage_1_tarballs.json
        python manage.py determine_version_docs_files --json-file=nginx_redirects_workspace/stage_1_tarballs.json --base-dir=tarballs
    """
    versions_data = load_json_list(json_file)
    if not versions_data:
        return

    if not Path(base_dir).exists():
        click.echo(f"Warning: Base directory '{base_dir}' does not exist")

    results = []
    for version_info in versions_data:
        version_dir = get_version_directory_from_tarball(version_info, base_dir)
        result = process_version_directory(version_dir, version_info)
        results.append(result)

    click.echo(json.dumps(results, indent=2))
