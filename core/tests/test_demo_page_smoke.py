"""The component demo page renders the recognition dialogs it documents."""

import pytest
import waffle.testutils
from django.test import Client

from badges.models import Achievement
from users.models import User


@pytest.mark.django_db
@waffle.testutils.override_flag("v3", active=True)
def test_demo_page_renders_recognition_modals(catalogue):
    staff = User.objects.create_user(
        email="staff@example.com", password="x", is_staff=True
    )
    client = Client()
    client.force_login(staff)

    response = client.get("/v3/demo/components/")

    assert response.status_code == 200
    body = response.content.decode()
    for dialog_id in (
        "achievements-modal",
        "achievements-modal-short",
        "badges-modal",
    ):
        assert f'id="{dialog_id}"' in body, dialog_id

    # Full catalogue plus Boost Day, the shortened variant, then the two kinds
    # of badge.
    achievements = Achievement.objects.count() + 1
    assert body.count("recognition-list__row") == achievements + 3 + 2
