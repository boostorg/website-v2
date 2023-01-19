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

### `GITHUB_TOKEN`

[Generate a new personal access token](https://github.com/settings/tokens) and replace the value for `GITHUB_TOKEN` in your `.env` file in order to connect to certain parts of the GitHub API. 

### `ENVIRONMENT_NAME`

Optional. Set a name for local development that will display in a banner in the Django Admin. 

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

## Deploying

TDB

## Production Environment Considerations

TDB
