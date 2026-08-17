"""Tests for the badge page as the single tier-configuration surface."""

import pytest
from django.contrib.admin.sites import AdminSite
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from badges.admin import AchievementAdmin, BadgeAdmin
from badges.enums import TierRank
from badges.models import Achievement, Badge, BadgeTier, UserBadge
from badges.services import deactivate_tier

pytestmark = pytest.mark.django_db

PREFIX = "tiers"


def _row(tier, threshold=None, rank=None, delete=False):
    """One bound inline row for an existing tier, optionally edited."""
    row = {
        "id": str(tier.pk),
        "rank": rank or tier.rank,
        "threshold": str(tier.threshold if threshold is None else threshold),
    }
    if delete:
        row["DELETE"] = "on"
    return row


def _post_ladder(client, badge, rows):
    """POST the badge change form with ``rows`` as its complete ladder."""
    data = {
        "label": badge.label,
        "description": badge.description,
        f"{PREFIX}-TOTAL_FORMS": str(len(rows)),
        f"{PREFIX}-INITIAL_FORMS": str(sum(1 for row in rows if row.get("id"))),
        f"{PREFIX}-MIN_NUM_FORMS": "0",
        f"{PREFIX}-MAX_NUM_FORMS": str(len(TierRank)),
    }
    for index, row in enumerate(rows):
        for name, value in row.items():
            data[f"{PREFIX}-{index}-{name}"] = value
    return client.post(
        reverse("admin:badges_badge_change", args=[badge.pk]), data, follow=True
    )


def _ladder_rows(badge):
    """Every tier of a badge as ``(rank, threshold, is_active)``."""
    return sorted(
        badge.tiers.values_list("rank", "threshold", "is_active"),
        key=lambda row: (TierRank(row[0]).order, row[1]),
    )


def test_editing_a_threshold_retires_and_replaces_the_tier(
    client, super_user, badge, achievement
):
    """An in-place update would revoke the members who met the old threshold."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    silver = badge.tiers.get(rank=TierRank.SILVER)
    gold = badge.tiers.get(rank=TierRank.GOLD)
    client.force_login(super_user)

    _post_ladder(client, badge, [_row(bronze, threshold=2), _row(silver), _row(gold)])

    bronze.refresh_from_db()
    assert bronze.threshold == 1
    assert bronze.is_active is False
    assert bronze.deactivated_by == super_user
    assert bronze.deactivated_at is not None
    replacement = badge.tiers.get(rank=TierRank.BRONZE, is_active=True)
    assert replacement.threshold == 2
    assert replacement.pk != bronze.pk


def test_editing_a_threshold_keeps_existing_holders(
    client,
    super_user,
    plain_user,
    badge,
    achievement,
    grant_achievement,
    django_capture_on_commit_callbacks,
):
    """The grandfathering guard, exercised through the form an admin uses."""
    grant_achievement(plain_user, achievement, count=5)
    gold = badge.tiers.get(rank=TierRank.GOLD)
    held = UserBadge.objects.get(user=plain_user, tier=gold)
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    silver = badge.tiers.get(rank=TierRank.SILVER)
    client.force_login(super_user)

    with django_capture_on_commit_callbacks(execute=True):
        _post_ladder(
            client, badge, [_row(bronze), _row(silver), _row(gold, threshold=10)]
        )

    held.refresh_from_db()
    assert held.revoked_at is None


def test_editing_a_threshold_awards_newly_qualifying_members(
    client,
    super_user,
    plain_user,
    badge,
    achievement,
    grant_achievement,
    django_capture_on_commit_callbacks,
):
    """Lowering a threshold takes effect without anyone running a sweep."""
    grant_achievement(plain_user, achievement, count=3)
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    silver = badge.tiers.get(rank=TierRank.SILVER)
    gold = badge.tiers.get(rank=TierRank.GOLD)
    assert not UserBadge.objects.filter(user=plain_user, tier=gold).exists()
    client.force_login(super_user)

    # Silver comes down with gold: the ladder has to stay ordered as submitted.
    with django_capture_on_commit_callbacks(execute=True):
        _post_ladder(
            client,
            badge,
            [_row(bronze), _row(silver, threshold=2), _row(gold, threshold=3)],
        )

    awarded = UserBadge.objects.get(
        user=plain_user, tier__rank=TierRank.GOLD, tier__is_active=True
    )
    assert awarded.revoked_at is None


def test_a_threshold_out_of_ladder_order_is_refused(
    client, super_user, badge, achievement
):
    """Silver may not be dragged onto bronze, and nothing is written when it is."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    silver = badge.tiers.get(rank=TierRank.SILVER)
    gold = badge.tiers.get(rank=TierRank.GOLD)
    client.force_login(super_user)

    response = _post_ladder(
        client, badge, [_row(bronze), _row(silver, threshold=1), _row(gold)]
    )

    assert "threshold of the rank below this one" in response.content.decode()
    assert _ladder_rows(badge) == [
        (TierRank.BRONZE.value, 1, True),
        (TierRank.SILVER.value, 3, True),
        (TierRank.GOLD.value, 5, True),
    ]


