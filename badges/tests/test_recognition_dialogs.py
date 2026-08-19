"""The Achievements and Badges dialogs, and the catalogue rows behind them."""

import pytest
from django.template.loader import render_to_string

from badges.display import (
    BOOST_DAY_ROW,
    TENURE_ROW,
    TIER_TOKENS,
    achievement_dialog_rows,
    badge_dialog_rows,
)
from badges.enums import BadgeLabel, TierRank
from badges.models import Achievement, Badge, BadgeTier
from badges.seed_data import SEED_CATALOGUE
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


def test_badge_rows_come_from_the_catalogue(catalogue):
    rows = badge_dialog_rows()

    assert len(rows) == Badge.objects.count() + 1
    by_name = {row["name"]: row for row in rows}
    for badge in Badge.objects.all():
        assert by_name[badge.get_label_display()]["description"] == badge.description


def test_badge_rows_end_with_tenure(catalogue):
    """Tenure stars are a display state, so they have no catalogue row either."""
    assert badge_dialog_rows()[-1] == TENURE_ROW


def test_badge_rows_follow_catalogue_order(catalogue):
    """Not Badge.Meta.ordering, which is alphabetical by raw label."""
    expected = [
        Badge.objects.get(label=label).get_label_display()
        for _, _, _, label, _ in SEED_CATALOGUE
    ]

    assert [row["name"] for row in badge_dialog_rows()[:-1]] == expected


def test_badge_rows_show_the_entry_tier(catalogue):
    rows = {row["name"]: row for row in badge_dialog_rows()}
    reviewer = Badge.objects.get(label=BadgeLabel.REVIEWER)

    assert rows[reviewer.get_label_display()]["token"] == TIER_TOKENS[TierRank.BRONZE]


def test_badge_with_no_active_tier_still_gets_a_row(catalogue):
    """A retuned badge is briefly tierless; its description still matters."""
    badge = Badge.objects.get(label=BadgeLabel.REVIEWER)
    BadgeTier.objects.filter(badge=badge).update(is_active=False)

    rows = {row["name"]: row for row in badge_dialog_rows()}

    assert badge.get_label_display() in rows
    assert rows[badge.get_label_display()]["token"] == TIER_TOKENS[TierRank.BRONZE]


def test_achievements_modal_renders_every_row(catalogue):
    out = render_to_string(ACHIEVEMENTS, {})

    assert out.count("recognition-list__row") == Achievement.objects.count() + 1
    for achievement in Achievement.objects.all():
        assert achievement.name in out
    assert "Boost day celebration" in out


def test_badges_modal_renders_every_row(catalogue):
    out = render_to_string(BADGES, {})

    assert out.count("recognition-list__row") == Badge.objects.count() + 1
    assert "Library Author" in out
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


@pytest.mark.parametrize("template", [ACHIEVEMENTS, BADGES])
def test_modals_render_on_an_empty_catalogue(db, template):
    """Only the display-state row remains; the dialog must not break."""
    out = render_to_string(template, {})

    assert out.count("recognition-list__row") == 1
