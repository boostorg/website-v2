def test_public_view(full_version_one, tp):
    r = tp.client.get("/api/v1/versions/")
    tp.response_200(r)
