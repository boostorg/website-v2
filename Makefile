COMPOSE_FILE := docker-compose-with-celery.yml

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
	@docker-compose --file $(COMPOSE_FILE) build --force-rm

.PHONY: cibuild
cibuild:  ## invoked by continuous integration servers to run tests
	@python -m pytest
	@python -m black --check .
	@interrogate -c pyproject.toml .

.PHONY: console
console:  ## opens a console
	@docker-compose run --rm web bash

.PHONY: server
server:  ## starts app
	@docker-compose --file docker-compose.yml run --rm web python manage.py migrate --noinput
	@docker-compose up

.PHONY: setup
setup:  ## sets up a project to be used for the first time
	@docker-compose --file $(COMPOSE_FILE) build --force-rm
	@docker-compose --file docker-compose.yml run --rm web python manage.py migrate --noinput

.PHONY: test_interrogate
test_interrogate:
	@docker-compose run --rm web interrogate -vv --fail-under 100 --whitelist-regex "test_.*" .

.PHONY: test_pytest
test_pytest:
	@docker-compose run --rm web pytest -s

.PHONY: test
test: test_interrogate test_pytest
	@docker-compose down

.PHONY: update
update:  ## updates a project to run at its current version
	@docker-compose --file $(COMPOSE_FILE) rm --force celery
	@docker-compose --file $(COMPOSE_FILE) rm --force celery-beat
	@docker-compose --file $(COMPOSE_FILE) rm --force web
	@docker-compose --file $(COMPOSE_FILE) pull
	@docker-compose --file $(COMPOSE_FILE) build --force-rm
	@docker-compose --file docker-compose.yml run --rm web python manage.py migrate --noinput

# ----

.PHONY: pip-compile
pip-compile:  ## rebuilds our pip requirements
	@docker-compose run --rm web pip-compile ./requirements.in --output-file ./requirements.txt
