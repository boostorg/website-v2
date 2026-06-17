import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class MailmanAPIError(Exception):
    pass


class MailmanClient:
    """Thin wrapper around the Mailman REST API.

    Instantiate with defaults (reads from settings) or pass explicit credentials
    to talk to a different Mailman instance:

        client = MailmanClient()
        client = MailmanClient(base_url="http://other:8001", user="u", password="p")
    """

    def __init__(self, base_url=None, api_version=None, user=None, password=None):
        url = (base_url or settings.MAILMAN_REST_API_URL).rstrip("/")
        version = api_version or settings.MAILMAN_REST_API_VERSION
        self._base = (
            f"{url}/api-proxy/{version}"
            if not settings.LOCAL_DEVELOPMENT
            else f"{url}/{version}"
        )
        self._credentials = (
            user or settings.MAILMAN_REST_API_USER,
            password or settings.MAILMAN_REST_API_PASS,
        )

    def subscribe(self, email: str, list_id: str) -> None:
        """POST /<version>/members — subscribe an email to a list.

        All pre_* flags are True because Django owns the confirmation flow. This is
        only called after the user has clicked the Django confirmation link.
        """
        url = f"{self._base}/members"
        payload = {
            "list_id": list_id,
            "subscriber": email,
            "pre_verified": True,
            "pre_confirmed": True,
            "pre_approved": True,
        }
        try:
            response = requests.post(
                url, data=payload, auth=self._credentials, timeout=10
            )
        except requests.RequestException as exc:
            raise MailmanAPIError(f"Mailman API unreachable: {exc}") from exc

        if response.status_code == 409:
            # Already a member — treat as a no-op.
            return
        if not response.ok:
            raise MailmanAPIError(
                f"subscribe failed [{response.status_code}]: {response.text}"
            )

    def is_confirmed(self, email: str, list_id: str) -> bool:
        """Return True if the email is a confirmed (active) member of the list."""
        url = f"{self._base}/lists/{list_id}/member/{email}"
        try:
            response = requests.get(url, auth=self._credentials, timeout=10)
        except requests.RequestException as exc:
            raise MailmanAPIError(f"Mailman API unreachable: {exc}") from exc

        if response.status_code == 404:
            return False
        if response.ok:
            return True
        raise MailmanAPIError(
            f"member lookup failed [{response.status_code}]: {response.text}"
        )

    def _discard_pending(self, email: str, list_id: str) -> None:
        """Discard any pending (unconfirmed) subscription request for email on list_id."""
        url = f"{self._base}/lists/{list_id}/requests"
        try:
            response = requests.get(url, auth=self._credentials, timeout=10)
        except requests.RequestException as exc:
            raise MailmanAPIError(f"Mailman API unreachable: {exc}") from exc

        if not response.ok:
            raise MailmanAPIError(
                f"pending requests lookup failed [{response.status_code}]: {response.text}"
            )

        entries = response.json().get("entries", [])
        token = next(
            (
                e["token"]
                for e in entries
                if e.get("email") == email and e.get("type") == "subscription"
            ),
            None,
        )
        if token is None:
            return

        discard_url = f"{self._base}/lists/{list_id}/requests/{token}"
        try:
            discard_response = requests.post(
                discard_url,
                data={"action": "discard"},
                auth=self._credentials,
                timeout=10,
            )
        except requests.RequestException as exc:
            raise MailmanAPIError(f"Mailman API unreachable: {exc}") from exc

        if discard_response.status_code == 404:
            return
        if not discard_response.ok:
            raise MailmanAPIError(
                f"discard pending failed [{discard_response.status_code}]"
            )

    def unsubscribe(self, email: str, list_id: str) -> None:
        """DELETE /<version>/members/<id> — remove a subscription."""
        url = f"{self._base}/lists/{list_id}/member/{email}"
        try:
            response = requests.get(url, auth=self._credentials, timeout=10)
        except requests.RequestException as exc:
            raise MailmanAPIError(f"Mailman API unreachable: {exc}") from exc

        if response.status_code == 404:
            # Not a confirmed member — discard any pending subscription request so
            # the user can subscribe again cleanly.
            self._discard_pending(email, list_id)
            return
        if not response.ok:
            raise MailmanAPIError(
                f"member lookup failed [{response.status_code}]: {response.text}"
            )

        member_id = response.json().get("member_id")
        if not member_id:
            raise MailmanAPIError("member lookup returned no member_id")

        delete_url = f"{self._base}/members/{member_id}"
        try:
            del_response = requests.delete(
                delete_url, auth=self._credentials, timeout=10
            )
        except requests.RequestException as exc:
            raise MailmanAPIError(f"Mailman API unreachable: {exc}") from exc

        if del_response.status_code == 404:
            return
        if not del_response.ok:
            raise MailmanAPIError(
                f"unsubscribe failed [{del_response.status_code}]: {del_response.text}"
            )
