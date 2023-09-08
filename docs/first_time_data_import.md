# Populating the Database for the First Time

- [Deployed Environments](#deployed-environments)
- [Further Reading](#further-reading)

This document contains information about importing Boost Versions (also called Releases), Libraries, and the data associated with those objects. It is concerned with importing data in **deployed environments**, but at the bottom of the page there is a section on importing data for **local development**.

## Deployed Environments

There are several steps to populating the database with historical Boost data, because we retrieve Boost data from multiple sources.

You can run all of these steps in sequence in a single command with the command:

```bash
./manage.py boost_setup
```

The `boost_setup` command will run all of the processes listed here:

```bash

# Import Boost releases
./manage.py import_versions
# import_versions also runs import_artifactory_release_data

# Import Boost libraries
./manage.py update_libraries

# Save which Boost releases include which libraries
./manage.py import_library_versions
# import_library_versions retrieves documentation urls, so boost_setup
# doesn't run import_library_version_docs_urls

# Save other data we need for Libraries and LibraryVersions
./manage.py update_maintainers
./manage.py update_authors
./manage.py import_commit_counts
```

Read more aboout these [management commands](./commands.md).

Collectively, this is what these management commands accomplish:

1. `import_versions`: Imports Boost releases as `Version` objects, and imports links to Boost downloads hosted on Artifactory.
2. `update_libraries`: Imports Boost libraries and categories as `Library` and `Category` objects.
3. `import_library_versions`: Establishes which Boost libraries are included in which Boost versions. That information is stored in `LibraryVersion` objects. This process also stores the link to the version-specific Boost documentation for this library.
4. `update_maintainers`: For each `LibraryVersion`, saves the maintainers as `User` objects and makes sure they are associated with the `LibraryVersion`.
5. `update_authors`: For each `Library`, saves the authors as `User` objects and makes sure they are associated with the `Library`.
6. `import_commit_counts`: For each `Library`, uses information in the GitHub API to save the last 12 months of commit history. One `CommitData` object per library, per month is created to store the number of commits to the `master` branch of that library for that month.

## Further Reading

- [Syncing Data about Boost Versions and Libraries with GitHub](./syncing_data_with_github.md)
- Read more aboout the [management commands](./commands.md) you see here.
