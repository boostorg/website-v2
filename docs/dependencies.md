# Dependency Management

## How to add a new Python dependency

1. Run `just down` to kill your running containers
1. Add the package to `requirements.in`
1. Run `just pip-compile`, which will add the dependency to `requirements.txt`
1. Run `just rebuild` to rebuild your Docker image to include the new dependencies
2. Run `just up` and continue with development

## Upgrading dependencies

To upgrade all dependencies to their latest versions, run:

1. `just pip-compile-upgrade`.
2. Get the django version from requirements.txt and set the `DJANGO_VERSION` value in /justfile
3. Update the `--target-version` args value for django-upgrade in .pre-commit-config.yaml to match
3. In a venv with installed packages run `just run-django-upgrade` to upgrade python code.
4. `just build` to create new docker images.
5. Tear down docker containers and restart with the newly built images, then test.
