# Boost.org Website

## Overview

A Django based website that will power https://boost.org

---

## Local Development Setup

This project will use Python 3.11, Docker, and Docker Compose.

**NOTE**: All of these various `docker compose` commands, along with other helpful
developer utility commands, are codified in our `justfile` and can be ran with
less typing.

You will need to install `just`, by [following the documentation](https://just.systems/man/en/)

**Environment Variables**: Copy file `env.template` to `.env` and adjust values to match your local environment. See [Environment Variables](docs/env_vars.md) for more information.

```shell
$ cp env.template .env
```

**NOTE**: Double check that the exposed port assigned to the PostgreSQL
container does not clash with a database or other server you have running
locally.

Then run:

```shell
# start our services (and build them if necessary)
$ docker compose up

# to create a superuser
$ docker compose run --rm web python manage.py createsuperuser

# to create database migrations
$ docker compose run --rm web python manage.py makemigrations

# to run database migrations
$ docker compose run --rm web python manage.py migrate
```

This will create the Docker image, install dependencies, start the services defined in `docker-compose.yml`, and start the webserver.

### Cleaning up

To shut down our database and any long running services, we shut everyone down using:

```shell
$ docker compose down
```

## Running the tests

To run the tests, execute:

```shell
$ docker compose run --rm web pytest
```

or run:

```shell
$ just test
```

## Yarn and Tailwind

To install dependencies, execute:

```shell
$ yarn
```

For development purposes, in a secondary shell run the following yarn script configured in `package.json` which will build styles.css with the watcher.

```shell
$ yarn dev
```

For production, execute:

```shell
$ yarn build
```

---

## Generating Local Data

### Sample (Fake) Data

To **remove all existing data** (except for superusers) from your local project's database (which is in its own Docker volume) and generate fresh sample data **that will not sync with GitHub**, run:

```bash
./manage.py create_sample_data --all
```

For more information on the many, many options available for this command, see `create_sample_data` in [Management Commands](docs/commands.md).

### Live GitHub Libraries

To **add real Boost libraries and sync all the data from GitHub**, run:

```bash
./manage.py update_libraries
```

This command can take a long time to run (about a half hour). For more information, see `update_libraries` in [Management Commands](docs/commands.md).

---

## Deploying

TDB

## Production Environment Considerations

TDB

---

## Pre-commit Hooks

We use [pre-commit hooks](https://pre-commit.com/) to check code for style, syntax, and other issues. They help to maintain consistent code quality and style across the project, and prevent issues from being introduced into the codebase.

| Pre-commit Hook | Description |
| --------------- | ----------- |
| [Black](https://github.com/psf/black) | Formats Python code using the `black` code formatter |
| [Ruff](https://github.com/charliermarsh/ruff) | Wrapper around `flake8` and `isort`, among other linters |
| [Djhtml](https://github.com/rtts/djhtml) | Auto-formats Django templates |
| [Rustywind](https://github.com/avencera/rustywind) | Sorts and formats Tailwind CSS classes |

### Setup and Usage

| Description | Command |
| ---- | ------- |
| 1. Install the `pre-commit` package using `pip` | `pip install pre-commit` |
| 2. Install our list of pre-commit hooks locally | `pre-commit install` |
| 3. Run all hooks for changed files before commit | `pre-commit run` |
| 4. Run specific hook before commit | `pre-commit run {hook}` |
| 5. Run hooks for all files, even unchanged ones | `pre-commit run --all-files` |
| 6. Commit without running pre-commit hooks | `git commit -m "Your commit message" --no-verify` |

Example commands for running specific hooks:

| Hook | Example |
| --------------- | --------------- |
| Black | `pre-commit run black` |
| Ruff | `pre-commit run ruff` |
| Djhtml | `pre-commit run djhtml` |
| Rustywind | `pre-commit run rustywind` |
