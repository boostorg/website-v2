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
    res = tp.get("version-list")
    tp.response_200(res)
    assert "current_version" in res.context
    assert "version_list" in res.context
    assert res.context["current_version"] == version
    assert old_version in res.context["version_list"]
    assert inactive_version not in res.context["version_list"]
    assert len(res.context["version_list"]) == 1


def test_version_detail(version, tp):
    """
    GET /versions/{pk}/
    """
    res = tp.get("version-detail", pk=version.pk)
    tp.response_200(res)
