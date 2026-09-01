import pytest
import waffle.testutils
from allauth.account.models import EmailConfirmationHMAC
from django.contrib.sites.models import Site
from django.core import mail
from django.urls import reverse
from model_bakery import baker

from users.forms import (
    DISPLAY_NAME_MAX_LENGTH,
    CustomSignUpForm,
    V3UserProfileForm,
)

from users.models import User

pytestmark = pytest.mark.django_db

SIGNUP_DATA = {
    "email": "signup-tester@example.com",
    "password1": "sup3r-s3cret-pw!",
    "password2": "sup3r-s3cret-pw!",
    "display_name": "Signup Tester",
    "accept_terms_of_use": "on",
}


@pytest.fixture(autouse=True)
def _disable_account_rate_limits(settings):
    """Avoid 429s from allauth's per-email rate limit across test runs."""
    settings.ACCOUNT_RATE_LIMITS = False


@waffle.testutils.override_flag("v3", active=True)
def test_signup_saves_the_username_as_display_name(tp):
    """The signup page's Username box has to reach display_name. allauth deletes
    a form field literally named `username` when the user model has none, which
    is why the field is called display_name."""
    tp.post("account_signup", data=SIGNUP_DATA)

    user = User.objects.get(email=SIGNUP_DATA["email"])
    assert user.display_name == "Signup Tester"


@waffle.testutils.override_flag("v3", active=True)
def test_signup_mints_a_routing_key_from_the_username(tp):
    """The key is minted when the row is created, so the name has to be set
    before that first save or the user is stuck with a placeholder URL."""
    tp.post("account_signup", data=SIGNUP_DATA)

    user = User.objects.get(email=SIGNUP_DATA["email"])
    key = user.profile_routing_keys.get()
    assert key.routing_key.startswith("signup-tester-")
    assert user.get_absolute_url() == f"/users/{key.routing_key}/"


def signup_data(**overrides):
    return {**SIGNUP_DATA, **overrides}


@waffle.testutils.override_flag("v3", active=True)
def test_signup_rejects_a_name_longer_than_the_shared_cap(tp):
    """Signup used to allow 255 characters while the edit form caps at 80, so a
    long name could be saved and then lock its owner out of Account details."""
    response = tp.post(
        "account_signup",
        data=signup_data(display_name="x" * (DISPLAY_NAME_MAX_LENGTH + 1)),
    )
    assert "display_name" in response.context["form"].errors
    assert not User.objects.filter(email=SIGNUP_DATA["email"]).exists()


@waffle.testutils.override_flag("v3", active=True)
def test_signup_rejects_a_name_another_real_account_holds(tp):
    baker.make("users.User", display_name="Taken Name", image=None, claimed=True)

    response = tp.post("account_signup", data=signup_data(display_name="taken name"))

    assert "display_name" in response.context["form"].errors
    assert not User.objects.filter(email=SIGNUP_DATA["email"]).exists()


@waffle.testutils.override_flag("v3", active=True)
def test_signup_allows_a_name_only_an_unclaimed_stub_holds(tp):
    """The importer mints unclaimed stubs carrying real names; those must not
    block someone signing up under the same name."""
    baker.make(
        "users.User",
        email="stub@example.com",
        display_name="Beman Dawes",
        image=None,
        claimed=False,
    )

    tp.post("account_signup", data=signup_data(display_name="Beman Dawes"))

    assert User.objects.get(email=SIGNUP_DATA["email"]).display_name == "Beman Dawes"


@waffle.testutils.override_flag("v3", active=True)
def test_signup_allows_a_name_only_a_deactivated_account_holds(tp):
    baker.make(
        "users.User",
        email="gone@example.com",
        display_name="Gone Person",
        image=None,
        claimed=True,
        is_active=False,
    )

    tp.post("account_signup", data=signup_data(display_name="Gone Person"))

    assert User.objects.get(email=SIGNUP_DATA["email"]).display_name == "Gone Person"


def test_both_forms_share_one_length_cap():
    """The two forms disagreeing is the bug; pin them to the same constant."""
    assert (
        CustomSignUpForm.base_fields["display_name"].max_length
        == V3UserProfileForm.base_fields["username"].max_length
        == DISPLAY_NAME_MAX_LENGTH
    )


@waffle.testutils.override_flag("v3", active=True)
def test_a_name_accepted_at_signup_can_be_saved_on_the_edit_form(tp):
    """The reported trap: signup accepted names the details section then refused,
    leaving Country and the login-method toggle unsaveable."""
    tp.post("account_signup", data=SIGNUP_DATA)
    user = User.objects.get(email=SIGNUP_DATA["email"])

    # force_login rather than tp.login: this account has the signup password,
    # not the fixture one, and email verification may gate a real login.
    tp.client.force_login(user)
    response = tp.post(
        f"{tp.reverse('profile-account')}?edit=true",
        data={
            "v3_update_details": "true",
            "username": user.display_name,
            "country": "US",
        },
    )
    assert response.status_code == 302

    user.refresh_from_db()
    assert str(user.country) == "US"


@waffle.testutils.override_flag("v3", active=True)
def test_signup_sends_the_branded_confirmation_email(tp):
    """Signing up has to send the V3 confirmation template, not allauth's
    default one, with a link the recipient can actually click."""
    tp.post("account_signup", data=SIGNUP_DATA)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    site_name = Site.objects.get_current().name
    assert msg.subject == f"[{site_name}] Confirm your email"
    assert msg.recipients() == [SIGNUP_DATA["email"]]

    html_body = next(
        alt.content for alt in msg.alternatives if alt.mimetype == "text/html"
    )
    assert "Welcome to Boost" in html_body
    assert f"Hi {SIGNUP_DATA['display_name']}," in html_body
    user = User.objects.get(email=SIGNUP_DATA["email"])
    confirmation = EmailConfirmationHMAC(user.emailaddress_set.get())
    activate_path = reverse("account_confirm_email", args=[confirmation.key]).rsplit(
        "/", 2
    )[0]
    assert activate_path in msg.body
    assert activate_path in html_body
