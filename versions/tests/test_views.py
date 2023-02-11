import datetime

from model_bakery import baker


def test_version_list(version, tp):
    """
    GET /versions/
    """
    res = tp.get("version-list")
    tp.response_200(res)


def test_version_list_context(version, old_version, inactive_version, tp):
    """
    GET /versions/
    """
    older_version = baker.make(
        "versions.Version",
        name="Version 1.67.0",
        description="Sample",
        release_date=datetime.date.today() - datetime.timedelta(days=700),
    )
    res = tp.get("version-list")
    tp.response_200(res)
    assert "current_version" in res.context
    assert "version_list" in res.context
    assert len(res.context["version_list"]) == 2
    assert res.context["current_version"] == version
    assert old_version in res.context["version_list"]
    assert older_version in res.context["version_list"]
    assert old_version == res.context["version_list"][0]
    assert inactive_version not in res.context["version_list"]


def test_version_detail(version, tp):
    """
    GET /versions/{pk}/
    """
    res = tp.get("version-detail", pk=version.pk)
    tp.response_200(res)