def test_shifting_the_whole_ladder_up_is_accepted(
    client, super_user, badge, achievement
):
    """Every rung moves at once, so each one briefly collides with a stored value.

    Judged against the submitted ladder this is legal, and it is the edit staff
    actually make when a badge turns out to be too easy across the board.
    """
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    silver = badge.tiers.get(rank=TierRank.SILVER)
    gold = badge.tiers.get(rank=TierRank.GOLD)
    client.force_login(super_user)

    _post_ladder(
        client,
        badge,
        [
            _row(bronze, threshold=5),
            _row(silver, threshold=10),
            _row(gold, threshold=15),
        ],
    )

    assert sorted(
        badge.tiers.filter(is_active=True).values_list("rank", "threshold"),
        key=lambda row: TierRank(row[0]).order,
    ) == [
        (TierRank.BRONZE.value, 5),
        (TierRank.SILVER.value, 10),
        (TierRank.GOLD.value, 15),
    ]


def test_deleting_a_tier_row_in_the_inline_retires_it(
    client, super_user, badge, achievement
):
    """Removing a row is a retirement; the UserBadge rows behind it survive."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    silver = badge.tiers.get(rank=TierRank.SILVER)
    gold = badge.tiers.get(rank=TierRank.GOLD)
    client.force_login(super_user)

    _post_ladder(client, badge, [_row(bronze), _row(silver, delete=True), _row(gold)])

    silver.refresh_from_db()
    assert silver.is_active is False
    assert silver.deactivated_by == super_user
    assert badge.tiers.count() == 3


def test_retiring_a_tier_the_members_have_earned_is_not_refused(
    client,
    super_user,
    plain_user,
    badge,
    achievement,
    grant_achievement,
    django_capture_on_commit_callbacks,
):
    """The inline's own delete check would refuse this, and name every holder.

    Django validates a ticked delete by collecting what the row protects, and
    ``UserBadge.tier`` protects it, so the only retirement it lets through is one
    nobody has earned - the case that needs no protecting. The retirement itself
    is what preserves those holders.
    """
    grant_achievement(plain_user, achievement, count=5)
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    silver = badge.tiers.get(rank=TierRank.SILVER)
    gold = badge.tiers.get(rank=TierRank.GOLD)
    held = UserBadge.objects.get(user=plain_user, tier=bronze)
    client.force_login(super_user)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post_ladder(
            client, badge, [_row(bronze, delete=True), _row(silver), _row(gold)]
        )

    assert "protected related objects" not in response.content.decode()
    bronze.refresh_from_db()
    assert bronze.is_active is False
    assert bronze.deactivated_by == super_user
    held.refresh_from_db()
    assert held.revoked_at is None


def test_adding_a_tier_row_in_the_inline_creates_and_awards_it(
    client,
    super_user,
    plain_user,
    badge,
    achievement,
    grant_achievement,
    django_capture_on_commit_callbacks,
):
    """A whole ladder is one page: a fourth rank needs no second changelist."""
    grant_achievement(plain_user, achievement, count=10)
    rows = [_row(tier) for tier in badge.tiers.order_by("threshold")]
    rows.append({"id": "", "rank": TierRank.PLATINUM, "threshold": "10"})
    client.force_login(super_user)

    with django_capture_on_commit_callbacks(execute=True):
        _post_ladder(client, badge, rows)

    platinum = badge.tiers.get(rank=TierRank.PLATINUM)
    assert platinum.is_active is True
    assert platinum.threshold == 10
    assert UserBadge.objects.filter(
        user=plain_user, tier=platinum, revoked_at=None
    ).exists()


def test_two_new_sibling_tiers_cannot_submit_the_same_rank(
    client, super_user, badge, achievement
):
    """Cross-form validation returns the page instead of a constraint error."""
    rows = [_row(tier) for tier in badge.tiers.order_by("threshold")]
    rows.extend(
        [
            {"id": "", "rank": TierRank.DIAMOND, "threshold": "7"},
            {"id": "", "rank": TierRank.DIAMOND, "threshold": "9"},
        ]
    )
    client.force_login(super_user)

    response = _post_ladder(client, badge, rows)

    assert response.status_code == 200
    assert "Only one active Diamond tier is allowed for a badge." in (
        response.content.decode()
    )
    assert not badge.tiers.filter(rank=TierRank.DIAMOND).exists()


def test_delete_and_readd_same_rank_stays_rejected(
    client, super_user, badge, achievement
):
    """Replacing a rank uses an edit; delete-and-readd remains unsupported."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    silver = badge.tiers.get(rank=TierRank.SILVER)
    gold = badge.tiers.get(rank=TierRank.GOLD)
    rows = [
        _row(bronze),
        _row(silver, delete=True),
        _row(gold),
        {"id": "", "rank": TierRank.SILVER, "threshold": "4"},
    ]
    client.force_login(super_user)

    response = _post_ladder(client, badge, rows)

    assert response.status_code == 200
    assert "An active Silver tier already exists for this badge." in (
        response.content.decode()
    )
    silver.refresh_from_db()
    assert silver.is_active is True
    assert list(badge.tiers.filter(rank=TierRank.SILVER)) == [silver]


