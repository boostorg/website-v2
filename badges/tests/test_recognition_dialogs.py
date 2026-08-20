"""The Achievements and Badges dialogs, and the catalogue rows behind them."""

import re

import pytest
from django.template.loader import render_to_string
from django.test import override_settings

from badges.display import (
    ACHIEVEMENT_BASED_ROW,
    BOOST_DAY_ROW,
    PLACEHOLDER_ACHIEVEMENT_COUNT,
    TENURE_ROW,
    achievement_dialog_rows,
    badge_dialog_rows,
)
from badges.models import Achievement
from core.constants import BadgeToken

ACHIEVEMENTS = "v3/includes/_achievements_modal.html"
BADGES = "v3/includes/_badges_modal.html"
DIALOG = "v3/includes/_dialog.html"


def test_achievement_rows_come_from_the_catalogue(catalogue):
    rows = achievement_dialog_rows()

    assert [row["name"] for row in rows[:-1]] == list(
        Achievement.objects.values_list("name", flat=True)
    )
    for row, achievement in zip(rows, Achievement.objects.all()):
        assert row["description"] == achievement.description


def test_achievement_rows_end_with_boost_day(catalogue):
    """Boost Day is a display state, so it has no catalogue row to read."""
    rows = achievement_dialog_rows()

    assert rows[-1] == BOOST_DAY_ROW
    assert len(rows) == Achievement.objects.count() + 1


def test_achievement_rows_carry_a_counter(catalogue):
    """Per Figma the achievement icon is a tally, not tier artwork."""
    rows = achievement_dialog_rows()[:-1]

    assert {row["token"] for row in rows} == {BadgeToken.ACHIEVEMENT_COUNT}
    assert {row["count"] for row in rows} == {PLACEHOLDER_ACHIEVEMENT_COUNT}


def test_single_digit_counts_render_padded(catalogue):
    """A single digit is padded so the counter keeps one width."""
    out = render_to_string(ACHIEVEMENTS, {})

    assert ">01<" in out


def test_achievement_rows_cost_one_query(catalogue, django_assert_num_queries):
    with django_assert_num_queries(1):
        achievement_dialog_rows()


def test_badge_rows_are_the_two_kinds_of_badge():
    """Per Figma the dialog names the kinds of badge, not the catalogue."""
    assert badge_dialog_rows() == [ACHIEVEMENT_BASED_ROW, TENURE_ROW]


def test_badge_rows_need_no_database(django_assert_num_queries):
    with django_assert_num_queries(0):
        badge_dialog_rows()


def test_badge_rows_use_the_cluster_icons():
    """Each row stands for a whole kind of badge, not one tier of one badge."""
    tokens = [row["token"] for row in badge_dialog_rows()]

    assert tokens == [BadgeToken.ACHIEVEMENT_BASED, BadgeToken.TENURE_BASED]


@pytest.mark.parametrize("local_development", [True, False], ids=["local", "s3"])
@pytest.mark.parametrize(
    "token,filename",
    [
        (BadgeToken.ACHIEVEMENT_BASED, "achievement-based.png"),
        (BadgeToken.TENURE_BASED, "tenure-based.png"),
    ],
)
def test_cluster_tokens_point_at_their_artwork(token, filename, local_development):
    """Pins the asset path each cluster token asks for; a typo is a silent 404.

    Both serving modes are forced because ``large_static`` wraps the same path in
    two entirely different URLs, and only the path is ours to get right.

    Whether the file is really there is not checkable: ``static-large`` is
    gitignored and synced from S3, so no checkout has it. Publishing a new asset
    means running ``just up_sync_images``.
    """
    with override_settings(
        LOCAL_DEVELOPMENT=local_development,
        STATIC_URL="/static/",
        STATIC_CONTENT_AWS_S3_ENDPOINT_URL="https://s3.example.test",
        STATIC_CONTENT_BUCKET_NAME="bucket",
    ):
        out = render_to_string("v3/includes/_badge_v3.html", {"token": token})

    (src,) = re.findall(r'src="([^"]+)"', out)
    assert src.endswith(f"img/v3/badges/{filename}")


