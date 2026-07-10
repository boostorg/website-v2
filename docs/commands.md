# Management Commands

- [Management Commands](#management-commands)
  - [`boost_setup`](#boost_setup)
  - [`import_versions`](#import_versions)
  - [`import_archives_release_data`](#import_archives_release_data)
  - [`update_libraries`](#update_libraries)
  - [`import_library_versions`](#import_library_versions)
  - [`import_library_version_docs_urls`](#import_library_version_docs_urls)
  - [`update_maintainers`](#update_maintainers)
  - [`update_authors`](#update_authors)
  - [`import_commits`](#import_commits)
  - [`update_issues`](#update_issues)
  - [`import_beta_release`](#import_beta_release)
  - [`import_release_notes`](#import_release_notes)
  - [`generate_whats_new`](#generate_whats_new)
  - [`refresh_popular_search_terms`](#refresh_popular_search_terms)
  - [`sync_mailinglist_stats`](#sync_mailinglist_stats)
  - [`update_library_version_dependencies`](#update_library_version_dependencies)
  - [`release_tasks`](#release_tasks)
  - [`import_ml_counts`](#import_ml_counts)
  - [`link_contributors_to_users`](#link_contributors_to_users)
  - [`refresh_users_github_photos`](#refresh_users_github_photos)
  - [`remove_unverified_users`](#remove_unverified_users)
  - [`clear_slack_activity`](#clear_slack_activity)

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

| Options              | Format | Description                                                                                             |
|----------------------|--------|---------------------------------------------------------------------------------------------------------|
| `--delete-versions`  | bool   | If passed, will delete all Version objects before importing Versions.                                   |
| `--new`              | bool   | Default: 'true'. If 'true', will import only new Version objects. Set to 'false' to import all versions |
| `--token`            | string | GitHub API Token. If passed, will use this value. If not passed, will use the value in settings.        |

**Process**

- Retrieves the tags for the GitHub repo in `BASE_GITHUB_URL`
- Loops through all tags, and discards any that do not match our inclusion logic, by default only versions that haven't already been imported.
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

| Options    | Format | Description                                                                                                                  |
|------------|--------|------------------------------------------------------------------------------------------------------------------------------|
| `--new`    | bool   | Default: 'true'. If 'true', imports archive data for the most recent full release and (if one exists) the most recent beta release. Set to 'false' to import archive data for all releases |
| `--release` | string   | Format: `boost-1.63.0`. If passed, will import Archive urls for only that release. Overrides --new                        |

**More Information**

- Loops through `Version` objects, by default only the most recent one, and calls the task that retrieves the Archives data with the version information
- Saves the Archives JSON data as `VersionFile` objects

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

| Options              | Format | Description                                                                                                                                                                            |
|----------------------|--------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `--token`            | string | GitHub API Token. If passed, will use this value. If not passed, will use the value in settings.                                                                                       |
| `--release`  | string   | Format: `boost-1.63.0`. If passed, will import Artifactory urls for only that version. Partial versions are accepted (so "1.7" will import libraries for version 1.70.0, 1.71.0, etc.) |
| `--new`    | bool   | Default: 'true'. If 'true', will import data for the newest release. Set to 'false' to import library version data for all releases                                                    |

**Process**

- Loops through `Version` objects based on passed-in options, by default just the most recent one.
- For each `Version`, gets the libraries in that release from the `.gitmodules` file using the GitHub API
- For each library listed in the `.gitmodules` file, get the complete list of libraries from the library's `meta/libraries.json` file (in its GitHub repo) using the GitHub API. (A single library repo might contain information for multiple libraries. Example: Functional also hosts Functional/Factory).
- Save the `LibraryVersion` objects
- Call the task to import documentation urls from data hosted in the S3 bucket


## `import_library_version_docs_urls`

*This process is taken care of automatically as part of `import_library_versions`.*

**Purpose**: Because of uniqueness in Boost library data, it's not possible to consistently format the URL for each Boost library-version. The current process involves hitting the url for the page in the Boost release notes that lists all the libraries and manually copying the URLs from the `<ul>` on that page to each `LibraryVersion` object.

**Example**

```bash
./manage.py import_library_version_docs_urls --version=1.81.0
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


## `import_release_notes`

**Purpose**: Fetch the rendered release notes for Boost versions and store them in the `RenderedContent` cache (keyed `release_notes_boost-X-XX-X`). Tries the AsciiDoc source on S3 first, falls back to the legacy HTML in the `boostorg/website` GitHub repo. Also fetches the in-progress release notes.

When a release note is freshly stored and the `Version.whats_new` field is empty, this command also queues the AI "What's New" summary task — see [`generate_whats_new`](#generate_whats_new).

**Example**

```bash
./manage.py import_release_notes
```

**Options**

| Options | Format | Description                                                                                  |
|---------|--------|----------------------------------------------------------------------------------------------|
| `--new` | bool   | Default: `true`. If `true`, only imports notes for the most recent version. Set to `false` to import for all active versions. |

## `generate_whats_new`

**Purpose**: Generate the AI-powered "What's New" draft summary for one or more Boost releases. The summary is a short, fixed-rubric bullet list (new libraries, performance, dependencies, security & reliability, developer experience) saved on the `Version` model as `whats_new` (markdown bullets). The public site parses the bullets into `whats_new_items` and renders them in the release-highlights card. Drafts are not shown on the public site until an admin sets `whats_new_approved=True` (also available as a Django admin action).

This command is opt-in. Auto-generation only runs as a side-effect of `import_release_notes` when a version's `whats_new` is empty. Use this command to backfill historical versions or to regenerate after editing the prompt.

The LLM call is a Celery task; the worker must be running and `OPENROUTER_API_KEY` must be set (see [Environment Variables](./env_vars.md)).

**Example**

```bash
./manage.py generate_whats_new --all-missing
./manage.py generate_whats_new --version boost-1-90-0 --force
./manage.py generate_whats_new --validate --limit 10
```

**Options**

| Options          | Format | Description                                                                                                |
|------------------|--------|------------------------------------------------------------------------------------------------------------|
| `--all-missing`  | bool   | Queue generation for every active version that has stored release notes but no `whats_new` summary yet.    |
| `--version`      | string | Slug of a single version to (re)generate. Format: `boost-1-90-0`.                                          |
| `--force`        | bool   | Regenerate even when a summary already exists. The chained save task overwrites `whats_new` and resets `whats_new_approved` to `False`, so regenerated content goes back through admin moderation. |
| `--dry-run`      | bool   | List the versions that would be queued without queuing them.                                               |
| `--validate`     | bool   | Run the prompt synchronously against the latest `--limit` versions (that have release notes) and print the LLM output. No DB writes. Use to review prompt changes before sign-off. |
| `--limit`        | int    | Number of versions to process when `--validate` is set. Default: 10.                                       |

## `refresh_popular_search_terms`

**Purpose**: Refresh the `PopularSearchTerm` rows backing the V3 homepage search-card keyword badges. Calls the same service the weekly Celery task uses: fetches the top searches from Algolia analytics, runs them through the LLM quality filter, and upserts the survivors. Use this to seed local data or to refresh on demand after editing the exclusion list / pinned rows. See [Popular Search Terms on the V3 Homepage](./popular_search_terms.md).

By default the refresh runs **inline** (synchronous) so you see the result immediately; pass `--queue` to dispatch it to Celery instead (same as the admin "Refresh from Algolia" button).

Requires `ALGOLIA_APP_ID`, `ALGOLIA_ANALYTICS_API_KEY` and `OPENROUTER_API_KEY` (see [Environment Variables](./env_vars.md)).

**Example**

```bash
./manage.py refresh_popular_search_terms
./manage.py refresh_popular_search_terms --dry-run
./manage.py refresh_popular_search_terms --queue
```

**Options**

| Options       | Format | Description                                                                                                |
|---------------|--------|------------------------------------------------------------------------------------------------------------|
| `--queue`     | bool   | Dispatch the refresh to Celery (matches the admin button and the weekly cron). Default is to run inline.   |
| `--dry-run`   | bool   | Fetch from Algolia and run the LLM filter, but roll back any DB writes. Useful for previewing the next run. Incompatible with `--queue`. |

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

## `refresh_users_github_photos`

**Purpose**: Refresh GitHub profile photos for all users who have a GitHub username. This command fetches the latest profile photo from GitHub for each user and updates their local profile image. This is useful for local dev/testing, isn't used for production where a periodic celery task is used.

**Example**

```bash
./manage.py refresh_users_github_photos
```

**Options**

| Options      | Format | Description                                                                                  |
|--------------|--------|----------------------------------------------------------------------------------------------|
| `--dry-run`  | bool   | Show which users would be updated without actually updating them. Useful for testing.        |

**Usage Examples**

Refresh photos for all users with GitHub usernames:
```bash
./manage.py refresh_users_github_photos
```

Preview which users would be updated:
```bash
./manage.py refresh_users_github_photos --dry-run
```
**Process**

- Calls the `refresh_users_github_photos()` Celery task which queues photo updates for all users with GitHub usernames
- With `--dry-run`, displays information about which users would be updated without making any changes

## `remove_unverified_users`

**Purpose**: Remove unverified users that are candidates for deletion. This command queues a Celery task that deletes user accounts with unverified email addresses that have been registered for more than 14 days (since November 21, 2025). This helps maintain database hygiene by cleaning up abandoned user registrations.

**Example**

```bash
./manage.py remove_unverified_users
```

**Options**

This command takes no options.

**Process**

- Queues a Celery task (`users.tasks.remove_unverified_users`) for execution
- The task finds users who:
  - Have claimed accounts (`claimed=True`)
  - Have unverified email addresses (`emailaddress__verified=False`)
  - Joined on or after November 21, 2025
  - Joined more than 14 days before the current date
- Deletes each matching user account
- Logs the deletion process for auditing purposes

**Note**: This command is also executed automatically via a Celery periodic task that runs daily at 2:15 AM.

## `clear_slack_activity`

**Purpose**: Delete all slack activity tracking data from the database. This command removes all records from the `SlackActivityBucket` and resets the `last_update_ts` field to July 31st 2025 (for now) for all channels. This is useful for resetting the slack activity tracking system. It should in future be reset to zero for all data.

**Example**

```bash
./manage.py clear_slack_activity --confirm
```

**Options**

| Options      | Format | Description                                                                                  |
|--------------|--------|----------------------------------------------------------------------------------------------|
| `--confirm`  | bool   | Required flag to confirm deletion. The command will not execute without this flag.           |

**Usage Examples**

Execute the deletion:
```bash
./manage.py clear_slack_activity --confirm
```

**Process**

- Deletes all `SlackActivityBucket` records (message counts per user per channel per day)
- Deletes all `ChannelUpdateGap` records (tracking of message fetch progress)
- Resets `last_update_ts` to "0" for all `Channel` records
- All operations are performed within a database transaction to ensure atomicity
- Logs the number of records affected in each table

**Warning**: This command permanently deletes all slack activity data. Use with caution.
