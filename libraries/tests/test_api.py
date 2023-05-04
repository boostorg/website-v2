def test_library_search(library, tp):
    """
    GET /api/v1/libraries/?q=
    A library containing the querystring is returned
    """
    library = library
    res = tp.get(f"/api/v1/libraries/?q={library.name[:3]}")
    tp.response_200(res)
    assert len(res.context["libraries"]) == 1
