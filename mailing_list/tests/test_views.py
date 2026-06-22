import pytest
from django.core import signing
from django.urls import reverse
from model_bakery import baker
from unittest.mock import patch

from mailing_list.constants import MAILMAN_LISTS
from mailing_list.models import SubscriptionStatus, UserMailingListSubscription
from mailing_list.views import _CONFIRM_SALT

LIST_ID = MAILMAN_LISTS[0]
EMAIL = "subscriber@example.com"


@pytest.fixture
def user(db):
    u = baker.make("users.User", email="user@example.com")
    u.set_password("password")
    u.save()
    return u


@pytest.fixture
def other_user(db):
    u = baker.make("users.User", email="other@example.com")
    u.set_password("password")
    u.save()
    return u


@pytest.fixture(autouse=True)
def locmem_cache(settings):
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    yield
    from django.core.cache import cache

    cache.clear()


def _make_token(email, list_ids, user_id=None):
    payload = {"email": email, "list_ids": list_ids}
    if user_id is not None:
        payload["user_id"] = user_id
    return signing.dumps(payload, salt=_CONFIRM_SALT)


# ---------------------------------------------------------------------------
# QuickSubscribeView — anonymous flow
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_anon_quick_subscribe_sends_email_and_returns_pending(client):
    """POST /mailing-list/quick-subscribe/ — anon: sends confirmation email, returns pending card."""
    url = reverse("mailing-list-quick-subscribe")
    with patch("mailing_list.views._send_confirmation_email") as mock_send, patch(
        "mailing_list.views.MailmanClient"
    ) as MockClient:
        MockClient.return_value.is_confirmed.return_value = False
        response = client.post(
            url,
            {"email": EMAIL, "list_id": LIST_ID},
            HTTP_HX_REQUEST="true",
        )
    assert response.status_code == 200
    mock_send.assert_called_once()
    assert b"pending" in response.content.lower() or b"sent" in response.content.lower()


@pytest.mark.django_db
def test_anon_quick_subscribe_already_subscribed_returns_error(client):
    """POST /mailing-list/quick-subscribe/ — anon: email already confirmed in Mailman returns error."""
    url = reverse("mailing-list-quick-subscribe")
    with patch("mailing_list.views.MailmanClient") as MockClient:
        MockClient.return_value.is_confirmed.return_value = True
        response = client.post(
            url,
            {"email": EMAIL, "list_id": LIST_ID},
            HTTP_HX_REQUEST="true",
        )
    assert response.status_code == 200
    assert b"already subscribed" in response.content.lower()


@pytest.mark.django_db
def test_anon_quick_subscribe_rate_limited(client):
    """POST /mailing-list/quick-subscribe/ — anon: 6th request within the window is rate-limited."""
    url = reverse("mailing-list-quick-subscribe")
    with patch("mailing_list.views._send_confirmation_email"), patch(
        "mailing_list.views.MailmanClient"
    ) as MockClient:
        MockClient.return_value.is_confirmed.return_value = False
        for _ in range(5):
            client.post(
                url, {"email": EMAIL, "list_id": LIST_ID}, HTTP_HX_REQUEST="true"
            )
        response = client.post(
            url,
            {"email": EMAIL, "list_id": LIST_ID},
            HTTP_HX_REQUEST="true",
        )
    assert response.status_code == 200
    assert b"too many" in response.content.lower()


@pytest.mark.django_db
def test_auth_quick_subscribe_rate_limited(client, user):
    """POST /mailing-list/quick-subscribe/ — auth: 6th request within the window is rate-limited."""
    client.force_login(user)
    url = reverse("mailing-list-quick-subscribe")
    with patch("mailing_list.views._send_confirmation_email"), patch(
        "mailing_list.views.MailmanClient"
    ) as MockClient:
        MockClient.return_value.is_confirmed.return_value = False
        for _ in range(5):
            client.post(
                url, {"email": EMAIL, "list_id": LIST_ID}, HTTP_HX_REQUEST="true"
            )
        response = client.post(
            url,
            {"email": EMAIL, "list_id": LIST_ID},
            HTTP_HX_REQUEST="true",
        )
    assert response.status_code == 200
    assert b"too many" in response.content.lower()


@pytest.mark.django_db
def test_staff_quick_subscribe_bypasses_rate_limit(client, db):
    """POST /mailing-list/quick-subscribe/ — staff: never rate-limited regardless of request count."""
    staff = baker.make("users.User", is_staff=True)
    client.force_login(staff)
    url = reverse("mailing-list-quick-subscribe")
    with patch("mailing_list.views._send_confirmation_email"), patch(
        "mailing_list.views.MailmanClient"
    ) as MockClient:
        MockClient.return_value.is_confirmed.return_value = False
        for _ in range(10):
            response = client.post(
                url, {"email": EMAIL, "list_id": LIST_ID}, HTTP_HX_REQUEST="true"
            )
    assert b"too many" not in response.content.lower()


