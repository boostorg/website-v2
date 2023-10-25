# Dependency Management

## How to add a new Python dependency

1. Run `just down` to kill your running containers
1. Add the package to `requirements.in`
1. Run `just pip-compile`, which will add the dependency to `requirements.txt`
1. Run `just rebuild` to rebuild your Docker image to include the new dependencies
2. Run `docker compose up` and continue with development
