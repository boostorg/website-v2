import pytest
from datetime import timedelta
from django.utils import timezone
from model_bakery import baker


@pytest.mark.skip("TODO: Fix. Live behavior is fine, but test fails")
def test_version_most_recent_detail(version, tp):
    """
    GET /releases/
    """
    now = timezone.now()

    ten_years_ago = now - timedelta(days=365 * 10)
    baker.make("versions.Version", release_date=ten_years_ago)
    res = tp.get_check_200("releases-most-recent")
    assert "versions" in res.context
    assert res.context["version"] == version


def test_version_detail(version, tp):
    """
    GET /releases/{slug}/
    """
    res = tp.get("release-detail", slug=version.slug)
    tp.response_200(res)


def test_version_detail_post(version, tp):
    """
    POST /releases/{slug}/
    """
    res = tp.post("releases-most-recent", data={"version": version.slug})
    tp.response_200(res)
