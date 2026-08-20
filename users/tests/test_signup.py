import pytest
import waffle.testutils

from users.models import User

pytestmark = pytest.mark.django_db

SIGNUP_DATA = {
    "email": "signup-tester@example.com",
    "password1": "sup3r-s3cret-pw!",
    "password2": "sup3r-s3cret-pw!",
    "display_name": "Signup Tester",
    "accept_terms_of_use": "on",
}


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
