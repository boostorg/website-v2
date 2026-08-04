from unittest.mock import patch

import pytest
from django.contrib.auth.models import Permission
from django.contrib.admin.sites import AdminSite
from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse
from model_bakery import baker

from versions.admin import ReviewAdmin
from versions.models import Review


@pytest.fixture(autouse=True)
def _clear_task_button_locks():
    """The import button debounces through the cache; isolate tests."""
    cache.clear()


@pytest.mark.django_db
def test_review_admin_import_button_enqueues_task(client, super_user):
    client.force_login(super_user)

    with patch("versions.admin.import_reviews_task.delay") as mock_delay:
        preview = client.post(reverse("admin:versions_review_import_reviews"))
        response = client.post(
            reverse("admin:versions_review_import_reviews"), {"apply": "1"}
        )

    assert preview.status_code == 200
    preview_body = preview.content.decode()
    assert "Duplicate stored reviews are merged" in preview_body
    assert "their results" in preview_body
    mock_delay.assert_called_once_with(actor_id=super_user.pk)
    # Redirects back to the Review changelist.
    assert response.status_code == 302


@pytest.mark.django_db
def test_review_admin_import_button_ignores_get(client, super_user):
    """Importing rewrites every Review row, so a link prefetch must not start it."""
    client.force_login(super_user)

    with patch("versions.admin.import_reviews_task.delay") as mock_delay:
        response = client.get(reverse("admin:versions_review_import_reviews"))

    mock_delay.assert_not_called()
    assert response.status_code == 302


@pytest.mark.django_db
def test_review_admin_changelist_shows_import_button(client, super_user):
    client.force_login(super_user)

    response = client.get(reverse("admin:versions_review_changelist"))

    assert response.status_code == 200
    assert reverse("admin:versions_review_import_reviews").encode() in response.content
    assert b"Duplicate reviews, their results" in response.content


@pytest.mark.django_db
def test_review_admin_import_requires_delete_permission(client):
    staff = baker.make("users.User", email="review-staff@example.com", is_staff=True)
    staff.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="versions",
            codename__in=("view_review", "change_review"),
        )
    )
    client.force_login(staff)

    changelist = client.get(reverse("admin:versions_review_changelist"))
    with patch("versions.admin.import_reviews_task.delay") as mock_delay:
        response = client.post(reverse("admin:versions_review_import_reviews"))

    assert changelist.status_code == 200
    assert changelist.context["task_buttons"] == []
    assert response.status_code == 403
    mock_delay.assert_not_called()


@pytest.mark.django_db
def test_review_admin_changelist_shows_review_manager_columns(client, super_user):
    client.force_login(super_user)
    manager = baker.make("libraries.CommitAuthor", name="Marshall Clow")
    baker.make(
        "versions.Review",
        submission="Boost.Linked",
        review_manager=manager,
        review_manager_raw="Marshall Clow",
    )
    baker.make(
        "versions.Review",
        submission="Boost.Unlinked",
        review_manager=None,
        review_manager_raw="Someone Unlinked",
    )

    response = client.get(reverse("admin:versions_review_changelist"))

    assert response.status_code == 200
    content = response.content.decode()
    # Resolved FK is rendered via CommitAuthor.__str__ (name).
    assert "Marshall Clow" in content
    # Raw column is always shown, even when the FK is unlinked.
    assert "Someone Unlinked" in content
    # Raw column is labelled as "Scraped review manager" to disambiguate it
    # from the resolved FK column.
    assert "Scraped review manager" in content


@pytest.mark.django_db
def test_review_admin_results_use_prefetched_objects(
    super_user, django_assert_num_queries
):
    review = baker.make("versions.Review")
    baker.make(
        "versions.ReviewResult",
        review=review,
        short_description="Accepted",
    )
    baker.make(
        "versions.ReviewResult",
        review=review,
        short_description="Released",
    )
    request = RequestFactory().get("/")
    request.user = super_user
    model_admin = ReviewAdmin(Review, AdminSite())
    prefetched = model_admin.get_queryset(request).get(pk=review.pk)

    with django_assert_num_queries(0):
        assert model_admin.get_results(prefetched) == "Accepted | Released"
