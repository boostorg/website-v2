from unittest.mock import patch

from mailing_list.client import MailmanAPIError
from mailing_list.health_checks import MailmanAPIHealthCheck


def test_mailman_health_check_ok_when_api_reachable():
    check = MailmanAPIHealthCheck()
    with patch("mailing_list.health_checks.MailmanClient") as MockClient:
        check.check_status()
    MockClient.return_value.list_lists.assert_called_once_with()
    assert check.errors == []


def test_mailman_health_check_reports_error_when_api_unreachable():
    check = MailmanAPIHealthCheck()
    with patch("mailing_list.health_checks.MailmanClient") as MockClient:
        MockClient.return_value.list_lists.side_effect = MailmanAPIError("boom")
        check.check_status()
    assert len(check.errors) == 1
    assert "unavailable" in str(check.errors[0]).lower()


def test_mailman_health_check_is_not_critical():
    """A Mailman outage should not flip /health/'s overall status code - the
    site works with the mailing list card degraded, it isn't down."""
    assert MailmanAPIHealthCheck.critical_service is False


def test_mailman_health_check_registered_with_health_check_plugins():
    from health_check.plugins import plugin_dir

    registered = [plugin_class for plugin_class, _ in plugin_dir._registry]
    assert MailmanAPIHealthCheck in registered
