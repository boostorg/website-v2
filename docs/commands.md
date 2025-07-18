# Management Commands

- [Management Commands](#management-commands)
  - [`boost_setup`](#boost_setup)
  - [`import_versions`](#import_versions)
  - [`import_archives_release_data`](#import_archives_release_data)
  - [`import_artifactory_release_data`](#import_artifactory_release_data)
  - [`update_libraries`](#update_libraries)
  - [`import_library_versions`](#import_library_versions)
  - [`import_library_version_docs_urls`](#import_library_version_docs_urls)
  - [`update_maintainers`](#update_maintainers)
  - [`update_authors`](#update_authors)
  - [`import_commits`](#import_commits)
  - [`update_issues`](#update_issues)
  - [`import_beta_release`](#import_beta_release)
  - [`sync_mailinglist_stats`](#sync_mailinglist_stats)
  - [`update_library_version_dependencies`](#update_library_version_dependencies)
  - [`release_tasks`](#release_tasks)

## `boost_setup`

Runs the management commands required to populate the Boost database from scratch with Boost versions, libraries, and other associated data.

Read more about `boost_setup` in [Populating the Database for the First Time](./first_time_data_import.md).

**Example**

```bash
./manage.py boost_setup
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--token`            | string | GitHub API Token. If passed, will use this value. If not passed, will use the value in settings. |

**Process**: See [Populating the Database for the First Time](./first_time_data_import.md).

## `import_versions`

Imports `Version` objects from GitHub.

**Example**

```bash
./manage.py import_versions
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--delete-versions`  | bool   | If passed, will delete all Version objects before importing Versions. |
| `--new`  | bool   | If passed, will import only new Version objects. |
| `--token`            | string | GitHub API Token. If passed, will use this value. If not passed, will use the value in settings. |

**Process**

- Retrieves the tags for the GitHub repo in `BASE_GITHUB_URL`
- Loops through all tags, and discards any that do not match our inclusion logic
- For each successful tag, import it as a `Version` object
- Then, run the command to the release downloads from Artifactory as `VersionFile` objects

## `import_archives_release_data`

*This process is run automatically as part of `import_versions`.*

Import `VersionFile` objects from Artifactory.

**Example**

```bash
./manage.py import_archives_release_data
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--release`  | string   | Format: `boost-1.63.0`. If passed, will import Archive urls for only that version. |

**More Information**

- Loops through `Version` objects and calls the task that retrieves the Archives data with the version information
- Saves the Archives JSON data as `VersionFile` objects


## `import_artifactory_release_data`

*This process was run automatically as part of `import_versions`, but has been replaced by `import_archives_release_data`.*

Import `VersionFile` objects from Artifactory.

**Example**

```bash
./manage.py import_artifactory_release_data
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--release`  | string   | Format: `boost-1.63.0`. If passed, will import Artifactory urls for only that version. |

**More Information**

- Loops through `Version` objects and calls the task that retrieves the Artifactory data with the version information
- Saves the Artifactory data as `VersionFile` objects


## `update_libraries`

**Purpose**: Import and update `Library` and `Category` objects. Runs the library update script, which cycles through the repos listed in the Boost library and syncs their information. Most library information comes from `meta/libraries.json` stored in each Boost library repo.

**Example**

```bash
./manage.py update_libraries
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--token`            | string | GitHub API Token. If passed, will use this value. If not passed, will use the value in settings. |

## `import_library_versions`

**Purpose**: Import and update `LibraryVersion` objects.

**Example**

```bash
./manage.py import_library_versions
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--token`            | string | GitHub API Token. If passed, will use this value. If not passed, will use the value in settings. |
| `--release`  | string   | Format: `boost-1.63.0`. If passed, will import Artifactory urls for only that version. Partial versions are accepted (so "1.7" will import libraries for version 1.70.0, 1.71.0, etc.) |

**Process**

- Loops through `Version` objects based on passed-in options
- For each `Version`, gets the libraries in that release from the `.gitmodules` file using the GitHub API
- For each library listed in the `.gitmodules` file, get the complete list of libraries from the library's `meta/libraries.json` file (in its GitHub repo) using the GitHub API. (A single library repo might contain information for multiple libraries. Example: Functional also hosts Functional/Factory).
- Save the `LibraryVersion` objects
- Call the task to import documentation urls from data hosted in the S3 bucket


## `import_library_version_docs_urls`

*This process is taken care of automatically as part of `import_library_versions`.*

**Purpose**: Because of uniqueness in Boost library data, it's not possible to consistently format the URL for each Boost library-version. The current process involves hitting the url for the page in the Boost release notes that lists all the libraries and manually copying the URLs from the `<ul>` on that page to each `LibraryVersion` object.

**Example**

```bash
./manage.py get_library_version_documentation_urls --version=1.81.0
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--min-version`            | string | Specify the minimum version for which you want to retrieve documentation URLs. The default is defined in the settings file. |
| `--version`  | string   | Format: `1.81.0`. Specify the version for which you want to retrieve documentation URLs. You can provide a specific version number (example: `1.81.0`) or a partial version number to process all versions that contain the partial version number (example: `1.7` would process 1.70.0, 1.71.0, 1.72.0, etc.). If no version is specified, all active versions will be processed. |

**Process**

- This command cycles through all Versions in the database, or specified versions using the `--version` option.
- For each version, the command calls a celery task that retrieves and stores the library version documentation url paths from S3.
- If a library version's documentation URL cannot be found, the command will skip and continue with the next library version.

## `update_maintainers`

Cycles through all library-versions and uses the `maintainers` element in the `data` JSONField to load the maintainer information from GitHub into the database.

**Example**

```bash
./manage.py update_maintainers
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--library-name`  | string   | Name of the library. If passed, the command will load maintainers for only this library. |
| `--release`  | string   | Format: `boost-1.63.0`. If passed, will import Artifactory urls for only that version. |

If both the `--release` and the `--library-name` are passed, the command will load maintainers for only that Library-Version.

## `update_authors`

**Purpose**: Cycles through all libraries and uses the `authors` element in the `data` JSONField to load the author information from GitHub into the database.

**Example**

```bash
./manage.py update_authors
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--library-name`  | string   | Name of the library. If passed, the command will load maintainers for only this library. |


## `import_commits`

**Purpose**: Cycles through all libraries and their library versions to import `Commit`, `CommitAuthor`, and `CommitAuthorEmail` models. Updates `CommitAuthor` github profile URLs and avatar URLs.

**Example**

```bash
./manage.py import_commits
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--key`  | string   | Key of the library. If passed, the command will import commits for only this library. |
| `--clean`  | boolean   | If passed, will delete all existing commits before importing new ones. |


## `update_issues`

**Purpose**: Cycles through all libraries and imports github Issues for that Library

**Example**

```bash
./manage.py update_issues
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--key`  | string   | Key of the library. Only update_issues for one library. |
| `--clean`  | boolean   | If passed, will delete the libraries' issues just before running the import. |


## `import_beta_release`

**Purpose**: Imports the most recent beta release

**Example**

```bash
./manage.py import_beta_release
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--token`  | string   | Pass a GitHub API token. If not passed, will use the value in `settings.GITHUB_TOKEN`. |
| `--delete-versions`  | bool  | If passed, all existing beta Version records will be deleted before the new beta release is imported. |


## `sync_mailinglist_stats`

**Purpose**: Build EmailData objects from the hyperkitty email archive database.

**Example**

```bash
./manage.py sync_mailinglist_stats
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--clean`  | bool  | If passed, all existing beta EmailData records will be deleted before running the sync. |


## `update_library_version_dependencies`

**Purpose**: Read a boostdep report text file uploaded as an artifact from a github action and update dependencies for LibraryVersion models.

**Example**

```bash
./manage.py update_library_version_dependencies
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--token`  | string  | Pass a GitHub API token. If not passed, will use the value in `settings.GITHUB_TOKEN`. |
| `--clean`  | bool    | If passed, existing dependencies in the M2M will be cleared before reinserting them. |
| `--owner`  | string  | The repo owner. Defaults to "boostorg", which is correct in most cases but can be useful to specify for testing. |


## `release_tasks`

**Purpose**: Execute a chain of commands which are necessary to run during a release. Imports new versions, beta versions, slack messages, github issues, commits, authors, maintainers, etc... Inspect the management command to see exactly which commands are being run.

For this to work `SLACK_BOT_API` must be set in the `.env` file.

**Example**

```bash
./manage.py release_tasks
```

**Options**

| Options              | Format | Description                                                  |
|----------------------|--------|--------------------------------------------------------------|
| `--user_id`  | int  | If passed, the user with this ID will receive email notifications when this task is started and finished, or if the task raises and exception. |


## `import_ml_counts`

**Purpose**: Import mailing list counts from the mailman archives.

```bash
./manage.py import_ml_counts
```

**Options**

| Options        | Format | Description                                                                                                          |
|----------------|--------|----------------------------------------------------------------------------------------------------------------------|
| `--start_date` | date   | If passed, retrieves data from the start date supplied, d-m-y, default 1998-11-20 (the start of the data in mailman) |
| `--end_date`   | date   | If passed, If passed, retrieves data until the start date supplied, d-m-y, default today                             |

## `link_contributors_to_users`

**Purpose**: Links commit authors to users in the database by setting `user.github_username` for users where no `github_username` value has been set, by matching the commit author email address against a user's account email address.


**Example**

```bash
./manage.py link_contributors_to_users
```
