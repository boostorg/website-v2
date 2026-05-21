"""Seed release-notes RenderedContent for every Version in the local DB.

Fetches each version's history page from the boostorg/website repo on GitHub
(the same source the prod pipeline falls back to when S3 is empty), runs it
through `process_release_notes` for parity with prod content, and upserts a
`RenderedContent` row keyed by `version.release_notes_cache_key`.

Run from the project root:

    docker compose exec web ./manage.py shell < scripts/seed_release_notes_all.py
"""

import requests

from core.models import RenderedContent
from versions.models import Version
from versions.releases import process_release_notes

BASE_URL = "https://raw.githubusercontent.com/boostorg/website/master/users/history/"
TIMEOUT = 30


def _filename_for(version):
    # boost-1.89.0 -> version_1_89_0, mirrors get_release_notes_for_version_github.
    return version.non_beta_slug.replace("boost", "version").replace("-", "_")


def _fetch(filename):
    url = f"{BASE_URL}{filename}.html"
    response = requests.get(url, timeout=TIMEOUT)
    if response.status_code == 404:
        # Some beta release notes end in _x.html instead of _0.html.
        fallback = filename.rsplit("_", 1)[0] + "_x"
        response = requests.get(f"{BASE_URL}{fallback}.html", timeout=TIMEOUT)
    return response


seeded, skipped, failed = [], [], []

for version in Version.objects.all().order_by("name"):
    if not version.cleaned_version_parts:
        skipped.append((version.name, "no version number"))
        continue

    filename = _filename_for(version)
    try:
        response = _fetch(filename)
        response.raise_for_status()
    except requests.RequestException as exc:
        failed.append((version.name, str(exc)))
        continue

    processed = process_release_notes(response.content)
    RenderedContent.objects.update_or_create(
        cache_key=version.release_notes_cache_key,
        defaults={
            "content_type": "text/html",
            "content_original": response.text,
            "content_html": processed,
        },
    )
    seeded.append(version.name)

print(f"Seeded: {len(seeded)}")
for name in seeded:
    print(f"  ok    {name}")
print(f"Skipped: {len(skipped)}")
for name, reason in skipped:
    print(f"  skip  {name} ({reason})")
print(f"Failed: {len(failed)}")
for name, reason in failed:
    print(f"  fail  {name} ({reason})")
