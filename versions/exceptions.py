class BoostImportedDataException(Exception):
    """Custom exception for Boost data errors."""

    pass


class PostImportStepFailed(Exception):
    """A step that runs after a release's library metadata was written failed.

    ``import_library_versions`` ends by scraping documentation URLs and loading
    maintainers, both of which run only once every library's metadata is in the
    database. A caller that needs that metadata and not those steps - the
    per-release repair in ``libraries.tasks.synchronize_release_library_data`` -
    has to be able to tell such a failure from one that wrote nothing at all, so
    it is raised as this and carries the keys the import managed to read.
    """

    def __init__(self, library_keys):
        super().__init__(
            "A step after the library metadata was written failed; "
            "the metadata itself is in place."
        )
        self.library_keys = library_keys
