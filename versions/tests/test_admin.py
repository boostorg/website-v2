import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.urls import reverse
from model_bakery import baker

from versions.admin import ReviewAdmin
from versions.models import Review


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
