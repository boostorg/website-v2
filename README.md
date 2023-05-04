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

Pre-commit is configured for the following:

* **[Black](https://github.com/psf/black)**: Formats Python code using the `black` code formatter.
* **[Ruff](https://github.com/charliermarsh/ruff)**: Wrapper around `flake8` and `isort`, among other linters
* **[Djhtml](https://github.com/rtts/djhtml)**:  for cleaning up django templates
* **[Rustywind](https://github.com/avencera/rustywind)** for sorting tailwind classes

Add the hooks by running: 

```bash
pre-commit install
``` 

Now, the pre-commit hooks will automatically run before each commit. If any hook fails, the commit will be aborted, and you'll need to fix the issues and try committing again.

### Running pre-commit hooks locally 

Ensure you have Python and `pip` installed. 

**Install `pre-commit`**: run:

```bash
pip install pre-commit
```

**Install the hooks**: navigate to the root directory and run:

```bash
pre-commit install
``` 

To **run individual hooks, run: 

```bash
pre-commit run {hook}
```

Example: 

```bash
pre-commit run black
```

or 

```bash
pre-commit run djhtml
```

To **preview** what the pre-commit hooks would catch **in the changes you are about to commit**, run: 

```bash
pre-commit run
```

To **preview** what the pre-commit hooks would catch **across the whole project**, run: 

```bash
pre-commit run --all-files
``` 

To **skip running the pre-commit hooks** for some reason, run:

```bash
git commit -m "Your commit message" --no-verify
```

This will allow you to commit without running the hooks first. When you push your branch, you will still need to resolve issues that CI catches. 

_Note: Added this when a couple of us installed pre-commit and got the Big Angry List, so I wanted to save is a Google._ 
