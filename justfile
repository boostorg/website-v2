set dotenv-load := false
COMPOSE_FILE := "docker-compose-with-celery.yml"
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
        cp .env-dist {{ENV_FILE}}
    fi

    # docker-compose --file $(COMPOSE_FILE) build --force-rm

@cibuild:  ## invoked by continuous integration servers to run tests
    python -m pytest
    python -m black --check .
    interrogate -c pyproject.toml .

@console:  ## opens a console
    docker-compose run --rm web bash

@server:  ## starts app
    docker-compose --file docker-compose.yml run --rm web python manage.py migrate --noinput
    docker-compose up

@setup:  ## sets up a project to be used for the first time
    docker-compose --file $(COMPOSE_FILE) build --force-rm
    docker-compose --file docker-compose.yml run --rm web python manage.py migrate --noinput

@test_interrogate:
    -docker-compose run --rm web interrogate -vv --fail-under 100 --whitelist-regex "test_.*" .

@test_pytest:
    -docker-compose run --rm web pytest -s

@test:
    just test_pytest
    just test_interrogate
    docker-compose down

@update:  ## updates a project to run at its current version
    docker-compose --file $(COMPOSE_FILE) rm --force celery
    docker-compose --file $(COMPOSE_FILE) rm --force celery-beat
    docker-compose --file $(COMPOSE_FILE) rm --force web
    docker-compose --file $(COMPOSE_FILE) pull
    docker-compose --file $(COMPOSE_FILE) build --force-rm
    docker-compose --file docker-compose.yml run --rm web python manage.py migrate --noinput

# ----

@pip-compile:  ## rebuilds our pip requirements
    docker-compose run --rm web pip-compile ./requirements.in --output-file ./requirements.txt
