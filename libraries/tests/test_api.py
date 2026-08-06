import pytest

from django.urls import NoReverseMatch, reverse

from libraries.models import Library


def test_library_search(library, tp):
    """
    GET /api/v1/libraries/?q=
    A library containing the querystring is returned
    """
    library = library
    res = tp.get(f"/api/v1/libraries/?q={library.name[:3]}")
    tp.response_200(res)
    assert len(res.context["libraries"]) == 1


def test_library_api_rejects_anonymous_create(db, tp):
    """POST /api/v1/libraries/ must not create a record for an anonymous caller."""
    before = Library.objects.count()
    res = tp.client.post(
        "/api/v1/libraries/",
        {"name": "probe", "slug": "probe", "description": "probe"},
    )
    tp.response_405(res)
    assert Library.objects.count() == before


def test_library_api_rejects_authenticated_create(super_user, tp):
    """The endpoint is read-only for everyone, not just anonymous callers."""
    before = Library.objects.count()
    with tp.login(super_user):
        res = tp.client.post(
            "/api/v1/libraries/",
            {"name": "probe", "slug": "probe", "description": "probe"},
        )
    tp.response_405(res)
    assert Library.objects.count() == before


def test_library_api_detail_route_not_registered():
    """The router exposes no per-library route for edits or deletes to target."""
    with pytest.raises(NoReverseMatch):
        reverse("libraries-detail", kwargs={"pk": 1})


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_library_api_rejects_detail_writes(method, library, tp):
    """Writes to the old detail path leave the record untouched.

    The status varies by client — the catch-all page URL this path now falls
    through to answers 405, but a real client without a CSRF token is refused
    with 403 before reaching it — so only assert that nothing succeeded.
    """
    res = getattr(tp.client, method)(
        f"/api/v1/libraries/{library.pk}/",
        data={"name": "renamed", "slug": "renamed", "description": "renamed"},
        content_type="application/json",
    )
    assert not 200 <= res.status_code < 300
    library.refresh_from_db()
    assert library.name == "multi_array"
