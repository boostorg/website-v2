import re
import djclick as click
import json
import requests
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from bs4 import BeautifulSoup
from versions.utils.common import load_json_list, has_index_files

FILE_FILTER_EXTENSIONS = (
    ".html",
    ".htm",
    ".js",
    ".xml",
    ".css",
    ".txt",
    ".c",
    ".mso",
    ".cpp",
    ".hpp",
    ".ipp",
    ".php",
    ".py",
    ".md",
    ".rst",
    ".pdf",
    ".qbk",
    ".docx",
    ".xlsx",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".txt",
    ".txt.gz",
    ".txt.bz2",
    ".txt.xz",
    ".txt.zst",
    ".txt.lz4.in",
    ".v2",
    ".dat",
    ".dat.gz",
    ".dat.bz2",
    ".dat.xz",
    ".dat.zst",
    ".dat.lz4",
    ".dot",
    ".ico",
    ".toyxml",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
)


def href_pass(url: str) -> bool:
    """Check if URL is local (relative or absolute local path)."""
    url = url.strip()
    if not url:
        return False

    # stage 1: quick checks, don't require filesystem access
    if any(
        [
            url.startswith(("http://", "https://", "javascript:", "mailto:")),
            url.startswith("{{") and url.endswith("}}"),  # Jinja2 style
            "#" in url,
            "://" in url,
            Path(url).suffix in FILE_FILTER_EXTENSIONS,
            re.match(r"^[./]+$", url),  # catch relative paths, "./", "../", "../../"
        ]
    ):
        return False

    # stage 2: filesystem check only if all quick checks passed, mitigates exception
    #  trip ups in lazily evaluated any() statement above
    return not has_index_files(Path(url))


def extract_href_urls_from_content(content: str) -> list[str]:
    """Extract and filter href URLs from HTML content using BeautifulSoup."""
    try:
        soup = BeautifulSoup(content, "html.parser")
        return [
            a_tag.get("href")
            for a_tag in soup.find_all("a", href=True)
            if a_tag.get("href") and href_pass(a_tag.get("href"))
        ]
    except (AttributeError, TypeError, ValueError):
        return []


def process_single_file(file_path: Path, relative_path: str) -> dict[str, list[str]]:
    """Process a single HTML file and return dict of URLs -> [files that reference them]."""
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    filtered_urls = extract_href_urls_from_content(content)
    return {url: [relative_path] for url in filtered_urls}


def process_version_files(
    version_dir: Path, doc_files: list[str]
) -> tuple[dict[str, list[str]], int]:
    """Process all doc files for a version and return dict of URLs -> referencing files."""
    url_references = {}
    files_processed = 0

    for doc_file in doc_files:
        file_path = version_dir / doc_file
        file_url_dict = process_single_file(file_path, doc_file)

        # Merge URLs into main dict, combining referencing file lists
        for url, referencing_files in file_url_dict.items():
            if url in url_references:
                url_references[url].extend(referencing_files)
            else:
                url_references[url] = referencing_files[:]

        if file_path.exists():
            files_processed += 1

    return url_references, files_processed


def check_path_exists(base_dir: Path, path: str) -> tuple[bool, bool]:
    """Check if path exists and return (is_file, is_directory)."""
    try:
        full_path = base_dir / path
        if not full_path.exists():
            return False, False
        return full_path.is_file(), full_path.is_dir()
    except ValueError:
        return False, False


def resolve_target_path(ref_file: str, url: str, version_dir: Path) -> Path:
    """Resolve a URL relative to a referencing file's directory."""
    ref_file_path = version_dir / ref_file
    ref_file_dir = ref_file_path.parent
    target_path = ref_file_dir / url
    return target_path.resolve()


def check_directory_contents(target_dir: Path) -> tuple[bool, bool]:
    """Check if directory has index files and other files."""
    has_index = False
    has_files = False

    if target_dir.exists() and target_dir.is_dir():
        has_index = has_index_files(target_dir)
        files_in_dir = [f for f in target_dir.iterdir() if f.is_file()]
        has_files = len(files_in_dir) > 0

    return has_index, has_files


@dataclass
class PathData:
    """Standardized path data with consistent structure."""

    references: list[dict[str, str]]
    is_file: bool = False
    is_directory: bool = False
    is_server_url: bool = False
    has_index: bool = False
    has_files: bool = False


def create_path_data(relative_target: Path, version_dir: Path) -> dict[str, Any]:
    """Create path data with existence flags and directory metadata."""
    is_file, is_directory = check_path_exists(version_dir, str(relative_target))

    has_index = has_files = False
    if is_directory:
        target_dir = version_dir / relative_target
        has_index, has_files = check_directory_contents(target_dir)

    path_data = PathData(
        references=[],
        is_server_url=False,
        is_file=is_file,
        is_directory=is_directory,
        has_index=has_index,
        has_files=has_files,
    )
    result = asdict(path_data)
    del result["references"]  # Will be created from reference_set
    result["reference_set"] = set()
    return result


def add_reference_to_path(
    existing_path_data: dict[str, Any], ref_file: str, url: str
) -> None:
    """Add a reference to path data in place."""
    if "reference_set" not in existing_path_data:
        existing_path_data["reference_set"] = set()

    existing_path_data["reference_set"].add((ref_file, url))


