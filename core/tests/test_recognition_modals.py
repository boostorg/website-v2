"""Template behaviour for the Achievements and Badges dialogs."""

from django.template.loader import render_to_string

from core.constants import (
    ACHIEVEMENTS_DIALOG_ITEMS,
    BADGES_DIALOG_ITEMS,
    BadgeToken,
)

ACHIEVEMENTS = "v3/includes/_achievements_modal.html"
BADGES = "v3/includes/_badges_modal.html"
DIALOG = "v3/includes/_dialog.html"


def test_achievements_modal_lists_the_whole_catalogue():
    out = render_to_string(ACHIEVEMENTS, {})

    assert out.count("recognition-list__row") == len(ACHIEVEMENTS_DIALOG_ITEMS)
    for item in ACHIEVEMENTS_DIALOG_ITEMS:
        assert item["name"] in out
        assert item["description"] in out


def test_badges_modal_lists_both_badge_types():
    out = render_to_string(BADGES, {})

    assert out.count("recognition-list__row") == len(BADGES_DIALOG_ITEMS)
    assert "Achievement-based" in out
    assert "Tenure-based" in out


def test_modals_render_title_and_description():
    achievements = render_to_string(ACHIEVEMENTS, {})
    badges = render_to_string(BADGES, {})

    assert ">Achievements</h2>" in achievements
    assert "Achievements capture your contributions to Boost" in achievements
    assert ">Badges</h2>" in badges
    assert "Badges recognize your journey on Boost" in badges


def test_items_can_be_overridden():
    """All content arrives via props; the catalogue is only the default."""
    items = [{"token": BadgeToken.TIER_2, "name": "Custom", "description": "Supplied."}]

    out = render_to_string(ACHIEVEMENTS, {"items": items})

    assert out.count("recognition-list__row") == 1
    assert "Custom" in out
    assert "Library Author" not in out


def test_dialog_id_can_be_overridden_so_two_instances_coexist():
    out = render_to_string(BADGES, {"dialog_id": "badges-modal-scrollable"})

    assert 'id="badges-modal-scrollable"' in out
    assert 'aria-labelledby="badges-modal-scrollable-title"' in out


def test_modals_have_no_action_buttons():
    """Figma shows neither a footer note nor action buttons on these dialogs."""
    for template in (ACHIEVEMENTS, BADGES):
        assert "dialog-modal__buttons" not in render_to_string(template, {})


def test_modals_inherit_dialog_aria():
    out = render_to_string(ACHIEVEMENTS, {})

    assert 'role="dialog"' in out
    assert 'aria-modal="true"' in out
    assert 'aria-labelledby="achievements-modal-title"' in out
    assert 'aria-describedby="achievements-modal-desc"' in out


def test_scroll_region_is_focusable_and_labelled():
    """The list must be reachable and scrollable by keyboard alone."""
    out = render_to_string(ACHIEVEMENTS, {})

    assert 'class="recognition-list"' in out
    assert 'tabindex="0"' in out
    assert 'aria-label="Achievements"' in out


def test_row_icons_are_decorative():
    """Each name is adjacent visible text, so the icon must not repeat it."""
    out = render_to_string(ACHIEVEMENTS, {})
    icons = out.count("badge-v3 ")

    assert icons == len(ACHIEVEMENTS_DIALOG_ITEMS)
    assert out.count('aria-hidden="true"') >= icons
    assert 'role="tooltip"' not in out


def test_boost_day_row_uses_its_own_icon():
    out = render_to_string(ACHIEVEMENTS, {})

    assert "boost_day" in out
    assert "Boost day celebration" in out


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
