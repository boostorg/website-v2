def test_version_detail(version, tp):
    """
    GET /versions/{slug}/
    """
    res = tp.get("version-detail", slug=version.slug)
    tp.response_200(res)
