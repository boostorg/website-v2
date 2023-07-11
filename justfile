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

bootstrap:  ## installs/updates all dependencies
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -f "{{ENV_FILE}}" ]; then
        echo "{{ENV_FILE}} created"
        cp env.template {{ENV_FILE}}
    fi

    # docker compose --file $(COMPOSE_FILE) build --force-rm

rebuild:
    docker compose rm -f celery-worker || true
    docker compose rm -f celery-beat || true
    docker compose rm -f web
    docker compose build --force-rm web
    docker compose build --force-rm celery-worker
    docker compose build --force-rm celery-beat

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
    docker compose --file $(COMPOSE_FILE) build --force-rm
    docker compose --file docker-compose.yml run --rm web python manage.py migrate --noinput

@test_pytest:
    -docker compose run --rm web pytest -s

@test:
    just test_pytest
    docker compose down

@coverage:
    docker compose run --rm web pytest --cov=. --cov-report=html
    open htmlcov/index.html

@update:  ## updates a project to run at its current version
    docker compose --file $(COMPOSE_FILE) rm --force celery
    docker compose --file $(COMPOSE_FILE) rm --force celery-beat
    docker compose --file $(COMPOSE_FILE) rm --force web
    docker compose --file $(COMPOSE_FILE) pull
    docker compose --file $(COMPOSE_FILE) build --force-rm
    docker compose --file docker-compose.yml run --rm web python manage.py migrate --noinput

@down:  ## stops a project
    docker compose down

# ----

# Compile new python dependencies
@pip-compile ARGS='':  ## rebuilds our pip requirements
    docker compose run --rm web pip-compile {{ ARGS }} ./requirements.in --output-file ./requirements.txt

# Upgrade existing Python dependencies to their latest versions
@pip-compile-upgrade:
    just pip-compile --upgrade
