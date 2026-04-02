set dotenv-load := false
COMPOSE_FILE := "docker-compose.yml"
ENV_FILE := ".env"
DJANGO_VERSION := "5.2"

@_default:
    just --list

# ----
# Research:
# - https://www.encode.io/reports/april-2020#our-workflow-approach
# - https://github.blog/2015-06-30-scripts-to-rule-them-all/
# ----

@bootstrap-nix:  ## installs/updates all dependencies
    command -v direnv >/dev/null 2>&1 || { echo >&2 "Direnv is required but not installed. see: https://direnv.net/docs/installation.html - Aborting."; exit 1; }
    command -v nix >/dev/null 2>&1 || { echo >&2 "Nix is required but not installed. see: https://nixos.org/download.html - Aborting."; exit 1; }
    command -v just >/dev/null 2>&1 || { echo >&2 "Just is required but not installed. see: https://just.systems/man/en/packages.html - Aborting."; exit 1; }
    command -v docker >/dev/null 2>&1 || { echo >&2 "Docker is required but not installed. see: docs for links - Aborting."; exit 1; }

    shell_name=$(basename "$SHELL") && \
    echo $shell_name && \
    if [ "$shell_name" = "zsh" ] && command -v zsh >/dev/null; then \
      zsh -i -c 'echo ${precmd_functions} | grep -q _direnv_hook' || { echo "❌ direnv hook is NOT installed in Zsh"; exit 1; }; \
    elif ([ "$shell_name" = "pwsh" ] || [ "$shell_name" = "powershell" ]) && command -v "$shell_name" >/dev/null; then \
      "$shell_name" -NoProfile -Command '$function:prompt.ToString() | grep -q direnv' || { echo "❌ direnv hook is NOT installed in PowerShell"; exit 1; }; \
    else \
      echo "ℹ️ Unsupported shell for checking direnv hook: $shell_name. Ensure you have the direnv shell hook eval set up correctly if there are problems."; \
    fi

    if [ ! -d $HOME/.config/direnv/direnv.toml ]; then \
        mkdir -p $HOME/.config/direnv; \
        printf "[global]\nhide_env_diff = true\nload_dotenv = true\n" > $HOME/.config/direnv/direnv.toml; \
    fi
    if [ ! -d $HOME/.config/nix ]; then \
        mkdir -p $HOME/.config/nix; \
        printf "experimental-features = nix-command flakes\n" > $HOME/.config/nix/nix.conf; \
    fi
    # check if the docker group exists, create if not
    if [ ! $(getent group docker) ]; then \
        echo "ℹ️ Adding docker group..."; \
        sudo groupadd docker; \
    fi

    # check if user is in docker group, add if not
    if [ $(id -Gn | grep -c docker) -eq 0 ]; then \
        echo "ℹ️ Adding docker group"; \
        sudo usermod -aG docker $USER; \
        echo "ℹ️ Added docker user. Please close the shell and open a new one."; \
    fi
    echo "Bootstrapping complete, update your .env and run 'just setup'"
    echo "If you have issues with docker permissions running just setup try restarting your machine."

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
    docker compose build

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
    npm install
    npm run build

@test_pytest *args:  ## runs pytest (optional: test file/pattern, -v for verbose, -vv for very verbose)
    -docker compose run --rm -e DEBUG_TOOLBAR="False" web pytest -s --create-db {{ args }}

@test_pytest_lf:  ## runs last failed pytest tests
    -docker compose run --rm -e DEBUG_TOOLBAR="False" web pytest -s --create-db --lf

@test_pytest_asciidoctor:  ## runs asciidoctor tests
    -docker compose run --rm -e DEBUG_TOOLBAR="False" web pytest -m asciidoctor -s --create-db

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
    echo "Adjusting migration file permissions (may require password)..."
    sudo chown -R $(id -u):$(id -g) */migrations/
    sudo chmod -R 664 */migrations/*.py
    echo "✓ Migration files ownership and permissions updated"


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

@run-django-upgrade:
    [ -n "${VIRTUAL_ENV-}" ] || { echo "❌ Activate your venv first."; exit 1; }
    -git ls-files -z -- '*.py' | xargs -0r django-upgrade --target {{DJANGO_VERSION}}

# Dependency management
@pip-compile ARGS='':  ## rebuilds our pip requirements
    docker compose run --rm web uv pip compile {{ ARGS }} ./requirements.in --no-strip-extras --output-file ./requirements.txt
    docker compose run --rm web uv pip compile {{ ARGS }} ./requirements-dev.in --no-strip-extras --output-file ./requirements-dev.txt

@pip-compile-upgrade:  ## Upgrade existing Python dependencies to their latest versions
    just pip-compile --upgrade

@load_production_data:  ## downloads and loads the latest production database dump
    bash scripts/load_production_data.sh

@dump_database:  ## dumps the current database to a .dump file in the project root
    #!/usr/bin/env bash
    DUMP_FILENAME="database_dump_$(date +"%Y-%m-%d-%H-%M-%S").dump"
    echo "Dumping database to ${DUMP_FILENAME}..."
    docker compose exec -T db pg_dump -U "$(grep PGDATABASE .env | cut -d= -f2)" -d "$(grep PGUSER .env | cut -d= -f2)" -F c -f "/tmp/${DUMP_FILENAME}"
    docker compose cp "db:/tmp/${DUMP_FILENAME}" "./${DUMP_FILENAME}"
    echo "Database dumped successfully to ${DUMP_FILENAME}"

@manage +args:
    docker compose run --rm web python manage.py {{ args }}
