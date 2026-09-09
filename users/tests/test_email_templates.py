"""Rendering guards shared by every branded transactional email.

The per-flow tests live with the app that sends the email; these check the
templates themselves, so a template that stops resolving its CTA or leaks an
unrendered tag fails here rather than in an inbox.
"""

import re

import pytest

from users.management.commands.send_test_emails import TEMPLATES, render_template

BASE_URL = "https://www.boost.org"


@pytest.mark.parametrize("key", sorted(TEMPLATES))
def test_template_renders_without_leftover_tags(key):
    subject, text_body, html_body = render_template(key, base_url=BASE_URL)

    assert subject
    for body in (subject, text_body, html_body):
        assert "{{" not in body
        assert "{%" not in body


@pytest.mark.parametrize("key", sorted(TEMPLATES))
def test_every_link_is_absolute(key):
    """No CTA may fall back to a placeholder or a root-relative path: an email
    client has no page to resolve those against."""
    _, _, html_body = render_template(key, base_url=BASE_URL)

    hrefs = re.findall(r'href="([^"]*)"', html_body)
    assert hrefs
    for href in hrefs:
        assert href.startswith(("http://", "https://", "mailto:")), href


@pytest.mark.parametrize("key", sorted(TEMPLATES))
def test_cta_url_reaches_both_bodies(key):
    """The button URL has to appear in the plain-text part too, for clients
    that never render the HTML alternative."""
    action_url = TEMPLATES[key]["action_url"]
    _, text_body, html_body = render_template(key, base_url=BASE_URL)

    assert action_url in text_body
    assert action_url in html_body


@pytest.mark.parametrize("key", sorted(TEMPLATES))
def test_preferences_link_only_where_it_applies(key):
    """The footer's opt-out sentence belongs on the notification emails, not on
    the one-off transactional ones the recipient cannot unsubscribe from."""
    expected = bool(TEMPLATES[key].get("context", {}).get("with_preferences"))
    _, text_body, html_body = render_template(key, base_url=BASE_URL)

    footer_sentence = "Want to change how you receive these emails?"
    assert (footer_sentence in html_body) is expected
    assert (footer_sentence in text_body) is expected
