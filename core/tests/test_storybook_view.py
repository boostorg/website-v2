def test_anonymous_is_redirected_to_login(tp, tmp_path, settings):
    settings.STORYBOOK_ROOT = tmp_path
    (tmp_path / "index.html").write_text("<html></html>")

    response = tp.client.get("/storybook/")

    assert response.status_code == 302
    assert "login" in response["Location"]


def test_non_staff_user_is_redirected_to_login(tp, user, tmp_path, settings):
    settings.STORYBOOK_ROOT = tmp_path
    (tmp_path / "index.html").write_text("<html></html>")
    tp.client.force_login(user)

    response = tp.client.get("/storybook/")

    assert response.status_code == 302


def test_staff_user_gets_the_bundle_uncached(tp, staff_user, tmp_path, settings):
    """A shared CDN sits in front of this site and caches responses by
    default. Without never_cache, the first staff user to load this view
    gets it cached at the edge, and every later visitor - staff or not - is
    served that cached copy directly, bypassing staff_member_required
    entirely.
    """
    settings.STORYBOOK_ROOT = tmp_path
    (tmp_path / "index.html").write_text("<html>storybook</html>")
    tp.client.force_login(staff_user)

    response = tp.client.get("/storybook/")

    assert response.status_code == 200
    cache_control = response["Cache-Control"]
    assert "no-store" in cache_control
    assert "private" in cache_control
