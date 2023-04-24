def test_public_view(full_version_one, logged_in_tp):
    r = logged_in_tp.client.get("/api/v1/versions/")
    logged_in_tp.response_200(r)
