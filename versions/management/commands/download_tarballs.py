import djclick as click
import os
import requests
from pathlib import Path
from urllib.parse import urljoin
import time
from typing import List
from enum import Enum


class DownloadResult(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


def download_file(url: str, destination_path: Path, chunk_size: int = 8192) -> bool:
    """Download a file from URL to destination path with progress indication."""
    try:
        click.echo(f"download {url=}")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded_size = 0

        with open(destination_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)

                    if total_size > 0:
                        progress = (downloaded_size / total_size) * 100
                        click.echo(
                            f"\rDownloading {os.path.basename(destination_path)}: {progress:.1f}%",
                            nl=False,
                        )

        click.echo()  # New line after progress
        return True

    except requests.exceptions.RequestException as e:
        click.echo(f"Error downloading {url}: {e}", err=True)
        return False


def get_filename_from_url(url: str) -> str:
    """Extract filename from URL, fallback to timestamp-based name."""
    filename = os.path.basename(url)
    return (
        filename
        if filename and "." in filename
        else f"tarball_{int(time.time())}.tar.bz2"
    )


def build_download_urls(base_url: str, filenames: List[str]) -> List[str]:
    """Build complete URLs from base URL and filenames."""
    return [urljoin(base_url.rstrip("/") + "/", fname) for fname in filenames]


def should_skip_existing_file(destination: Path, overwrite: bool) -> bool:
    """Check if file should be skipped due to existing file."""
    return not overwrite and destination.exists()


def download_with_retries(
    url: str, destination: Path, max_retries: int, retry_delay: int
) -> bool:
    """Download file with retry logic."""
    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            click.echo(f"Retry attempt {attempt}/{max_retries}")

        success = download_file(url, destination)
        if success:
            return True
        elif attempt < max_retries:
            time.sleep(retry_delay)

    return False


def process_single_download(
    download_url: str,
    output_path: Path,
    overwrite: bool,
    max_retries: int,
    retry_delay: int,
) -> DownloadResult:
    """Process a single file download."""
    filename = get_filename_from_url(download_url)
    destination = output_path / filename

    if should_skip_existing_file(destination, overwrite):
        click.echo(f"File {filename} exists, skipping (use --overwrite to replace)")
        return DownloadResult.SKIPPED

    if download_with_retries(download_url, destination, max_retries, retry_delay):
        try:
            click.echo(f"Downloaded {filename}")
            return DownloadResult.SUCCESS
        except FileNotFoundError:
            click.echo(f"Error: File {filename} was not created after download.")
            return DownloadResult.FAILED
    else:
        click.echo(f"Failed to download {filename}")
        if destination.exists():
            destination.unlink()
        return DownloadResult.FAILED


def print_download_summary(
    successful: int, failed: int, skipped: int, total: int
) -> None:
    """Print download completion summary."""
    click.echo("\nDownload Summary:")
    click.echo(f"  Successful: {successful}")
    click.echo(f"  Already downloaded: {skipped}")
    click.echo(f"  Failed: {failed}")
    click.echo(f"  Total: {total}")


@click.command()
@click.option("--base-url", required=True, help="Base URL to combine with filenames")
@click.option(
    "--filename",
    multiple=True,
    required=True,
    help="Filename to append to base URL (can be used multiple times)",
)
@click.option(
    "--output-dir",
    default="/code/tarballs",
    help="Output directory for downloaded files",
)
@click.option("--overwrite", is_flag=True, help="Overwrite existing files")
@click.option(
    "--max-retries", default=3, help="Maximum number of retry attempts per URL"
)
@click.option("--delay", default=1, help="Delay in seconds between downloads")
def command(
    base_url: str,
    filename: List[str],
    output_dir: str,
    overwrite: bool,
    max_retries: int,
    delay: int,
) -> None:
    """Download one or more tarballs using base URL + filenames.

    Combines a base URL with multiple filenames to download tarballs.

    Examples:
        # Download using base URL + filenames
        python manage.py download_tarballs --base-url=https://archives.boost.io/release/ --filename=boost_1_81_0.tar.bz2 --filename=boost_1_82_0.tar.bz2

        # With custom settings
        python manage.py download_tarballs --base-url=https://archives.boost.io/release/ --filename=boost_1_81_0.tar.bz2 --overwrite --max-retries=5 --delay=2
    """
    urls_to_download = build_download_urls(base_url, filename)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    click.echo(
        f"Downloading {len(urls_to_download)} tarball(s) to {output_path.absolute()}"
    )

    results = {
        DownloadResult.SUCCESS: 0,
        DownloadResult.FAILED: 0,
        DownloadResult.SKIPPED: 0,
    }
    for i, download_url in enumerate(urls_to_download, 1):
        click.echo(f"\n[{i}/{len(urls_to_download)}] Processing: {download_url}")
        result = process_single_download(
            download_url, output_path, overwrite, max_retries, delay
        )
        results[result] += 1

        if i < len(urls_to_download) and delay > 0:
            time.sleep(delay)

    print_download_summary(
        results[DownloadResult.SUCCESS],
        results[DownloadResult.FAILED],
        results[DownloadResult.SKIPPED],
        len(urls_to_download),
    )

    if results[DownloadResult.FAILED] > 0:
        exit(1)
