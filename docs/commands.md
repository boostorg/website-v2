# Management Commands

## `import_commit_counts`

Imports commit counts for all libraries, broken down by month, and saves them to the database. The command uses the Github API to retrieve commit data and is intended for a one-time import.

- Saves `CommitData` objects, one per month, with a count of the number of commits made to the specified branch (or the `master` branch) of each Library object.
- If there is already a `CommitData` record for that library-month-branch, this command will **overwrite** the `commit_count` field, not increment it.
- Idempotent.

**Options**

Here are the options you can use:

- `--branch`: Specify the branch you want to count commits for. Defaults to `master`.
- `--token`: Pass a GitHub API token. If not passed, will use the value in `settings.GITHUB_TOKEN`.

### Example:

    ./manage.py import_commit_counts

Output:

    ...
    {"message": "commit_data_updated", "commit_data_pk": 721, "obj_created": true, "library": "Math/Statistical Distributions", "branch": "master", "logger": "libraries.github", "level": "info", "timestamp": "2023-05-25T22:13:58.074730Z"}
    Updated Math/Statistical Distributions commits; 247 monthly counts added


## `import_library_version_docs_urls`

This command retrieves and stores the documentation URLs for specific or all library versions in the database. It provides a way to keep the database updated with the most current URLs for the documentation of each library version.

- This command cycles through all Versions in the database, or specified versions using the `--version` option.
- For each version, the command calls a celery task that retrieves and stores the library version documentation url paths from S3.
- If a library version's documentation URL cannot be found, the command will skip and continue with the next library version.

**Options**

Here are the options you can use:

- `--version`: Specify the version for which you want to retrieve documentation URLs. You can provide a specific version number (example: '1.81.0') or a partial version number to process all versions that contain the partial version number (example: '--version=1.7' would process 1.70.0, 1.71.0, 1.72.0, etc.). If no version is specified, all active versions will be processed.
- `--min-version`: Specify the minimum version for which you want to retrieve documentation URLs. The default is "1.30.0".

### Example:

    ./manage.py get_library_version_documentation_urls --version=1.81.0

Output:

    Processing version 1.81.0...
    ...
    Processing version 1.81.0...
    Could not get docs url for Math/Statistical Distributions (1.81.0).
    ...

This command is idempotent; running it multiple times with the same arguments will not change the result after the first run.


## `import_library_versions`

Connect Library objects to the Boost versions (AKA "release") that included them using information from the main Boost GitHub repo and the library repos. Functions of this command:

- Prints out any versions or libraries that were skipped at the end.
- Idempotent.

**Options**

Here are the options you can use:

- `--release`: Full or partial Boost version (release) number. If `release` is passed, the command will import all libraries for the versions that contain the passed-in release number. If not passed, the command will import libraries for all active versions newer than the min-release.
- `--min-release`: Specify the minimum version for which you want to retrieve documentation URLs. The default is "1.30.0".
- `--token`: Pass a GitHub API token. If not passed, will use the value in `settings.GITHUB_TOKEN`.

### Example:

    ./manage.py import_library_versions

Output:

    Saved library version Log (boost-1.16.1).
    Processing version boost-0.9.27...
    Processing module python...
    Saved library version Python (boost-0.9.27). Created? False
    User stefan@seefeld.name added as a maintainer of Python (boost-0.9.27)
    {"message": "User username added as a maintainer of Python (boost-0.9.27)", "logger": "libraries.github", "level": "info", "timestamp": "2023-05-17T21:24:39.046029Z"}
    Updated maintainers for Python (boost-0.9.27).
    Saved library version Python (boost-0.9.27).
    Skipped disjoint_sets in boost-1.57.0: Could not find library in database by gitmodule name
    Skipped signals in boost-1.57.0: Could not find library in database by gitmodule name


## `import_versions`

Import Boost version (AKA "release") information from the Boost GitHub repo. Functions of this command:

- **Retrieves Boost tags**: It collects all the Boost tags from the main Github repo, excluding beta releases and release candidates. For each tag, it gathers the associated data. If it's a full release, the data is in the tag; otherwise, the data is in the commit.
- **Updates local database**: For each tag, it creates or updates a Version instance in the local database.
- Adds the download links from Artifactory for the release downloads
- Idempotent.

**Options**

Here are the options you can use:

- `--delete-versions`: Deletes all existing Version instances in the database before importing new ones.
- `--token`: Pass a GitHub API token. If not passed, will use the value in `settings.GITHUB_TOKEN`.
- `--verbose`: Print output information


### Example:

    ./manage.py import_versions

Output:

    Saved version boost-1.82.0. Created: True
    Skipping boost-1.82.0.beta1, not a full release
    Saved version boost-1.81.0. Created: True
    Skipping boost-1.81.0.beta1, not a full release
    ...


## `update_libraries`

Runs the library update script, which cycles through the repos listed in the Boost library and syncs their information.

Synced information:

- Most library information comes from `meta/libraries.json` stored in each Boost library repo
- Library data and metadata from GitHub is saved to our database
- Categories are updated, if needed
- Library categories are updated, if need be.
- Issues and Pull Requests are synced

**For local development**: Run with the `--local` flag. This skips pulling Issues and Pull Requests data, Commit history, and other data that takes a long time to run.

**NOTE**: Can take upwards of a half hour to run if the `--local` flag is not passed.
