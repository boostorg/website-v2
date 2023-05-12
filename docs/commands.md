# Management Commands

## `create_sample_data`

Running this command will populate the database with fake data for local development.

When run, it will create fake objects for these models:

- User
- Version
- Category
- Library
- LibraryVersion
- Authors for Libraries and Maintainers for LibraryVersions
- Issues and Pull Requests for Libraries

The data generated is fake. Any links, information that looks like it comes from GitHub, email addresses, etc. is all fake. Some of it is made to look like realistic data.

The following options can be used with the command:

- `--all`: If True, run all methods including the drop command.

If you don't want to drop all records for the above models and create a new set of fresh data, you can pass these options to clear your database or and create new records.

- `--drop`: If True, drop all records in the database.
- `--users`: If True, create fake users.
- `--versions`: If True, create fake versions.
- `--categories`: If True, create fake categories.
- `--libraries`: If True, create fake libraries and assign them categories.
- `--library_versions`: If True or if both `--libraries` and `--versions` are True, create fake library versions.
- `--authors`: If True, add fake library authors.
- `--maintainers`: If True, add fake library version maintainers.
- `--prs`: If True, add fake library pull requests.
- `--issues`: If True, add fake library issues.

### Example: Drop your database and create a new set of data

    ./manage.py create_sample_data --all

Output:

    Dropping all records...
    Dropping Non-Superusers...
    Dropping LibraryVersions...
    Dropping Versions...
    Dropping Categories...
    Dropping PullRequests...
    Dropping Issues...
    Dropping Libraries...
    Creating users...
    ...Created 100 users
    Creating versions...
    ...Created 10 versions
    ...Created 10 categories
    Creating libraries...
    ...Created 17 versions
    Assigning categories to libraries...
    ...algorithm assigned the Assertions category
    Creating library versions...
    ...algorithm (1.81.0) created
    Adding library authors...
    ...ghtkeoqjao@example.com assigned as algorithm author
    Adding library version maintainers...
    ...hpztdsynsa@example.com assigned as algorithm (1.81.0) maintainer
    Adding library pull requests...
    ...6 pull requests created for algorithm
    Adding library issues...
    ...10 issues created for algorithm


### Example: Create new pull requests and issues for existing library objects

    ./manage.py create_sample_data --prs --issues

Output:

    Adding library pull requests...
    ...9 pull requests created for algorithm
    ...7 pull requests created for asio
    Adding library issues...
    ...9 issues created for algorithm
    ...10 issues created for asio


## `generate_fake_versions`

Creates fake Version objects **only**, then creates LibraryVersion objects for each existing Library and the new Versions.

### Example:

    ./manage.py generate_fake_versions

Output:

    Version 1.30.0 created succcessfully
    ---algorithm (1.30.0) created succcessfully


## `import_versions`

Import Boost version (AKA "release") information from the Boost GitHub repo. Functions of this command:

- **Retrieves Boost tags**: It collects all the Boost tags from the main Github repo, excluding beta releases and release candidates. For each tag, it gathers the associated data. If it's a full release, the data is in the tag; otherwise, the data is in the commit.
- **Updates local database**: For each tag, it creates or updates a Version instance in the local database.
- **Options for managing versions and library versions**: The command provides options to delete existing versions and library versions, and to create new library versions for the most recent Boost version.
- Idempotent.

**Options**

Here are the options you can use:

- `--delete-versions`: Deletes all existing Version instances in the database before importing new ones.
- `--delete-library-versions`: Deletes all existing LibraryVersion instances in the database before importing new ones.
- `--create-recent-library-versions`: Creates a LibraryVersion for each active Boost library and the most recent Boost version.


### Example:

    ./manage.py import_versions

Output:

    Saved version boost-1.82.0. Created: True
    Skipping boost-1.82.0.beta1, not a full release
    Saved version boost-1.81.0. Created: True
    Skipping boost-1.81.0.beta1, not a full release
    tag_not_found
    {"message": "tag_not_found", "tag_name": "boost-1.80.0", "repo_slug": "boost", "logger": "libraries.github", "level": "info", "timestamp": "2023-05-12T22:14:08.721270Z"}
    ...
    Saved library version Math (boost-1.82.0). Created: True
    Saved library version Xpressive (boost-1.82.0). Created: True
    Saved library version Dynamic Bitset (boost-1.82.0). Created: True
    Saved library version Multi-Index (boost-1.82.0). Created: True
    ...


## `update_libraries`

Runs the library update script, which cycles through the repos listed in the Boost library and syncs their information.

Synced information:

- Most library information comes from `meta/libraries.json` stored in each Boost library repo
- Library data and metadata from GitHub is saved to our database
- Categories are updated, if needed
- Library categories are updated, if need be.
- Issues and Pull Requests are synced

**NOTE**: Can take upwards of a half hour to run. If you are trying to populate tables for local development, `create_sample_data` is a better option if the GitHub integrations aren't important.
