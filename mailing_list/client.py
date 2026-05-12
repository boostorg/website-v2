import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class MailmanAPIError(Exception):
    pass


def _base_url() -> str:
    return settings.MAILMAN_REST_API_URL.rstrip("/") + settings.MAILMAN_REST_API_PATH


def _auth() -> tuple[str, str]:
    return (settings.MAILMAN_REST_API_USER, settings.MAILMAN_REST_API_PASS)


def subscribe(email: str, list_id: str) -> None:
    """POST /3.1/members — subscribe an email to a list.

    All pre_* flags are True because Django owns the confirmation flow. This is
    only called after the user has clicked the Django confirmation link.
    """
    url = f"{_base_url()}/members"
    payload = {
        "list_id": list_id,
        "subscriber": email,
        "pre_verified": True,
        "pre_confirmed": True,
        "pre_approved": True,
    }
    try:
        response = requests.post(url, data=payload, auth=_auth(), timeout=10)
    except requests.RequestException as exc:
        raise MailmanAPIError(f"Mailman API unreachable: {exc}") from exc

    if response.status_code == 409:
        # Already a member — treat as a no-op.
        return
    if not response.ok:
        raise MailmanAPIError(
            f"subscribe failed [{response.status_code}]: {response.text}"
        )


def is_confirmed(email: str, list_id: str) -> bool:
    """Return True if the email is a confirmed (active) member of the list."""
    url = f"{_base_url()}/lists/{list_id}/member/{email}"
    try:
        response = requests.get(url, auth=_auth(), timeout=10)
    except requests.RequestException as exc:
        raise MailmanAPIError(f"Mailman API unreachable: {exc}") from exc

    if response.status_code == 404:
        return False
    if response.ok:
        return True
    raise MailmanAPIError(
        f"member lookup failed [{response.status_code}]: {response.text}"
    )


def _discard_pending(email: str, list_id: str) -> None:
    """Discard any pending (unconfirmed) subscription request for email on list_id."""
    url = f"{_base_url()}/lists/{list_id}/requests"
    try:
        response = requests.get(url, auth=_auth(), timeout=10)
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

    discard_url = f"{_base_url()}/lists/{list_id}/requests/{token}"
    try:
        requests.post(discard_url, data={"action": "discard"}, auth=_auth(), timeout=10)
    except requests.RequestException as exc:
        raise MailmanAPIError(f"Mailman API unreachable: {exc}") from exc


def unsubscribe(email: str, list_id: str) -> None:
    """DELETE /3.1/members/<id> — remove a subscription."""
    url = f"{_base_url()}/lists/{list_id}/member/{email}"
    try:
        response = requests.get(url, auth=_auth(), timeout=10)
    except requests.RequestException as exc:
        raise MailmanAPIError(f"Mailman API unreachable: {exc}") from exc

    if response.status_code == 404:
        # Not a confirmed member — discard any pending subscription request so
        # the user can subscribe again cleanly.
        _discard_pending(email, list_id)
        return
    if not response.ok:
        raise MailmanAPIError(
            f"member lookup failed [{response.status_code}]: {response.text}"
        )

    member_id = response.json().get("member_id")
    if not member_id:
        raise MailmanAPIError("member lookup returned no member_id")

    delete_url = f"{_base_url()}/members/{member_id}"
    try:
        del_response = requests.delete(delete_url, auth=_auth(), timeout=10)
    except requests.RequestException as exc:
        raise MailmanAPIError(f"Mailman API unreachable: {exc}") from exc

    if del_response.status_code == 404:
        return
    if not del_response.ok:
        raise MailmanAPIError(
            f"unsubscribe failed [{del_response.status_code}]: {del_response.text}"
        )