def check_filesystem(
    url: str,
    referencing_files: list[str],
    version_dir: Path,
    existing_paths: dict[str, Any],
) -> dict[str, Any]:
    """Check filesystem for URL references and return updated paths."""
    updated_paths = existing_paths.copy()

    for ref_file in referencing_files:
        try:
            normalized_target = resolve_target_path(ref_file, url, version_dir)
            relative_target = normalized_target.relative_to(version_dir.resolve())
            relative_target_str = str(relative_target)

            if relative_target_str not in updated_paths:
                updated_paths[relative_target_str] = create_path_data(
                    relative_target, version_dir
                )

            add_reference_to_path(updated_paths[relative_target_str], ref_file, url)

        except ValueError as e:
            print(f"Error resolving path: {e}")
            continue

    return updated_paths


def check_url_status(url: str) -> bool:
    """Check if a URL returns a 404 status (single attempt, no retries)."""
    try:
        response = requests.head(url, timeout=10, allow_redirects=True)
        return response.status_code != 404
    except requests.RequestException:
        return False


def check_server(
    url: str,
    referencing_files: list[str],
    version_dir: Path,
    existing_paths: dict[str, Any],
    version_slug: str = "",
) -> dict[str, Any]:
    """Check server for URL references by fetching HTML from server and checking URLs."""
    updated_paths = existing_paths.copy()

    for ref_file in referencing_files:
        try:
            # Extract version number from slug (boost-1-79-0 -> 1_79_0)
            version_number = version_slug.replace("boost-", "").replace("-", "_")
            response = requests.get(
                f"http://web:8000/doc/libs/{version_number}/{ref_file}", timeout=15
            )
            if response.status_code != 200:
                continue

            all_hrefs = extract_href_urls_from_content(response.text)
            if url in all_hrefs:
                url_exists = check_url_status(url)
                if url not in updated_paths:
                    path_data = PathData(
                        references=[],
                        is_server_url=True,
                        is_file=url_exists,
                        is_directory=False,
                        has_index=False,
                        has_files=False,
                    )
                    result = asdict(path_data)
                    del result["references"]  # Will be created from reference_set
                    result["reference_set"] = set()
                    updated_paths[url] = result

                add_reference_to_path(updated_paths[url], ref_file, url)

        except (requests.RequestException, ValueError, KeyError):
            continue

    return updated_paths


def is_django_template_url(url: str) -> bool:
    """Check if URL looks like a Django template (contains template syntax)."""
    return "{%" in url or "{{" in url


def process_url_reference(
    url: str,
    referencing_files: list[str],
    version_dir: Path,
    existing_paths: dict[str, Any],
    version_slug: str = "",
) -> dict[str, Any]:
    """Process a single URL and its referencing files, returning updated paths."""
    if is_django_template_url(url):
        return check_server(
            url, referencing_files, version_dir, existing_paths, version_slug
        )
    else:
        return check_filesystem(url, referencing_files, version_dir, existing_paths)


def analyze_version_urls(version_data: dict[str, Any], base_dir: str) -> dict[str, Any]:
    """Analyze all documentation files for a version, extract URLs, and verify paths."""
    version_name = version_data.get("version")
    slug = version_data.get("slug")
    doc_files = version_data.get("doc_files", [])
    directory_exists = version_data.get("directory_exists", False)

    if not version_name or not slug:
        raise ValueError(
            f"Missing required fields: version_name={version_name}, slug={slug}"
        )

    if not directory_exists:
        return {"version": version_name, "directory_exists": False, "paths": {}}

    version_dir = Path(base_dir) / slug.replace("-", "_")
    url_references, files_processed = process_version_files(version_dir, doc_files)

    # Process each URL and verify paths
    paths_result = {}
    for url, referencing_files in url_references.items():
        paths_result = process_url_reference(
            url, referencing_files, version_dir, paths_result, slug
        )

    # Convert reference sets to lists for JSON serialization
    for path_data in paths_result.values():
        path_data["references"] = [
            {"referencing_file": ref_file, "original_url": url}
            for ref_file, url in path_data.pop("reference_set", set())
        ]

    return {
        "version": version_name,
        "directory_exists": directory_exists,
        "version_directory": slug.replace("-", "_"),
        "total_doc_files": len(doc_files),
        "files_processed": files_processed,
        "paths": paths_result,
    }


@click.command()
@click.option(
    "--json-file", required=True, help="JSON file containing documentation information"
)
@click.option(
    "--base-dir",
    default="tarballs",
    help="Base directory containing extracted tarballs",
)
@click.option(
    "--output-dir",
    required=True,
    help="Directory to write individual version JSON files",
)
def command(json_file: str, base_dir: str, output_dir: str):
    """Analyze local documentation URLs and verify that referenced paths exist.

    Takes a JSON file with documentation file information, scans each HTML file
    to extract local href URLs, then verifies that all referenced files and
    directories actually exist in the extracted tarballs. Writes individual
    JSON files for each version.

    Examples:
        python manage.py analyze_docs_urls --json-file=tarballs/docs_files.json --output-dir=nginx_redirects_data
    """
    docs_data = load_json_list(json_file)
    if not docs_data:
        return

    if not Path(base_dir).exists():
        click.echo(f"Warning: Base directory '{base_dir}' does not exist")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    for version_data in docs_data:
        version_name = version_data.get("version", "unknown")
        version_slug = version_name.replace("boost-", "")
        output_file = Path(output_dir) / f"{version_slug}_paths.json"

        if output_file.exists():
            click.echo(f"Skipping {version_name} - {output_file} already exists")
            continue

        result = analyze_version_urls(version_data, base_dir)

        output_file.write_text(json.dumps([result], indent=2))
        output_file.chmod(0o666)

        click.echo(f"Written {output_file}")
