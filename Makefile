COMPOSE_FILE := docker-compose.yml

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

# ----
# Research:
# - https://www.encode.io/reports/april-2020#our-workflow-approach
# - https://github.blog/2015-06-30-scripts-to-rule-them-all/
# ----

.PHONY: bootstrap
bootstrap:  ## installs/updates all dependencies
	@docker compose --file $(COMPOSE_FILE) build --force-rm

.PHONY: cibuild
cibuild:  ## invoked by continuous integration servers to run tests
	@python -m pytest
	@python -m black --check .
	@interrogate -c pyproject.toml .

.PHONY: console
console:  ## opens a console
	@docker compose run --rm web bash

.PHONY: server
server:  ## starts app
	@docker compose --file docker-compose.yml run --rm web python manage.py migrate --noinput
	@docker compose up

.PHONY: setup
setup:  ## sets up a project to be used for the first time
	@docker compose --file $(COMPOSE_FILE) build --force-rm
	@docker compose --file docker-compose.yml run --rm web python manage.py migrate --noinput

.PHONY: test_interrogate
test_interrogate:
	@docker compose run --rm web interrogate -vv --fail-under 100 --whitelist-regex "test_.*" .

.PHONY: test_pytest
test_pytest:
	@docker compose run --rm web pytest -s

.PHONY: test
test: test_interrogate test_pytest
	@docker compose down

.PHONY: update
update:  ## updates a project to run at its current version
	@docker compose --file $(COMPOSE_FILE) rm --force celery
	@docker compose --file $(COMPOSE_FILE) rm --force celery-beat
	@docker compose --file $(COMPOSE_FILE) rm --force web
	@docker compose --file $(COMPOSE_FILE) pull
	@docker compose --file $(COMPOSE_FILE) build --force-rm
	@docker compose --file docker-compose.yml run --rm web python manage.py migrate --noinput

# ----

.PHONY: pip-compile
pip-compile:  ## rebuilds our pip requirements
	@docker compose run --rm web pip-compile ./requirements.in --output-file ./requirements.txt

.PHONY: build
build:
	docker compose pull
	DOCKER_BUILDKIT=1 docker compose build

.PHONY: createsuperuser
createsuperuser:
	docker compose run --rm web /code/manage.py createsuperuser

.PHONY: down
down:
	docker compose down

.PHONY: makemigrations
makemigrations:
	@echo "Running makemigrations..."
	docker compose run --rm web /code/manage.py makemigrations

.PHONY: migrate
migrate:
	@echo "Running migrations..."
	docker compose run --rm web /code/manage.py migrate --noinput

.PHONY: rebuild
rebuild:
	@echo "Rebuilding local docker images..."
	docker compose kill
	docker compose rm -f web
	DOCKER_BUILDKIT=1 docker compose build --force-rm web

.PHONY: shell
shell:
	docker compose run --rm web bash

.PHONY: up
up:
	docker compose up -d

# todo: update make setup to use development-tofu-init
.PHONY: development-tofu-init
development-tofu-init:
#	@command -v gh >/dev/null 2>&1 || { echo >&2 "gh is required but not installed. see: https://cli.github.com/ Aborting."; exit 1; }
	@command -v gcloud >/dev/null 2>&1 || { echo >&2 "gcloud is required but not installed. see: https://cloud.google.com/sdk/docs/install Aborting."; exit 1; }
	@command -v tofu >/dev/null 2>&1 || { echo >&2 "opentofu is required but not installed. see: https://opentofu.org/docs/intro/install/ Aborting."; exit 1; }
	@if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q '.'; then \
		gcloud auth application-default login; \
	fi
	@cd development-tofu; tofu init

.PHONY: development-tofu-plan
development-tofu-plan:
	@if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q '.'; then \
		gcloud auth application-default login; \
	fi
	@cd development-tofu; direnv allow && tofu plan

.PHONY: development-tofu-apply
development-tofu-apply:
	@if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q '.'; then \
		gcloud auth application-default login; \
	fi
	@cd development-tofu; direnv allow && tofu apply

.PHONY: development-tofu-destroy
development-tofu-destroy:
	@if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q '.'; then \
		gcloud auth application-default login; \
	fi
	@cd development-tofu; direnv allow && tofu destroy
