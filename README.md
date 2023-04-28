# Boost.org Website

## Overview

A Django based website that will power https://boost.org

## Local Development Setup

This project will use Python 3.9, Docker, and Docker Compose.

**NOTE**: All of these various docker-compose commands, along with other helpful
developer utility commands, are codified in our `justfile` and can be ran with
less typing.

Copy .env-dist to .env and adjust values to match your local environment:

```shell
$ cp env.template .env
```

Then run:

```shell
# start our services (and build them if necessary)
$ docker-compose up

# to create a superuser
$ docker-compose run --rm web python manage.py createsuperuser

# to create database migrations
$ docker-compose run --rm web python manage.py makemigrations

# to run database migrations
$ docker-compose run --rm web python manage.py migrate
```

This will create the Docker image, install dependencies, start the services defined in `docker-compose.yml`, and start the webserver.

### Cleaning up

To shut down our database and any long running services, we shut everyone down using:

```shell
$ docker-compose down
```

### Running with Celery and Redis

Forum ships with Celery and Redis support, but they are off by default. To rebuild our image with support, we need to pass the `docker-compose-with-celery.yml` config to Docker Compose via:

```shell
# start our services
$ docker-compose -f docker-compose-with-celery.yml up

# stop and unregister all of our services
$ docker-compose -f docker-compose-with-celery.yml down
```

### Markdown content handling

Clone the content repo to your local machine, at the same level as this repo: https://github.com/boostorg/website2022. Docker-compose will look for this folder and its contents on your machine, so it can copy the contents into a Docker container.

## Environment Variables

See [Environment Variables](docs/env_vars.md) for more information on environment variables.

## Running the tests

To run the tests, execute:

```shell
$ docker-compose run --rm web pytest
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
