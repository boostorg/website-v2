import djclick as click
import requests
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile

from libraries.models import Library
from patches.models import LibraryPatch
from versions.models import Version

ORIGINAL_WEBSITE_URL = "https://original.boost.org/"
ORIGINAL_PATCH_URL = ORIGINAL_WEBSITE_URL + "patches/"


@click.command()
def command():
    response = requests.get(ORIGINAL_PATCH_URL)
    soup = BeautifulSoup(response.text)

    all_anchors = soup.find_all("a")

    for a in all_anchors:
        href = a.get("href", "")
        # This page contains a great many links, we only care about the ones that link
        # to .patch files
        if href and href.endswith(".patch"):
            # Each file is linked in for the form of `{version_number}/{patch_name}`
            # where the patch name is four number followed by a snake cased name .patch
            # e.g. 0001_catalog_example.patch
            # The first word after the number is the library, if this patch is for a specific library
            split = href.split("/")
            semantic_version = split[0]
            patch_name = split[1]
            # Make sure patch name is in our expected shape
            patch_split = patch_name.split("-")
            if len(patch_split) > 1:
                library_name = patch_split[1].removesuffix(".patch")
                # Associate the patch with a library if it exists, but some patches are
                # combined (and cover multiple libraries) or apply to internal tools like b2
                try:
                    library = Library.objects.get(name__iexact=library_name)
                except Library.DoesNotExist:
                    library = None
            else:
                library = None

            version = Version.objects.get(
                name=f'boost-{".".join(semantic_version.split("_"))}'
            )
            patch_file = requests.get(ORIGINAL_PATCH_URL + href.removeprefix("/")).text

            library_patch, _ = LibraryPatch.objects.get_or_create(
                library=library,
                version=version,
                patch_name=patch_name,
            )
            library_patch.patch_file.delete()
            library_patch.patch_file.save(patch_name, ContentFile(patch_file))
            library_patch.save()

            print(f"Saved patch {library_patch.patch_name}")
