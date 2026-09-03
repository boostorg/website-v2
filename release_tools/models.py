"""Admin-only proxies. Nothing here adds a table."""

from versions.models import Version


class ReleaseLibraryData(Version):
    """A `Version` seen from the release tools page.

    A proxy, not a model: the page needs somewhere to hang its own admin URLs and
    permissions, and the thing an operator picks on it is a release.
    """

    class Meta:
        proxy = True
        verbose_name = "release library data"
        verbose_name_plural = "Library data"
