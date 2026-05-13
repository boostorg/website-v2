"""QA helper: seed a Boost Version + release-notes RenderedContent row so
the `generate_whats_new` command has something to summarize.

Run from the project root:

    docker compose exec web ./manage.py shell < scripts/seed_whats_new_qa.py

To target a different release, edit NAME / RELEASE_NOTES_URL below.
"""

import requests

from core.models import RenderedContent
from versions.models import Version

NAME = "boost-1.89.0"
RELEASE_NOTES_URL = (
    "https://raw.githubusercontent.com/boostorg/website/master/"
    "users/history/version_1_89_0.html"
)

version, _ = Version.objects.update_or_create(
    name=NAME,
    defaults={
        "active": True,
        "fully_imported": True,
        "full_release": True,
        "beta": False,
        "github_url": f"https://github.com/boostorg/boost/releases/tag/{NAME}",
    },
)

response = requests.get(RELEASE_NOTES_URL, timeout=30)
response.raise_for_status()

RenderedContent.objects.update_or_create(
    cache_key=version.release_notes_cache_key,
    defaults={
        "content_type": "text/html",
        "content_html": response.text,
        "content_original": "",
    },
)

print(f"Seeded {version.name} (slug={version.slug}, pk={version.pk})")
print(f"Cache key: {version.release_notes_cache_key}")
print(
    f"Next:  docker compose exec web ./manage.py generate_whats_new --version={version.slug} --force"
)