def test_a_badge_and_its_whole_ladder_are_one_save(client, super_user, achievement):
    """Creating a badge from scratch must not need a second page."""
    client.force_login(super_user)
    rows = [
        {"id": "", "rank": rank, "threshold": str(index + 1)}
        for index, rank in enumerate(TierRank)
    ]
    data = {
        "label": "documenter",
        "achievement": str(achievement.pk),
        "description": "Docs.",
        f"{PREFIX}-TOTAL_FORMS": str(len(rows)),
        f"{PREFIX}-INITIAL_FORMS": "0",
        f"{PREFIX}-MIN_NUM_FORMS": "0",
        f"{PREFIX}-MAX_NUM_FORMS": str(len(TierRank)),
    }
    for index, row in enumerate(rows):
        for name, value in row.items():
            data[f"{PREFIX}-{index}-{name}"] = value

    client.post(reverse("admin:badges_badge_add"), data, follow=True)

    tiers = BadgeTier.objects.filter(badge__label="documenter")
    assert tiers.count() == len(TierRank)
    assert set(tiers.values_list("is_active", flat=True)) == {True}


def test_the_replacement_message_names_both_tiers(
    client, super_user, badge, achievement
):
    """ "Bronze was changed" is not what happened, and the difference matters."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    silver = badge.tiers.get(rank=TierRank.SILVER)
    gold = badge.tiers.get(rank=TierRank.GOLD)
    client.force_login(super_user)

    response = _post_ladder(
        client, badge, [_row(bronze, threshold=2), _row(silver), _row(gold)]
    )

    body = response.content.decode()
    assert "Retired Bronze (&gt;= 1) and created Bronze (&gt;= 2)" in body
    assert "Members who already earned Bronze keep it" in body


def test_the_retirement_message_says_the_tier_was_not_deleted(
    client, super_user, badge, achievement
):
    """The row survives, and so do the badges awarded against it."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    silver = badge.tiers.get(rank=TierRank.SILVER)
    gold = badge.tiers.get(rank=TierRank.GOLD)
    client.force_login(super_user)

    response = _post_ladder(
        client, badge, [_row(bronze), _row(silver, delete=True), _row(gold)]
    )

    assert "Retired Silver (&gt;= 3)" in response.content.decode()


