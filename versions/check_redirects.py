#!/usr/bin/env python3
import time
import requests
from urllib.parse import urlparse
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from versions.utils.common import load_json_dict


def check_url_status(url, timeout=10):
    """Check if URL returns status 200."""
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        return response.status_code
    except requests.exceptions.RequestException as e:
        return f"Error: {str(e)}"


def is_valid_url(url):
    """Check if URL is valid and not empty."""
    if not url or url.strip() == "":
        return False

    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except (ValueError, TypeError):
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Check if destination URLs in known_redirects.json return status 200"
    )
    parser.add_argument("redirects_file", help="Path to known_redirects.json file")
    args = parser.parse_args()

    redirects_file = Path(args.redirects_file)
    if not redirects_file.exists():
        print(f"Error: {redirects_file} not found")
        sys.exit(1)
    print("Loading redirects...")
    redirects_data = load_json_dict(str(redirects_file))
    if not redirects_data:
        print(f"Error: Could not load redirects from {redirects_file}")
        sys.exit(1)

    valid_redirects = {
        source_path: data
        for source_path, data in redirects_data.items()
        if is_valid_url(data.get("destination", ""))
    }

    total_redirects = len(valid_redirects)
    print(f"Found {total_redirects} valid redirect entries to check")
    print("Starting URL status checks with 1 second delay between requests...\n")

    success_count = 0
    error_count = 0
    results = []

    for i, (source_path, data) in enumerate(valid_redirects.items(), 1):
        destination_url = data["destination"]

        print(f"[{i}/{total_redirects}] Checking: {destination_url}")

        status = check_url_status(destination_url)

        if status == 200:
            success_count += 1
            status_text = "✓ 200 OK"
        else:
            error_count += 1
            status_text = f"✗ {status}"

        print(f"{status_text}")
        results.append(
            {
                "source_path": source_path,
                "destination_url": destination_url,
                "status": status,
                "success": status == 200,
            }
        )

        if i < total_redirects:
            time.sleep(1)

    print("\n" + "=" * 50)
    print(f"Total URLs checked: {total_redirects}")
    print(f"Successful (200): {success_count}")
    print(f"Failed/Error: {error_count}")
    print(f"Success rate: {success_count/total_redirects*100:.1f}%")

    failed_results = [r for r in results if not r["success"]]
    if failed_results:
        print("\nFailed URLs:")
        for result in failed_results:
            print(f"  {result['status']}: {result['destination_url']}")


if __name__ == "__main__":
    main()
