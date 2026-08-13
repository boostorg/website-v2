"""Tests for the email routing predicates used by `config.settings`."""

import pytest

from config.email_routing import catch_all_conflicts_with_production, is_production


class TestIsProduction:
    @pytest.mark.parametrize(
        "deployment_environment,environment_name",
        [
            ("production", "Production Environment"),
            ("production", "Development Environment"),
            ("production", ""),
            ("", "Production Environment"),
            ("stage", "Production Environment"),
        ],
    )
    def test_either_signal_reads_as_production(
        self, deployment_environment, environment_name
    ):
        assert is_production(deployment_environment, environment_name) is True

    @pytest.mark.parametrize(
        "deployment_environment,environment_name",
        [
            ("stage", "Development Environment"),
            ("dev", "Development Environment"),
            ("", ""),
            ("", "Unknown Environment"),
        ],
    )
    def test_neither_signal_reads_as_non_production(
        self, deployment_environment, environment_name
    ):
        assert is_production(deployment_environment, environment_name) is False


class TestCatchAllConflictsWithProduction:
    @pytest.mark.parametrize(
        "deployment_environment,environment_name",
        [
            ("production", "Production Environment"),
            ("production", "Development Environment"),
            ("", "Production Environment"),
        ],
    )
    def test_catch_all_in_production_conflicts(
        self, deployment_environment, environment_name
    ):
        assert (
            catch_all_conflicts_with_production(
                True, deployment_environment, environment_name
            )
            is True
        )

    @pytest.mark.parametrize(
        "deployment_environment,environment_name",
        [
            ("stage", "Development Environment"),
            ("dev", "Development Environment"),
        ],
    )
    def test_catch_all_outside_production_is_allowed(
        self, deployment_environment, environment_name
    ):
        assert (
            catch_all_conflicts_with_production(
                True, deployment_environment, environment_name
            )
            is False
        )

    @pytest.mark.parametrize(
        "deployment_environment,environment_name",
        [
            ("production", "Production Environment"),
            ("stage", "Development Environment"),
        ],
    )
    def test_no_conflict_when_catch_all_is_disabled(
        self, deployment_environment, environment_name
    ):
        assert (
            catch_all_conflicts_with_production(
                False, deployment_environment, environment_name
            )
            is False
        )
