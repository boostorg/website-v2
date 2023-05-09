import pytest
from django.contrib.auth import get_user_model
from users.forms import ClaimAccountForm


User = get_user_model()


@pytest.mark.django_db
def test_claim_account_form_valid():
    """Ensure that the form is valid when passwords match."""
    form_data = {
        "email": "test@example.com",
        "password1": "test123",
        "password2": "test123",
    }
    form = ClaimAccountForm(data=form_data)
    assert form.is_valid() is True

    # Save the form to create a new user
    user = form.save()
    assert User.objects.filter(email="test@example.com").exists() is True


@pytest.mark.django_db
def test_claim_account_form_invalid():
    """Ensure that the form is invalid when passwords don't match."""
    form_data = {
        "email": "test@example.com",
        "password1": "test123",
        "password2": "differentpassword",
    }
    form = ClaimAccountForm(data=form_data)

    assert form.is_valid() is False
    assert "password2" in form.errors

    # Verify that no user is created
    assert User.objects.filter(email="test@example.com").exists() is False
