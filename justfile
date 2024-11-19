set dotenv-load := false
COMPOSE_FILE := "docker-compose.yml"
ENV_FILE := ".env"

@_default:
    just --list

# ----
# Research:
# - https://www.encode.io/reports/april-2020#our-workflow-approach
# - https://github.blog/2015-06-30-scripts-to-rule-them-all/
# ----

@bootstrap:  ## installs/updates all dependencies
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -f "{{ENV_FILE}}" ]; then
        echo "{{ENV_FILE}} created"
        cp env.template {{ENV_FILE}}
    fi
    docker compose --file {{COMPOSE_FILE}} build --force-rm

@rebuild:  ## rebuilds containers
    docker compose kill
    docker compose rm -f celery-worker || true
    docker compose rm -f celery-beat || true
    docker compose rm -f web
    DOCKER_BUILDKIT=1 docker compose build --force-rm web
    docker compose build --force-rm celery-worker
    docker compose build --force-rm celery-beat

@build:  ## builds containers
    docker compose pull
    DOCKER_BUILDKIT=1 docker compose build

@cibuild:  ## invoked by continuous integration servers to run tests
    python -m pytest
    python -m black --check .
    interrogate -c pyproject.toml .

alias shell := console
@console:  ## opens a console
    docker compose run --rm web bash

@server:  ## starts app
    docker compose --file docker-compose.yml run --rm web python manage.py migrate --noinput
    docker compose up

@setup:  ## sets up a project to be used for the first time
    docker compose --file {{COMPOSE_FILE}} build --force-rm
    docker compose --file docker-compose.yml run --rm web python manage.py migrate --noinput

@test_pytest:  ## runs pytest
    -docker compose run --rm web pytest -s --create-db

@test_pytest_asciidoctor:  ## runs asciidoctor tests
    -docker compose run --rm web pytest -m asciidoctor -s

@test_interrogate:  ## runs interrogate tests
    docker compose run --rm web interrogate -vv --fail-under 100 --whitelist-regex "test_.*" .

@test: test_interrogate test_pytest  ## runs all tests
    docker compose down

@coverage:  ## generates test coverage report
    docker compose run --rm web pytest --cov=. --cov-report=html
    open htmlcov/index.html

@update:  ## updates a project to run at its current version
    docker compose --file {{COMPOSE_FILE}} rm --force celery-worker
    docker compose --file {{COMPOSE_FILE}} rm --force celery-beat
    docker compose --file {{COMPOSE_FILE}} rm --force web
    docker compose --file {{COMPOSE_FILE}} pull
    docker compose --file {{COMPOSE_FILE}} build --force-rm
    docker compose --file docker-compose.yml run --rm web python manage.py migrate --noinput

@down:  ## stops a project
    docker compose down

@up:  ## starts containers in detached mode
    docker compose up -d

@makemigrations:  ## creates new database migrations
    docker compose run --rm web /code/manage.py makemigrations

@migrate:  ## applies database migrations
    docker compose run --rm web /code/manage.py migrate --noinput

@createsuperuser:  ## creates a superuser
    docker compose run --rm web /code/manage.py createsuperuser

@shell_plus:  ## open interactive django shell
    docker compose run --rm web /code/manage.py shell_plus

# Development infrastructure commands
@development-tofu-init:  ## initializes development infrastructure
    @command -v gcloud >/dev/null 2>&1 || { echo >&2 "gcloud is required but not installed. see: https://cloud.google.com/sdk/docs/install Aborting."; exit 1; }
    @command -v tofu >/dev/null 2>&1 || { echo >&2 "opentofu is required but not installed. see: https://opentofu.org/docs/intro/install/ Aborting."; exit 1; }
    @if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q '.'; then \
        gcloud auth application-default login; \
    fi
    @cd development-tofu; tofu init

@development-tofu-plan:  ## plans development infrastructure changes
    @if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q '.'; then \
        gcloud auth application-default login; \
    fi
    @cd development-tofu; direnv allow && tofu plan

@development-tofu-apply:  ## applies development infrastructure changes
    @if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q '.'; then \
        gcloud auth application-default login; \
    fi
    @cd development-tofu; direnv allow && tofu apply

@development-tofu-destroy:  ## destroys development infrastructure
    @if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q '.'; then \
        gcloud auth application-default login; \
    fi
    @cd development-tofu; direnv allow && tofu destroy

# Dependency management
@pip-compile ARGS='':  ## rebuilds our pip requirements
    docker compose run --rm web uv pip compile {{ ARGS }} ./requirements.in --no-strip-extras --output-file ./requirements.txt

@pip-compile-upgrade:  ## Upgrade existing Python dependencies to their latest versions
    just pip-compile --upgrade