def test_achievements_modal_renders_every_row(catalogue):
    out = render_to_string(ACHIEVEMENTS, {})

    assert out.count("recognition-list__row") == Achievement.objects.count() + 1
    for achievement in Achievement.objects.all():
        assert achievement.name in out
    assert "Boost day celebration" in out


def test_badges_modal_renders_both_kinds():
    out = render_to_string(BADGES, {})

    assert out.count("recognition-list__row") == 2
    assert "Achievement-based" in out
    assert "Tenure-based" in out


def test_modals_render_title_and_description(catalogue):
    achievements = render_to_string(ACHIEVEMENTS, {})
    badges = render_to_string(BADGES, {})

    assert ">Achievements</h2>" in achievements
    assert "Achievements capture your contributions to Boost" in achievements
    assert ">Badges</h2>" in badges
    assert "Badges recognize your journey on Boost" in badges


def test_items_can_be_overridden_without_touching_the_database(
    django_assert_num_queries,
):
    """A caller with rows in hand pays no query for the catalogue."""
    items = [{"token": BadgeToken.TIER_2, "name": "Custom", "description": "Supplied."}]

    with django_assert_num_queries(0):
        out = render_to_string(ACHIEVEMENTS, {"items": items})

    assert out.count("recognition-list__row") == 1
    assert "Custom" in out


def test_dialog_id_can_be_overridden_so_two_instances_coexist(catalogue):
    out = render_to_string(BADGES, {"dialog_id": "badges-modal-short"})

    assert 'id="badges-modal-short"' in out
    assert 'aria-labelledby="badges-modal-short-title"' in out


def test_modals_have_no_action_buttons(catalogue):
    """Figma shows neither a footer note nor action buttons on these dialogs."""
    for template in (ACHIEVEMENTS, BADGES):
        assert "dialog-modal__buttons" not in render_to_string(template, {})


def test_modals_inherit_dialog_aria(catalogue):
    out = render_to_string(ACHIEVEMENTS, {})

    assert 'role="dialog"' in out
    assert 'aria-modal="true"' in out
    assert 'aria-labelledby="achievements-modal-title"' in out
    assert 'aria-describedby="achievements-modal-desc"' in out


def test_scroll_region_is_focusable_and_labelled(catalogue):
    """The list must be reachable and scrollable by keyboard alone."""
    out = render_to_string(ACHIEVEMENTS, {})

    assert 'class="recognition-list"' in out
    assert 'tabindex="0"' in out
    assert 'aria-label="Achievements"' in out


def test_row_icons_are_decorative(catalogue):
    """Each name is adjacent visible text, so the icon must not repeat it."""
    out = render_to_string(ACHIEVEMENTS, {})
    icons = out.count("badge-v3 ")

    assert icons == Achievement.objects.count() + 1
    assert out.count('aria-hidden="true"') >= icons
    assert 'role="tooltip"' not in out


def test_dialog_content_slot_is_opt_in():
    """An existing Dialog caller passes no content_template and is unaffected."""
    out = render_to_string(
        DIALOG,
        {
            "dialog_id": "plain",
            "title": "Title",
            "description": "Body",
            "primary_label": "Confirm",
            "secondary_label": "Cancel",
        },
    )

    assert "dialog-modal__content" not in out
    assert "dialog-modal__buttons" in out


def test_badge_keeps_its_hover_label_when_not_decorative():
    """The decorative flag is additive; existing badge callers keep the tooltip."""
    out = render_to_string(
        "v3/includes/_badge_v3.html",
        {"token": BadgeToken.TIER_3, "label": "Gold badge"},
    )

    assert 'role="tooltip"' in out
    assert 'tabindex="0"' in out
    assert 'aria-label="Gold badge"' in out


@pytest.mark.parametrize(
    "template,rows", [(ACHIEVEMENTS, 1), (BADGES, 2)], ids=["achievements", "badges"]
)
def test_modals_render_on_an_empty_catalogue(db, template, rows):
    """Achievements falls back to Boost Day alone; Badges never read the table."""
    out = render_to_string(template, {})

    assert out.count("recognition-list__row") == rows
