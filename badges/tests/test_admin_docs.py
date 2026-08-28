"""Tests for the badges app index, which doubles as the section's docs page.

The copy on the page is rendered from ``docs/badges-admin.md``, so the tests
here check both that the page renders it and that the source file is intact.
"""

import pytest
from django.template import Context, Template
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_app_index_renders_the_documentation(client, super_user):
    """The first page of the badges section explains the pages and operations."""
    client.force_login(super_user)

    body = client.get(reverse("admin:app_list", args=["badges"])).content.decode()

    assert "How this section works" in body
    assert "The operations and when to run them" in body
    assert "Changing a badge's tiers" in body
    assert "How revocation works" in body


def test_app_index_links_the_documentation_stylesheet(client, super_user):
    """The docs page carries its own stylesheet, like the other admin pages."""
    client.force_login(super_user)

    body = client.get(reverse("admin:app_list", args=["badges"])).content.decode()

    assert "css/admin/admin-docs.css" in body


def test_app_index_keeps_the_model_links(client, super_user):
    """The model table below the docs still navigates to every page."""
    client.force_login(super_user)

    body = client.get(reverse("admin:app_list", args=["badges"])).content.decode()

    assert reverse("admin:badges_achievement_changelist") in body
    assert reverse("admin:badges_badge_changelist") in body
    assert reverse("admin:badges_userachievement_changelist") in body
    assert reverse("admin:badges_userbadge_changelist") in body
    assert reverse("admin:badges_achievementsyncrun_changelist") in body


def test_docs_file_is_present_and_renders_as_markdown():
    """The docs source exists and the tag turns its markdown into HTML.

    A raw dump of the file would pass a ``in body`` assertion, so the render is
    checked for the HTML that markdown processing produces: headings and tables
    become elements, and blockquotes carry the note copy.
    """
    output = Template("{% load badges_docs %}{% render_badges_docs %}").render(
        Context()
    )

    assert "<table>" in output
    assert "<blockquote>" in output
    assert ">How this section works</h2>" in output
    assert "<code>manage.py backfill_achievements</code>" in output