def test_the_threshold_column_explains_that_changes_are_not_retroactive(
    client, super_user, badge, achievement
):
    """Tabular inlines render field help text once, as the column tooltip."""
    client.force_login(super_user)

    response = client.get(reverse("admin:badges_badge_change", args=[badge.pk]))

    assert "members who already reached the old threshold keep" in (
        response.content.decode()
    )


def test_the_inline_shows_the_live_ladder_in_rank_order(
    client, super_user, badge, achievement
):
    """Retired tiers stay out of the way, and bronze reads before diamond."""
    deactivate_tier(badge.tiers.get(rank=TierRank.SILVER))
    # Thresholds deliberately out of ladder order, so an ordering by threshold
    # alone would put diamond first.
    baker.make(BadgeTier, badge=badge, rank=TierRank.DIAMOND, threshold=2)
    client.force_login(super_user)

    response = client.get(reverse("admin:badges_badge_change", args=[badge.pk]))

    formset = response.context["inline_admin_formsets"][0].formset
    assert [form.instance.rank for form in formset.initial_forms] == [
        TierRank.BRONZE,
        TierRank.GOLD,
        TierRank.DIAMOND,
    ]


def test_the_badge_page_links_its_retired_tiers(client, super_user, badge, achievement):
    """Retired rows stay reachable without cluttering the live ladder."""
    deactivate_tier(badge.tiers.get(rank=TierRank.SILVER))
    client.force_login(super_user)

    response = client.get(reverse("admin:badges_badge_change", args=[badge.pk]))

    expected = (
        f"{reverse('admin:badges_badgetier_changelist')}"
        f"?is_active__exact=0&amp;badge__id__exact={badge.pk}"
    )
    assert expected in response.content.decode()


def test_the_badge_page_says_so_when_nothing_is_retired(
    client, super_user, badge, achievement
):
    """A link to an empty changelist would read as a broken one."""
    client.force_login(super_user)

    response = client.get(reverse("admin:badges_badge_change", args=[badge.pk]))

    body = response.content.decode()
    assert "is_active__exact=0" not in body
    assert "None." in body


def test_the_retired_tier_link_filters_to_one_badge(
    client, super_user, badge, achievement
):
    """The filtered changelist has to accept both lookups, not redirect to ?e=1."""
    retired = badge.tiers.get(rank=TierRank.SILVER)
    deactivate_tier(retired)
    other = baker.make("badges.Badge", label="documenter", achievement=achievement)
    deactivate_tier(
        baker.make(BadgeTier, badge=other, rank=TierRank.BRONZE, threshold=1)
    )
    client.force_login(super_user)

    response = client.get(
        f"{reverse('admin:badges_badgetier_changelist')}"
        f"?is_active__exact=0&badge__id__exact={badge.pk}"
    )

    assert response.status_code == 200
    assert set(response.context["cl"].queryset.values_list("pk", flat=True)) == {
        retired.pk
    }


def _changelist_rows(client):
    """Badge changelist rows keyed by label, with the health columns prefetched."""
    response = client.get(reverse("admin:badges_badge_changelist"))
    assert response.status_code == 200
    return {row.label: row for row in response.context["cl"].result_list}


def test_the_changelist_shows_the_ladder_in_rank_order(
    client, super_user, badge, achievement
):
    """Thresholds do not have to ascend with rank, so ordering by them lies."""
    baker.make(BadgeTier, badge=badge, rank=TierRank.DIAMOND, threshold=2)
    client.force_login(super_user)

    rows = _changelist_rows(client)

    assert BadgeAdmin(Badge, AdminSite()).ladder(rows[badge.label]) == "1 / 3 / 5 / 2"


def test_the_changelist_flags_a_badge_that_can_never_award(
    client, super_user, achievement
):
    """A badge with no active tiers looks complete and does nothing."""
    baker.make("badges.Badge", label="documenter", achievement=achievement)
    client.force_login(super_user)

    rows = _changelist_rows(client)

    assert BadgeAdmin(Badge, AdminSite()).ladder(rows["documenter"]) == (
        "No tiers - awards nothing"
    )


def test_the_changelist_flags_an_unwired_source(client, super_user, catalogue):
    """Two of the eight badges only ever move on a manual grant."""
    client.force_login(super_user)
    admin_class = BadgeAdmin(Badge, AdminSite())

    rows = _changelist_rows(client)

    assert admin_class.source_wired(rows["commits_master"]) is True
    assert admin_class.source_wired(rows["documenter"]) is False
    assert admin_class.source_wired(rows["regular"]) is False


