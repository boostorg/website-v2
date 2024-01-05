# Caching and the `RenderedContent` model

This model is mostly used as a database cache or backup for data that is retrieved from GitHub or from the S3 buckets.

See [Static Content](./static_content.md) for more information about retrieving static content from S3.

Usage:

- Cache static content (like asciidoc content, library documentation, the help pages, anything that is rendered from S3). The `cache_key` field will be prefixed with `static_content_`.
  - There is a Celery task to clear this database cache for all rows older than 7 days, which is set up to run daily.
- Cache a copy of the library description (from the library asciidoc or other readme file). This enables us to load a library description even if the GitHub API goes down. The `cache_key` field will be prefixed with `library_description_`. Because these descriptions are primarily for past versions, they will not update, they will not be deleted from the database cache, and there is no need to retrieve them from GitHub fresh every time.
- Store a copy of the release notes for each Boost version. Because the release notes are for past versions, they will not update, they will not be deleted from the database cache, and there is no need to retrieve them from GitHub fresh every time. The `cache_key` field will be prefixed with `release_notes_`.
