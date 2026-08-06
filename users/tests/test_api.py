import pytest

from django.urls import reverse


def test_user_api_read_requires_authentication(user, tp):
    """Neither list nor detail is readable by an anonymous caller."""
    tp.response_403(tp.client.get(reverse("users-list")))
    tp.response_403(tp.client.get(reverse("users-detail", kwargs={"pk": user.pk})))


def test_user_api_serializer_switches_on_staff(user, staff_user, tp):
    """Non-staff callers get UserSerializer, which exposes only the public
    identity; staff get the full record. This switch is what kept the loose
    PATCH check from being exploitable, so it's worth pinning."""
    with tp.login(user):
        as_member = tp.client.get(reverse("users-detail", kwargs={"pk": staff_user.pk}))
    tp.response_200(as_member)
    assert set(as_member.json()) == {"id", "display_name"}

    with tp.login(staff_user):
        as_staff = tp.client.get(reverse("users-detail", kwargs={"pk": user.pk}))
    tp.response_200(as_staff)
    assert {"email", "date_joined", "is_staff"} <= set(as_staff.json())


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_user_api_detail_write_rejected_for_anonymous(method, user, tp):
    """Anonymous callers can't edit or delete another member's record."""
    res = getattr(tp.client, method)(
        reverse("users-detail", kwargs={"pk": user.pk}),
        data={"display_name": "outsider"},
        content_type="application/json",
    )
    tp.response_403(res)
    user.refresh_from_db()
    assert user.display_name == "Regular User"


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_user_api_detail_write_rejected_for_regular_user(method, user, super_user, tp):
    """A logged-in member can't reach another member's record with any write
    method. PATCH used to pass the permission check where PUT/DELETE did not."""
    with tp.login(user):
        res = getattr(tp.client, method)(
            reverse("users-detail", kwargs={"pk": super_user.pk}),
            data={"display_name": "outsider"},
            content_type="application/json",
        )
    tp.response_403(res)
    super_user.refresh_from_db()
    assert super_user.display_name == "Super User"


def test_user_api_create_rejected_for_regular_user(user, tp):
    with tp.login(user):
        res = tp.client.post(
            reverse("users-list"),
            data={"email": "outsider@example.com", "display_name": "outsider"},
            content_type="application/json",
        )
    tp.response_403(res)


def test_user_api_patch_allowed_for_staff(user, staff_user, tp):
    """Staff writes still work — the tightened check only closes the member path."""
    with tp.login(staff_user):
        res = tp.client.patch(
            reverse("users-detail", kwargs={"pk": user.pk}),
            data={"display_name": "Renamed By Staff"},
            content_type="application/json",
        )
    tp.response_200(res)
    user.refresh_from_db()
    assert user.display_name == "Renamed By Staff"