def test_the_changelist_counts_each_holder_once_and_skips_revocations(
    client, super_user, plain_user, badge, achievement, grant_achievement
):
    """Three tiers held by one member is one holder, and a revoked badge is none."""
    grant_achievement(plain_user, achievement, count=5)  # bronze + silver + gold
    other = baker.make("users.User", email="revoked-holder@example.com")
    grant_achievement(other, achievement, count=1)
    UserBadge.objects.filter(user=other).update(revoked_at=timezone.now())
    client.force_login(super_user)

    rows = _changelist_rows(client)

    assert BadgeAdmin(Badge, AdminSite()).holders(rows[badge.label]) == 1


def _achievement_rows(client):
    """Achievement changelist rows keyed by slug."""
    response = client.get(reverse("admin:badges_achievement_changelist"))
    assert response.status_code == 200
    return {row.slug: row for row in response.context["cl"].result_list}


def test_the_achievement_changelist_names_the_badge_it_feeds(
    client, super_user, badge, achievement
):
    """Which badge a type drives is otherwise only visible from the badge side."""
    client.force_login(super_user)

    rows = _achievement_rows(client)

    assert AchievementAdmin(Achievement, AdminSite()).badge(rows[achievement.slug]) == (
        "Maintainer"
    )


def test_the_achievement_changelist_flags_a_type_with_no_badge(
    client, super_user, achievement
):
    """Grants against a badgeless type accumulate and can never award."""
    client.force_login(super_user)

    rows = _achievement_rows(client)

    assert AchievementAdmin(Achievement, AdminSite()).badge(rows[achievement.slug]) == (
        "None - awards nothing"
    )


def test_the_achievement_changelist_counts_only_valid_grants(
    client, super_user, plain_user, badge, achievement, grant_achievement
):
    """Thresholds count valid grants, so that is the number worth showing."""
    rows_granted = grant_achievement(plain_user, achievement, count=3)
    rows_granted[0].is_valid = False
    rows_granted[0].save()
    client.force_login(super_user)

    rows = _achievement_rows(client)

    assert (
        AchievementAdmin(Achievement, AdminSite()).grants(rows[achievement.slug]) == 2
    )


def test_badge_tiers_are_hidden_from_the_admin_index(client, super_user, badge):
    """One entry point for configuring a ladder, not two."""
    client.force_login(super_user)

    index = client.get(reverse("admin:index"))
    changelist = client.get(reverse("admin:badges_badgetier_changelist"))

    listed = [
        model["object_name"]
        for app in index.context["app_list"]
        if app["app_label"] == "badges"
        for model in app["models"]
    ]
    assert "Badge" in listed
    assert "BadgeTier" not in listed
    assert changelist.status_code == 200


def test_a_full_ladder_offers_no_blank_row(client, super_user, catalogue):
    """The blank row exists because "Add another" needs JS; five ranks is the cap."""
    full = Badge.objects.get(label="commits_master")
    client.force_login(super_user)

    response = client.get(reverse("admin:badges_badge_change", args=[full.pk]))

    formset = response.context["inline_admin_formsets"][0].formset
    assert len(formset.initial_forms) == len(TierRank)
    assert formset.extra_forms == []


def test_the_inline_refuses_a_second_active_tier_for_a_rank(
    client, super_user, badge, achievement
):
    """The constraint is reported as a form error, not a 500."""
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    silver = badge.tiers.get(rank=TierRank.SILVER)
    gold = badge.tiers.get(rank=TierRank.GOLD)
    client.force_login(super_user)

    response = _post_ladder(
        client,
        badge,
        [
            _row(bronze),
            _row(silver),
            _row(gold),
            {"id": "", "rank": TierRank.BRONZE, "threshold": "9"},
        ],
    )

    assert "An active Bronze tier already exists" in response.content.decode()
    assert _ladder_rows(badge) == [
        (TierRank.BRONZE, 1, True),
        (TierRank.SILVER, 3, True),
        (TierRank.GOLD, 5, True),
    ]
