"""Predicates behind the email routing decisions in `config.settings`.

Kept out of the settings module so they are importable and testable: the guard
below is the only thing stopping a values-file mistake from sending QA mail to
real recipients, and settings modules cannot be reimported under test.
"""


def is_production(deployment_environment: str, environment_name: str) -> bool:
    """Report whether this environment is production, by either available signal.

    `deployment_environment` is `X_DEPLOYMENT_ENV`, set from the chart's
    `deploymentEnvironment` anchor. `environment_name` is `ENVIRONMENT_NAME`, set
    for the admin banner. Both are set in `values-production-gke.yaml`, and
    either one alone being unset or renamed must not read as non-production.
    """
    return (
        deployment_environment == "production"
        or environment_name == "Production Environment"
    )


def catch_all_conflicts_with_production(
    catch_all_email: bool, deployment_environment: str, environment_name: str
) -> bool:
    """Report whether catch-all email is enabled somewhere it must never be."""
    return catch_all_email and is_production(deployment_environment, environment_name)
