import re

import pytest
from django.urls import resolve, Resolver404

NGINX_CONFIG_FILE_PATH = "kube/boost/templates/configmap-nginx.yaml"


def _extract_redirects_from_nginx_config():
    redirects = []
    with open(NGINX_CONFIG_FILE_PATH, "r") as f:
        config = f.read()

    # Match static mappings
    static_pattern = re.compile(r"location(?: ~)? =? (.*?) \{ return 301 (.*?); \}")
    static_matches = static_pattern.findall(config)

    for source, destination in static_matches:
        redirects.append((source.strip(), destination.strip()))

    # Match regex-based mappings
    regex_pattern = re.compile(r"location ~ (.*?) \{ return 301 (.*?); \}")
    regex_matches = regex_pattern.findall(config)

    for source, destination in regex_matches:
        # Example: Add dynamic cases for the "version" regex
        if source.strip() == "^/users/history/version_(\\d+)_(\\d+)_(\\d+)\\.html$":
            # Generate test cases for a few example versions
            examples = [
                ("/users/history/version_1_22_0.html", "/releases/1.22.0/"),
                ("/users/history/version_1_84_0.html", "/releases/1.84.0/"),
                ("/users/history/version_1_87_0.html", "/releases/1.87.0/"),
            ]
            redirects.extend(examples)

    print(f"\n\n{redirects}\n\n")

    return redirects


@pytest.mark.parametrize(
    "source,expected_redirect", _extract_redirects_from_nginx_config()
)
def test_nginx_redirects(tp, source, expected_redirect):
    """
    Test nginx redirect mappings contain all valid redirects.
    """
    if expected_redirect.startswith("http"):
        pytest.skip(f"Skipping external URL: {expected_redirect}")
    if expected_redirect == "$scheme://$host":
        pytest.skip("Skipping $scheme://$host redirect")

    try:
        resolve(expected_redirect)
    except Resolver404:
        pytest.fail(f"URL cannot be resolved: {expected_redirect}")
