# Boost.org Website

## Overview

A Django based website that will power https://boost.org

## Local Development Setup

This project will use Python 3.11, Docker, and Docker Compose.

**NOTE**: All of these various `docker compose` commands, along with other helpful
developer utility commands, are codified in our `justfile` and can be ran with
less typing.

You will need to install `just`, by [following the documentation](https://just.systems/man/en/)

Copy file `env.template` to `.env` and adjust values to match your local environment:

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

## Environment Variables

See [Environment Variables](docs/env_vars.md) for more information on environment variables.

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

## Generating Fake Data

### Versions and LibraryVersions

First, make sure your `GITHUB_TOKEN` is set in you `.env` file and run `./manage.py update_libraries`. This takes a long time. See below.

Run `./manage.py generate_fake_versions`. This will create 50 active Versions, and associate Libraries to them.

The data created is realistic-looking in that each Library will contain a M2M relationship to every Version newer than the oldest one it's included in. (So if a Library's earliest LibraryVersion is 1.56.0, then there will be a LibraryVersion object for that Library for each Version since 1.56.0 was released.)

This does not add VersionFile objects to the Versions.

### Libraries, Pull Requests, and Issues

There is not currently a way to generate fake Libraries, Issues, or Pull Requests. To generate those, use your GitHub token and run `./manage.py update_libraries` locally to pull in live GitHub data. This command takes a long time to run; you might consider editing `libraries/github.py` to add counters and breaks to shorten the runtime.

## Deploying

TDB

## Production Environment Considerations

TDB


## Pre-commit

Pre-commit is configured for the following

* Black
* Ruff
* Djhtml for cleaning up django templates
* Rustywind for sorting tailwind classes

Add the hooks by executing `pre-commit install`
