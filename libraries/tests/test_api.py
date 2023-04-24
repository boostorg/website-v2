def test_library_search(library, logged_in_tp):
    """
    GET /api/v1/libraries/?q=
    A library containing the querystring is returned
    """
    library = library
    res = logged_in_tp.get(f"/api/v1/libraries/?q={library.name[:3]}")
    logged_in_tp.response_200(res)
    assert len(res.context["libraries"]) == 1
