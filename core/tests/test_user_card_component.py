from django.template.loader import render_to_string

TEMPLATE = "v3/includes/_user_card.html"
BASE_CONTEXT = {"username": "Jane Doe", "avatar_url": "/img/avatar.png"}


def render_card(**overrides):
    return render_to_string(TEMPLATE, {**BASE_CONTEXT, **overrides})


def test_user_card_links_avatar_and_username_when_given_a_profile_url():
    html = render_card(profile_url="/users/jane-doe-k3f9/")
    assert '<a href="/users/jane-doe-k3f9/" class="user-card__avatar-link">' in html
    assert (
        '<a href="/users/jane-doe-k3f9/" class="user-card__username">Jane Doe</a>'
        in html
    )


def test_user_card_renders_plain_without_a_profile_url():
    """The profile page shows this card for the user whose page it is, where a
    link back to the same page would be noise."""
    html = render_card()
    assert '<span class="user-card__username">Jane Doe</span>' in html
    assert "user-card__avatar-link" not in html
    assert "<a href" not in html


def test_user_card_keeps_the_country_flag_out_of_the_link():
    """The flag labels a country; it is not a second click target."""
    html = render_card(profile_url="/users/jane-doe-k3f9/", flag_emoji="🇺🇸")
    flag = '<span class="user-card__flag" aria-hidden="true">🇺🇸</span>'
    assert flag in html
    assert flag in html.split("</a>", 1)[1]


def test_logged_out_user_card_ignores_a_profile_url():
    """The logged-out variant has no user to link to."""
    html = render_card(logged_out=True, profile_url="/users/jane-doe-k3f9/")
    assert "user-card__avatar-link" not in html
    assert "user-card__username" not in html
