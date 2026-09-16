from health_check.backends import HealthCheck
from health_check.exceptions import ServiceUnavailable

from mailing_list.client import MailmanAPIError, MailmanClient


class MailmanAPIHealthCheck(HealthCheck):
    """Confirms the Mailman REST API is reachable with a read-only query.

    Not critical: Mailman being briefly unreachable shouldn't flip /health/'s
    overall status code, since the site itself still works with the mailing
    list card degraded to its normal "try again" error state.
    """

    critical_service = False

    def __repr__(self):
        return "Mailman API"

    def check_status(self):
        try:
            MailmanClient().list_lists()
        except MailmanAPIError as exc:
            self.add_error(ServiceUnavailable("Mailman API unreachable"), exc)
