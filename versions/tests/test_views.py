def test_version_list(version, tp):
    res = tp.get("version-list")
    tp.response_200(res)
    print(res.context)
    objs = res.context["version_list"]
    assert len(objs) == 1
    assert version in objs
