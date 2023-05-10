from datetime import datetime

from django.core.management.base import BaseCommand

from libraries.github import GithubAPIClient
from libraries.models import Library, LibraryVersion
from versions.models import Version


class Command(BaseCommand):
    """Import the releases from Github as best we can.

    1. Get all the Boost tags for the main repo
    2. For each tag, get the release data:
      - If it's a full release (shows up in the "releases" tab), the data is in the tag
      - If it's not a release, the data is in the commit
    3. Get or create it as a Version model instance
    4. Attach each Library to the most recent Version so we don't break existing functionality.
    """

    help = "Import the releases from Github as best we can."

    def handle(self, *args, **options):
        # Clear Versions
        # Version.objects.all().delete()

        # Get all Boost tags from Github
        client = GithubAPIClient()
        tags = client.get_tags()
        for tag in tags:
            name = tag["name"]

            # Skip beta releases
            if any(["beta" in name.lower(), "-rc" in name.lower()]):
                continue

            tag_data = client.get_tag_by_name(name)

            version_data = None
            if tag_data:
                # This is a tag and a release, so the metadata is in the tag itself
                version_data = parse_tag(tag_data)
            else:
                # This is a tag, but not a release, so the metadata is in the commit
                commit_data = client.get_commit_by_sha(commit_sha=tag["commit"]["sha"])
                version_data = parse_commit(commit_data)

            if not version_data:
                # fixme: log this
                continue

            version, _ = Version.objects.get_or_create(name=name, defaults=version_data)
            print(f"Created version {version.name}. Created: {_}")

        # Associate existing Libraries with the most recent LibraryVersion
        version = Version.objects.most_recent()
        for library in Library.objects.all():
            library_version, _ = LibraryVersion.objects.get_or_create(
                library=library, version=version
            )
            print(f"Created library version {library_version}. Created: {_}")


def parse_tag(tag_data):
    """Parse the tag data from Github and return a dict of the data we want."""
    published_at = tag_data.get("published_at", "")
    description = tag_data.get("body", "")
    release_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").date()
    return {
        "release_date": release_date,
        "description": description,
    }


def parse_commit(commit_data):
    """Parse the commit data from Github and return a dict of the data we want."""
    published_at = commit_data["committer"]["date"]
    description = commit_data.get("message", "")
    release_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").date()
    return {
        "release_date": release_date,
        "description": description,
    }