# ---------------------------------------------------------------------------
# QuickSubscribeView — authenticated flow
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_auth_quick_subscribe_creates_pending_record(client, user):
    """POST /mailing-list/quick-subscribe/ — auth: creates a PENDING subscription record."""
    client.force_login(user)
    url = reverse("mailing-list-quick-subscribe")
    with patch("mailing_list.views._send_confirmation_email"):
        response = client.post(
            url,
            {"email": EMAIL, "list_id": LIST_ID},
            HTTP_HX_REQUEST="true",
        )
    assert response.status_code == 200
    sub = UserMailingListSubscription.objects.get(user=user, list_id=LIST_ID)
    assert sub.status == SubscriptionStatus.PENDING
    assert sub.email == EMAIL


@pytest.mark.django_db
def test_auth_quick_subscribe_already_pending_returns_pending_card(client, user):
    """POST /mailing-list/quick-subscribe/ — auth: existing PENDING record returns pending card without re-sending email."""
    baker.make(
        UserMailingListSubscription,
        user=user,
        list_id=LIST_ID,
        email=EMAIL,
        status=SubscriptionStatus.PENDING,
    )
    client.force_login(user)
    url = reverse("mailing-list-quick-subscribe")
    with patch("mailing_list.views._send_confirmation_email") as mock_send:
        response = client.post(
            url,
            {"email": EMAIL, "list_id": LIST_ID},
            HTTP_HX_REQUEST="true",
        )
    assert response.status_code == 200
    mock_send.assert_not_called()
    assert b"pending" in response.content.lower()


@pytest.mark.django_db
def test_auth_quick_subscribe_already_active_returns_success_card(client, user):
    """POST /mailing-list/quick-subscribe/ — auth: existing ACTIVE record returns success card without re-sending email."""
    baker.make(
        UserMailingListSubscription,
        user=user,
        list_id=LIST_ID,
        email=EMAIL,
        status=SubscriptionStatus.ACTIVE,
    )
    client.force_login(user)
    url = reverse("mailing-list-quick-subscribe")
    with patch("mailing_list.views._send_confirmation_email") as mock_send:
        response = client.post(
            url,
            {"email": EMAIL, "list_id": LIST_ID},
            HTTP_HX_REQUEST="true",
        )
    assert response.status_code == 200
    mock_send.assert_not_called()


@pytest.mark.django_db
def test_auth_quick_subscribe_duplicate_email_returns_error(client, user, other_user):
    """POST /mailing-list/quick-subscribe/ — auth: email already registered by another account returns error."""
    baker.make(
        UserMailingListSubscription,
        user=other_user,
        list_id=LIST_ID,
        email=EMAIL,
        status=SubscriptionStatus.ACTIVE,
    )
    client.force_login(user)
    url = reverse("mailing-list-quick-subscribe")
    with patch("mailing_list.views._send_confirmation_email"):
        response = client.post(
            url,
            {"email": EMAIL, "list_id": LIST_ID},
            HTTP_HX_REQUEST="true",
        )
    assert response.status_code == 200
    assert b"already registered" in response.content.lower()
    assert not UserMailingListSubscription.objects.filter(user=user).exists()


# ---------------------------------------------------------------------------
# ConfirmSubscriptionView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_confirm_valid_token_subscribes_and_shows_success(client, user):
    """GET /mailing-list/confirm/<token>/ — valid token: calls Mailman, marks subscription ACTIVE."""
    baker.make(
        UserMailingListSubscription,
        user=user,
        list_id=LIST_ID,
        email=EMAIL,
        status=SubscriptionStatus.PENDING,
    )
    token = _make_token(EMAIL, [LIST_ID], user_id=user.pk)
    url = reverse("mailing-list-confirm", args=[token])
    with patch("mailing_list.views.MailmanClient"):
        response = client.get(url)
    assert response.status_code == 200
    assert (
        UserMailingListSubscription.objects.get(user=user, list_id=LIST_ID).status
        == SubscriptionStatus.ACTIVE
    )


@pytest.mark.django_db
def test_confirm_bad_token_shows_invalid_page(client):
    """GET /mailing-list/confirm/<token>/ — bad signature: returns 400 with invalid/expired message."""
    url = reverse("mailing-list-confirm", args=["not-a-real-token"])
    response = client.get(url)
    assert response.status_code == 400
    assert (
        b"invalid" in response.content.lower() or b"expired" in response.content.lower()
    )


@pytest.mark.django_db
def test_confirm_unknown_user_shows_invalid_page_with_expiry_label(client):
    """GET /mailing-list/confirm/<token>/ — user_id not found: returns 400 with expiry duration in body."""
    token = _make_token(EMAIL, [LIST_ID], user_id=99999999)
    url = reverse("mailing-list-confirm", args=[token])
    response = client.get(url)
    assert response.status_code == 400
    assert (
        b"invalid" in response.content.lower() or b"expired" in response.content.lower()
    )
    assert b"7" in response.content


@pytest.mark.django_db
def test_confirm_anonymous_token_subscribes_without_db_record(client):
    """GET /mailing-list/confirm/<token>/ — anonymous token: calls Mailman subscribe without touching DB."""
    token = _make_token(EMAIL, [LIST_ID])
    url = reverse("mailing-list-confirm", args=[token])
    with patch("mailing_list.views.MailmanClient") as MockClient:
        response = client.get(url)
    assert response.status_code == 200
    MockClient.return_value.subscribe.assert_called_once_with(EMAIL, LIST_ID)
