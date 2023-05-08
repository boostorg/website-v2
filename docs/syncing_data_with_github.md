# Syncing Data about Boost Libraries with GitHub

## About

The data in this database generally originates from somewhere in the Boost GitHub ecosystem. 

This page will explain to Django developers how data about Libraries is synced from GitHub to our database. 

- Most code is in `libraries/github.py` and `libraries/tasks.py`
- Once a month, the task `libraries/tasks/update_libraries()` runs.
- It cycles through all Boost libraries and updates data
- **It only handles the most recent version of Boost** and does not handle older versions yet.
- There are methods to download issues and PRs, but **the methods to download issues and PRs are not called**.

## Tasks or Questions

- [ ]  A new GitHub API needs to be generated through the CPPAlliance GitHub organization, and be added as a kube secret
- [ ]  `self.skip_modules`: This exists in both `GitHubAPIClient` and `LibraryUpdater` but it should probably only exist in `LibraryUpdater`, to keep `GitHubAPIClient` less tightly coupled to specific repos
- [ ]  If we only want aggregate data for issues and PRs, do we need to save the data from them in models, or can we just save the aggregate data somewhere?

## Glossary

To make the code more readable to the Boost team, who will ultimately maintain the project, we tried to replicate their terminology as much as possible. 

- Library: Boost “Libraries” correspond to GitHub repositories
- `.gitmodules`: The file in the main Boost project repo that contains the information on all the repos that are considered Boost libraries
- module and submodule: Other words for library that correspond more specifically to GitHub data

---

## How it Works

### `LibraryUpdater`

_This is not a code walkthrough, but is a general overview of the objects and data that this class retrieves._

- The Celery task `libraries/tasks.py/update_libraries` runs `LibraryUpdater.update_libraries()`
- This class uses the `GitHubAPIClient` class to call the GitHub API
- It retrieves the list of libraries to update from the `.gitmodules` file in the [main Boost repo](https://github.com/boostorg/boost): [https://github.com/boostorg/boost/blob/master/.gitmodules](https://github.com/boostorg/boost/blob/master/.gitmodules)
- From that list, it makes sure to exclude any libraries in `self.skip_modules`. The modules in `self.skipped_submodules` are not imported into the database.
- For each remaining library:
    - It uses the information from the `.gitmodules` file to call the GitHub API for that specific library
    - It downloads the `meta/libraries.json` file for that library and parses that data
    - It uses the parsed data to add or update the Library record in our database for that GitHub repo
    - It adds the library to the most recent Version object to create a LibraryVersion record, if needed
    - The library categories are updated
    - The maintainers are updated and stub Users are added for them if needed.
    - The authors are updated and stub Users are added for them if needed (updated second because maintainers are more likely to have email addresses, so matching is easier).

## `GithubAPIClient`

- This class controls the requests to and responses from the GitHub API. Mostly a wrapper around `GhApi` that allows us to set some default values to make calling the methods easier, and allows us to retrieve some data that is very specific to the Boost repos
- Requires the environment variable `GITHUB_TOKEN` to be set
- Contains methods to retrieve the `.gitmodules` file, retrieve the `.libraries.json` file, general repo data, repo issues, repo PRs, and the git tree.

## `GithubDataParser`

- Contains methods to parse the data we retrieve from GitHub into more useful formats
- Contains methods to parse the `.gitmodules` file and the `libraries.json` file, and to extract the author and maintainer names and email addresses, if present.

**Attributes**

| owner | GitHub repo owner | boostorg |
| --- | --- | --- |
| ref | GitHub branch or tag to use on that repo | heads/master |
| repo_slug | GitHub repo slug  | default |

- `self.skip_modules`: This is the list of modules/libraries from `.gitmodules` that we do not download

---

## GitHub Data

- Each Boost Library has a GitHub repo.
- Most of the time, one library has one repo. Other times, one GitHub repo is shared among multiple libraries (the “Algorithm” library is an example).
- The most important file for each Boost library is `meta/libraries.json`

### `.gitmodules`

This is the most important file in the main Boost repository. It contains the GitHub information for all Libraries included in that tagged Boost version, and is what we use to identify which Libraries to download into our database. 

- `submodule`: Corresponds to the `key` in `libraries.json`
- Contains information for the top-level Library, but not other sub-libraries stored in the same repo
- `path`: the path to navigate to the Library repo from the main Boost repo
- `url`: the URL for the `.git` repo for the library, in relative terms (`../system.git`)
- `fetchRecurseSubmodules`: We don’t use this field
- `branch`: We don’t use this field

<img width="1381" alt="Screenshot 2023-05-08 at 12 32 32 PM" src="https://user-images.githubusercontent.com/2286304/236922229-af2a62e6-d91c-496d-b785-6c05e0a6c393.png">

### `libraries.json`

This is the most important file in the GitHub repo for a library. It is where we retrieve all the metadata about the Library. It is the source of truth. 

- `key`: The GitHub slug, and the slug we use for our Library object
    - When the repo hosts a single Library, the `key` corresponds to the `submodule` in the main Boost repo’s `libraries.json` file. Example: `"key": "asio"`
    - When the repo hosts multiple libraries, the **first** `key` corresponds to the `submodule`. Example: `"key": "algorithm"`. Then, the **following** keys in `libraries.json` will be prefixed with the original `key` before adding their own slug. Example: `"key": "algorithm/minimax"`
- `name`: What we save as the Library name
- `authors`: A list of names of original authors of the Library’s documentation.
    - Data is very unlikely to change
    - Data generally does not contain emails
    - Stub users are creates for authors with fake email addresses and users will be able to claim those accounts.
- `description`: What we save as the `Library` description
- `category`: A list of category names. We use this to attach Categories to the Libraries.
- `maintainers`: A list of names and emails of current maintainers of this Library
    - Data may change between versions
    - Data generally contains emails
    - Stub users are created for all maintainers. We use fake email addresses if an email address is not present
    - We try to be smart — if the same name shows up as an author and a maintainer, we won’t create two fake records. But it’s imperfect.
- `cxxstd`: C++ version in which this Library was added

Example with a single library: 

<img width="1392" alt="Screenshot 2023-05-08 at 12 25 59 PM" src="https://user-images.githubusercontent.com/2286304/236922369-398aa9bf-060e-4e6e-9a37-20a68fb1d1d6.png">

Example with multiple libraries: 

<img width="1369" alt="Screenshot 2023-05-08 at 12 25 30 PM" src="https://user-images.githubusercontent.com/2286304/236922503-4e633575-9f6b-47af-b6e1-05be8be2c4e4.png">

## Maintenance Notes

### How to change the skipped libraries

- To **add a new skipped submodule**: add the name of the submodule to the list `self.skipped_modules` and make a PR. This will not remove the library from the database, but it will stop refreshing data for that library.
- To **remove a submodule that is currently being skipped**: remove the name of the submodule from `self.skipped_modules` and make a PR. The library will be added to the database the next time the update runs.

### How to delete Libraries

- Via the Admin. The Library update process does not delete any records. 

### How to add new Categories

- They will be **automatically added** as part of the download process as soon as they are added to a library's `libraries.json` file. 

### How to remove authors or maintainers 

- Via the Admin. 
- But if they are not also removed from the `libraries.json` file for the affected library, then they will be added back the next time the job runs. 
