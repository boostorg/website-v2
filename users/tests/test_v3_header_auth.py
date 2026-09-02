from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.urls import reverse


def test_anonymous_gets_the_log_in_link(client, db):
    response = client.get(reverse("v3-header-auth"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Log In" in html
    assert "header__user-menu" not in html


def test_authenticated_gets_the_avatar_menu(client, user, db):
    client.force_login(user)
    response = client.get(reverse("v3-header-auth"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "header__user-menu" in html
    assert "Log In" not in html


def test_response_is_never_cached(client, user, db):
    """The whole point of the endpoint: a shared cache must not store it."""
    client.force_login(user)
    response = client.get(reverse("v3-header-auth"))

    assert "no-store" in response["Cache-Control"]
    assert "private" in response["Cache-Control"]
    assert "Cookie" in response["Vary"]


def test_avatar_id_is_used_when_known(client, user, db):
    client.force_login(user)
    response = client.get(reverse("v3-header-auth"), {"avatar_id": "mobile-user-menu"})

    assert 'id="mobile-user-menu-toggle"' in response.content.decode()


def test_unknown_avatar_id_falls_back_to_the_default(client, user, db):
    """An arbitrary id would otherwise be reflected into the markup."""
    client.force_login(user)
    response = client.get(
        reverse("v3-header-auth"), {"avatar_id": 'x" onload="alert(1)'}
    )
    html = response.content.decode()

    assert 'id="desktop-user-menu-toggle"' in html
    assert "onload" not in html


def _render_utilities(rf, db, **context):
    request = rf.get("/doc/user-guide/index.html")
    request.user = AnonymousUser()
    return render_to_string(
        "v3/includes/header/_header_utilities.html",
        {"avatar_id": "desktop-user-menu", **context},
        request=request,
    )


def test_header_defers_the_auth_slot_when_flagged(rf, db):
    html = _render_utilities(rf, db, defer_auth_state=True)

    assert "header__auth-placeholder" in html
    assert f'hx-get="{reverse("v3-header-auth")}?avatar_id=desktop-user-menu"' in html
    assert "<noscript>" in html


def test_header_renders_the_auth_slot_inline_by_default(rf, db):
    html = _render_utilities(rf, db)

    assert "header__auth-placeholder" not in html
    assert "hx-get" not in html
    assert "Log In" in html
