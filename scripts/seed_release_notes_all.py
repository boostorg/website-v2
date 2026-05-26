"""Seed release-notes RenderedContent for every Version in the local DB.

Uses the same source-of-truth strategy as prod (`get_release_notes_for_version`):
S3 first (asciidoc, for 1.90.0 onwards), falling back to the boostorg/website
GitHub history page (html) for older versions. Upserts a `RenderedContent` row
keyed by `version.release_notes_cache_key`.

Run from the project root:

    docker compose run web ./manage.py shell < scripts/seed_release_notes_all.py
"""

from core.models import RenderedContent
from versions.models import Version
from versions.releases import get_release_notes_for_version

seeded, skipped, failed = [], [], []

for version in Version.objects.all().order_by("name"):
    if not version.cleaned_version_parts:
        skipped.append((version.name, "no version number"))
        continue

    try:
        content, processed_content, content_type = get_release_notes_for_version(
            version.pk
        )
    except Exception as exc:
        failed.append((version.name, str(exc)))
        continue

    if not content:
        skipped.append((version.name, "no release notes found"))
        continue

    RenderedContent.objects.update_or_create(
        cache_key=version.release_notes_cache_key,
        defaults={
            "content_type": content_type,
            "content_original": content,
            "content_html": processed_content,
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
