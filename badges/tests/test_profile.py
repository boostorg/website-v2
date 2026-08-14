"""Tests for turning a user's awarded badges into rendered profile data."""

from datetime import date, timedelta

import pytest
import waffle.testutils
from django.db import connection
from django.template.loader import render_to_string
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils import timezone
from django.utils.formats import date_format
from model_bakery import baker

from badges import display
from badges.enums import TierRank
from badges.models import Achievement, UserAchievement, UserBadge
from core.constants import BadgeToken

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _catalogue(catalogue):
    """Seed the real achievement catalogue for every test in this module."""


def _grant(user, slug, count=1):
    """Grant `count` manual achievements of `slug` (recalcs via the signal)."""
    achievement = Achievement.objects.get(slug=slug)
    for _ in range(count):
        UserAchievement.objects.create(
            user=user, achievement=achievement, source_type="manual"
        )


def _reload(user):
    """Re-fetch the user so cached_property badge state is discarded."""
    return type(user).objects.get(pk=user.pk)


def _pick(user, rank, slug="library-review"):
    """Store `rank` of `slug`'s badge as the user's chosen display badge."""
    user_badge = UserBadge.objects.get(
        user=user, badge__achievement__slug=slug, tier__rank=rank
    )
    user.display_badge = user_badge
    user.save(update_fields=["display_badge"])
    return user_badge


def _feature(user, slug, count=1):
    """Grant `count` of `slug` and feature the top badge that awards.

    Nothing is featured until the member picks one, so every test that expects a
    rendered badge has to make that choice, exactly as the edit page does.
    """
    _grant(user, slug, count=count)
    user.display_badge = display.held_badges(_reload(user), include_hidden=True)[0]
    user.save(update_fields=["display_badge"])
    return _reload(user)


def _published_entry(author, index):
    """A visible entry suitable for both recent and ranked card origins."""
    from news.models import Entry

    published_at = timezone.now() - timedelta(minutes=index)
    return Entry.objects.create(
        title=f"Post {index}",
        slug=f"profile-query-post-{index}",
        author=author,
        moderator=author,
        approved_at=published_at,
        publish_at=published_at,
        summary="A test post.",
    )


def _badge_queries(call):
    """Return a call's value and the number of UserBadge queries it issued."""
    with CaptureQueriesContext(connection) as queries:
        value = call()
    badge_query_count = sum(
        'FROM "badges_userbadge"' in query["sql"] for query in queries
    )
    return value, badge_query_count


def test_no_badges_yields_no_featured_badge(plain_user):
    """A fresh user has nothing to feature and an empty card list."""
    assert display.held_badges(plain_user) == []
    assert display.featured_badge(plain_user) is None
    assert display.badge_cards(plain_user) == []
    assert plain_user.featured_badge is None


def test_featured_badge_and_card_list(plain_user):
    """The featured badge and the card list expose real earned badges."""
    plain_user = _feature(plain_user, "library-authoring")  # bronze (threshold 1)

    featured = display.featured_badge(plain_user)
    assert featured["name"] == "Library Author"
    assert featured["icon"] == BadgeToken.TIER_1  # bronze -> tier-1

    cards = display.badge_cards(plain_user)
    assert cards[0]["icon"] == BadgeToken.TIER_1
    assert cards[0]["name"] == "Library Author"
    assert cards[0]["earned_date"] is not None


@pytest.mark.parametrize(
    ("rank", "token"),
    [
        (TierRank.BRONZE, BadgeToken.TIER_1),
        (TierRank.SILVER, BadgeToken.TIER_2),
        (TierRank.GOLD, BadgeToken.TIER_3),
        (TierRank.PLATINUM, BadgeToken.TIER_4),
        (TierRank.DIAMOND, BadgeToken.TIER_5),
    ],
)
def test_rank_maps_to_the_component_token_of_the_same_height(rank, token):
    """Diamond is the top rank, so it draws the component's top badge."""
    assert display.TIER_TOKENS[rank] == token


def test_token_numbers_climb_with_the_rank_ladder():
    """The reason the mapping above is what it is, asserted on its own.

    The component's assets are numbered rather than named after a metal, so the
    number *is* the ladder - and a mapping that does not climb with the ranks
    would show a lower-ranked member the higher-looking medal.
    """
    assert [display.TIER_TOKENS[rank] for rank in TierRank] == sorted(
        display.TIER_TOKENS.values()
    )


def test_badge_card_renders_its_semantic_asset_and_award_date(plain_user):
    """The card hands the component a token and a date the template formats.

    A ``date`` rather than a preformatted string: the project renders dates
    through Django's ``DATE_FORMAT`` everywhere else, so a string here would pin
    this one card to a format nothing else uses.
    """
    achievement = Achievement.objects.get(slug="library-review")
    badge = achievement.badges.get()
    diamond = badge.tiers.get(rank=TierRank.DIAMOND)
    awarded_at = timezone.datetime(2025, 3, 7, 14, 30, tzinfo=timezone.UTC)
    user_badge = UserBadge.objects.create(
        user=plain_user,
        badge=badge,
        tier=diamond,
        awarded_at=awarded_at,
    )

    card = display.badge_card(user_badge)
    rendered = render_to_string("v3/includes/_badges_card.html", {"badges": [card]})

    assert card["earned_date"] == date(2025, 3, 7)
    assert "img/v3/badges/tier-5.png" in rendered
    assert "img/v3/badges/tier-4.png" not in rendered
    assert date_format(date(2025, 3, 7)) in rendered


@override_settings(TIME_ZONE="America/New_York")
def test_badge_card_dates_the_award_in_the_project_timezone(plain_user):
    """A late-evening award keeps the day it happened on, not the UTC day.

    ``TIME_ZONE`` is UTC today, which makes the naive reading look correct; this
    pins the boundary so configuring a real timezone cannot shift every badge
    awarded after 7pm to the next day.
    """
    badge = Achievement.objects.get(slug="library-review").badges.get()
    user_badge = UserBadge.objects.create(
        user=plain_user,
        badge=badge,
        tier=badge.tiers.get(rank=TierRank.BRONZE),
        # 8:30pm in New York, already the 8th in UTC.
        awarded_at=timezone.datetime(2025, 3, 8, 1, 30, tzinfo=timezone.UTC),
    )

    assert display.badge_card(user_badge)["earned_date"] == date(2025, 3, 7)


def test_held_badges_lead_with_the_top_tier(plain_user):
    """With several tiers earned, the highest one leads the list."""
    badge = Achievement.objects.get(slug="library-review").badges.first()
    # Reviewer tiers: bronze=1, silver=2, gold=3. Three achievements -> gold.
    _grant(plain_user, "library-review", count=3)
    plain_user = _reload(plain_user)

    assert display.held_badges(plain_user)[0].tier.rank == TierRank.GOLD
    assert (
        UserBadge.objects.filter(
            user=plain_user, badge=badge, revoked_at__isnull=True
        ).count()
        == 3
    )


def test_featured_badge_honours_the_members_choice(plain_user):
    """A picked badge outranks the top tier - that is the point of picking."""
    _grant(plain_user, "library-review", count=3)  # bronze, silver and gold
    _pick(plain_user, TierRank.BRONZE)
    plain_user = _reload(plain_user)

    assert display.held_badges(plain_user)[0].tier.rank == TierRank.GOLD
    assert display.featured_badge(plain_user)["icon"] == BadgeToken.TIER_1


def test_badges_held_but_none_picked_features_nothing(plain_user):
    """No pick, no featured badge - even holding several.

    Featuring the top rank for a member who never chose would publish a choice
    they did not make. The cards list is unaffected; only the headline is a pick.
    """
    _grant(plain_user, "library-review", count=3)
    plain_user = _reload(plain_user)

    assert plain_user.display_badge_id is None
    assert display.held_badges(plain_user) != []
    assert display.featured_badge(plain_user) is None
    assert plain_user.featured_badge is None
    assert plain_user.to_v3_profile_dict()["badge"] is None
    assert len(display.badge_cards(plain_user)) == 3


def test_featured_badge_shows_nothing_when_the_choice_is_revoked(plain_user):
    """A revoked pick features nothing rather than silently moving to another."""
    _grant(plain_user, "library-review", count=3)
    picked = _pick(plain_user, TierRank.BRONZE)
    UserBadge.objects.filter(pk=picked.pk).update(revoked_at="2026-01-01T00:00:00Z")
    plain_user = _reload(plain_user)

    assert display.held_badges(plain_user) != []
    assert display.featured_badge(plain_user) is None


def test_a_chosen_badge_is_still_hidden_by_hide_badges(plain_user):
    """Picking a badge is not a way to publish badges the member hid."""
    _grant(plain_user, "library-review", count=3)
    _pick(plain_user, TierRank.BRONZE)
    plain_user.hide_badges = True
    plain_user.save(update_fields=["hide_badges"])
    plain_user = _reload(plain_user)

    assert display.featured_badge(plain_user) is None
    assert display.featured_badge(plain_user, include_hidden=True)["icon"] == (
        BadgeToken.TIER_1
    )


def test_the_chosen_badge_costs_no_extra_query(plain_user, django_assert_num_queries):
    """Reading the pick must not reintroduce a query per rendered user."""
    from users.models import User

    _grant(plain_user, "library-review", count=3)
    _pick(plain_user, TierRank.BRONZE)

    user = User.objects.prefetch_related(display.active_badges_prefetch()).get(
        pk=plain_user.pk
    )
    with django_assert_num_queries(0):
        assert display.featured_badge(user)["icon"] == BadgeToken.TIER_1


def test_rank_beats_threshold_across_badge_types(plain_user):
    """A higher rank wins even when another badge has a larger threshold.

    Reviewer diamond needs only 5 achievements while commits silver needs 12,
    so sorting by raw threshold would wrongly feature the silver.
    """
    _grant(plain_user, "library-review", count=5)  # reviewer diamond
    _grant(plain_user, "code-commits", count=12)  # commits silver
    plain_user = _reload(plain_user)

    held = display.held_badges(plain_user)
    assert held[0].tier.rank == TierRank.DIAMOND
    orders = [TierRank(badge.tier.rank).order for badge in held]
    assert orders == sorted(orders, reverse=True)


def test_replaced_tier_does_not_duplicate_a_rank(plain_user):
    """Grandfathering can leave two rows for one rank; show the rank once.

    Retiring a tier deliberately keeps the badges awarded against it, so a user
    who also qualifies under the replacement holds both rows and the badges card
    would list the same medal twice.
    """
    from badges.models import BadgeTier
    from badges.services import recalculate_badges

    achievement = Achievement.objects.get(slug="library-review")
    _grant(plain_user, "library-review", count=5)
    badge = achievement.badges.first()
    bronze = badge.tiers.get(rank=TierRank.BRONZE)
    bronze.is_active = False
    bronze.save(update_fields=["is_active"])
    BadgeTier.objects.create(badge=badge, rank=TierRank.BRONZE, threshold=5)
    recalculate_badges(plain_user.pk, achievement.pk)
    plain_user = _reload(plain_user)

    ranks = [held.tier.rank for held in display.held_badges(plain_user)]

    assert len(ranks) == len(set(ranks))
    assert ranks.count(TierRank.BRONZE) == 1


def test_hide_badges_suppresses_every_public_accessor(plain_user):
    """hide_badges empties everything the public profile can reach."""
    plain_user = _feature(plain_user, "library-authoring")
    assert plain_user.featured_badge is not None

    plain_user.hide_badges = True
    plain_user.save(update_fields=["hide_badges"])
    plain_user = _reload(plain_user)

    assert display.held_badges(plain_user) == []
    assert display.featured_badge(plain_user) is None
    assert display.badge_cards(plain_user) == []
    assert plain_user.featured_badge is None
    assert plain_user.to_v3_profile_dict()["badge"] is None


def test_hide_badges_can_be_bypassed_for_the_owner(plain_user):
    """include_hidden lets the owner still see badges they have hidden."""
    plain_user = _feature(plain_user, "library-authoring")
    plain_user.hide_badges = True
    plain_user.save(update_fields=["hide_badges"])
    plain_user = _reload(plain_user)

    assert display.featured_badge(plain_user, include_hidden=True)["icon"] == (
        BadgeToken.TIER_1
    )
    assert len(display.badge_cards(plain_user, include_hidden=True)) == 1


def test_revoked_badges_are_not_displayed(plain_user):
    """A revoked badge disappears from the profile without being deleted."""
    _grant(plain_user, "library-authoring")
    UserBadge.objects.filter(user=plain_user).update(revoked_at="2026-01-01T00:00:00Z")
    plain_user = _reload(plain_user)

    assert display.held_badges(plain_user) == []
    assert UserBadge.objects.filter(user=plain_user).exists()


def test_held_badges_uses_the_prefetch_cache(plain_user, django_assert_num_queries):
    """Callers rendering many users must be able to avoid a query each."""
    from users.models import User

    plain_user = _feature(plain_user, "library-authoring")

    user = User.objects.prefetch_related(display.active_badges_prefetch()).get(
        pk=plain_user.pk
    )
    with django_assert_num_queries(0):
        assert len(display.held_badges(user)) == 1
        assert display.featured_badge(user)["icon"] == BadgeToken.TIER_1


def test_news_author_prefetch_covers_the_whole_card(
    plain_user, django_assert_num_queries
):
    """A news page's author cards must cost no query each once prefetched.

    ``Prefetch("author", ...)`` looks like it does this and does not: the same
    queryset select_relates the author, so Django finds the foreign key cached,
    skips the prefetch, and drops the nested badge prefetch with it. Asserted
    against the view's own tuple, through the function that reads it, because the
    failure is silent - the page renders correctly and just queries per card.
    """
    from news.models import Entry
    from news.views import EntryDetailView
    from users.profile_cards import user_profile_card

    plain_user = _feature(plain_user, "library-authoring")
    for index in range(3):
        Entry.objects.create(
            title=f"Post {index}",
            slug=f"post-{index}",
            author=plain_user,
            publish_at=timezone.now(),
        )

    entries = list(
        Entry.objects.select_related("author").prefetch_related(
            *EntryDetailView.AUTHOR_PREFETCH
        )
    )

    assert len(entries) == 3
    with django_assert_num_queries(0):
        cards = [user_profile_card(entry.author) for entry in entries]
    assert {card["badge_label"] for card in cards} == {"Library Author"}


def test_community_recent_post_badge_query_is_constant(plain_user):
    """The community page loads author badges once, not once per post card."""
    from core.views import build_recent_community_posts

    plain_user = _feature(plain_user, "library-authoring")
    _published_entry(plain_user, 0)

    one_card, one_badge_query = _badge_queries(build_recent_community_posts)

    for index in range(1, 4):
        author = baker.make("users.User", email=f"community-{index}@example.com")
        _feature(author, "library-authoring")
        _published_entry(author, index)
    four_cards, four_badge_queries = _badge_queries(build_recent_community_posts)

    assert one_badge_query == four_badge_queries == 1
    assert len(one_card) == 1
    assert len(four_cards) == 4
    assert {card["author"]["badge_label"] for card in four_cards} == {"Library Author"}


def test_homepage_ranked_post_badge_query_is_constant(plain_user):
    """The V3 homepage loads ranked-post author badges in one query."""
    from ak.homepage import build_community_posts

    plain_user = _feature(plain_user, "library-authoring")
    _published_entry(plain_user, 0)

    one_card, one_badge_query = _badge_queries(build_community_posts)

    for index in range(1, 4):
        author = baker.make("users.User", email=f"homepage-{index}@example.com")
        _feature(author, "library-authoring")
        _published_entry(author, index)
    four_cards, four_badge_queries = _badge_queries(build_community_posts)

    assert one_badge_query == four_badge_queries == 1
    assert len(one_card) == 1
    assert len(four_cards) == 4
    assert {card["author"]["badge_label"] for card in four_cards} == {"Library Author"}


def test_library_intro_badge_query_is_constant(library_version, plain_user):
    """The homepage library intro prefetches its User authors and maintainers."""
    from libraries.utils import build_library_intro_context

    plain_user = _feature(plain_user, "library-authoring")
    library_version.authors.add(plain_user)

    one_card, one_badge_query = _badge_queries(
        lambda: build_library_intro_context(library_version)
    )

    for index in range(1, 4):
        user = baker.make("users.User", email=f"library-intro-{index}@example.com")
        _feature(user, "library-authoring")
        relation = library_version.authors if index % 2 else library_version.maintainers
        relation.add(user)
    four_cards, four_badge_queries = _badge_queries(
        lambda: build_library_intro_context(library_version)
    )

    assert one_badge_query == four_badge_queries == 1
    assert len(one_card["authors"]) == 1
    assert len(four_cards["authors"]) == 4
    assert {card["badge_label"] for card in four_cards["authors"]} == {"Library Author"}


def test_library_detail_user_badge_query_is_constant(library_version, plain_user):
    """The detail-page User origins prefetch badges before card conversion."""
    from libraries.mixins import ContributorMixin

    plain_user = _feature(plain_user, "library-authoring")
    library_version.authors.add(plain_user)
    mixin = ContributorMixin()

    def author_cards():
        authors = mixin.get_related(library_version, "authors")
        return [author.to_v3_profile_dict("Author") for author in authors]

    one_card, one_badge_query = _badge_queries(author_cards)

    for index in range(1, 4):
        user = baker.make("users.User", email=f"library-detail-{index}@example.com")
        _feature(user, "library-authoring")
        library_version.authors.add(user)
    four_cards, four_badge_queries = _badge_queries(author_cards)

    assert one_badge_query == four_badge_queries == 1
    assert len(one_card) == 1
    assert len(four_cards) == 4
    assert {card["badge_label"] for card in four_cards} == {"Library Author"}


@waffle.testutils.override_flag("v3", active=True)
def test_own_profile_page_shows_hidden_badges(plain_user, tp):
    """The owner's own v3 profile still renders badges they have hidden."""
    plain_user = _feature(plain_user, "library-authoring")
    plain_user.hide_badges = True
    plain_user.save(update_fields=["hide_badges"])

    tp.client.force_login(plain_user)
    response = tp.get(tp.reverse("profile-account"))

    tp.response_200(response)
    assert response.context["user_info"]["featured_badge"]["icon"] == BadgeToken.TIER_1
    assert len(response.context["profile_badges"]) == 1


def test_user_profile_card_emits_the_keys_the_template_reads(plain_user):
    """_user_profile.html reads `badge`/`badge_label`, not `badge_url`."""
    from users.profile_cards import user_profile_card

    plain_user = _feature(plain_user, "library-authoring")  # bronze (threshold 1)

    card = user_profile_card(plain_user)

    assert card["badge"] == BadgeToken.TIER_1
    assert card["badge_label"] == "Library Author"
    assert "badge_url" not in card


def test_user_profile_card_without_badges(plain_user):
    """A badgeless user renders no badge rather than a placeholder medal."""
    from users.profile_cards import user_profile_card

    card = user_profile_card(plain_user)

    assert card["badge"] is None
    assert card["badge_label"] == ""


def test_v3_profile_dict_carries_the_badge_label(plain_user):
    """_user_profile.html shows the badge label on hover, so it must be set."""
    plain_user = _feature(plain_user, "library-authoring")

    profile = plain_user.to_v3_profile_dict()

    assert profile["badge"] == BadgeToken.TIER_1
    assert profile["badge_label"] == "Library Author"


@waffle.testutils.override_flag("v3", active=True)
def test_v3_news_list_renders_a_real_badge_for_the_sidebar_user(plain_user, tp):
    """The sidebar card showed a hardcoded "Bug Catcher" label for everyone."""
    plain_user = _feature(plain_user, "library-authoring")
    tp.client.force_login(plain_user)

    response = tp.get(tp.reverse("news"))

    tp.response_200(response)
    body = response.content.decode()
    assert "Bug Catcher" not in body
    assert "Library Author" in body


@waffle.testutils.override_flag("v3", active=True)
def test_v3_news_list_renders_no_badge_without_one(plain_user, tp):
    """A badgeless user gets no badge chip rather than a placeholder label."""
    tp.client.force_login(plain_user)

    response = tp.get(tp.reverse("news"))

    tp.response_200(response)
    assert "user-card__badge" not in response.content.decode()


@waffle.testutils.override_flag("v3", active=True)
def test_own_profile_page_renders_without_badges(plain_user, tp):
    """The empty state must render; featured_badge is None, not a blank dict."""
    tp.client.force_login(plain_user)

    response = tp.get(tp.reverse("profile-account"))

    tp.response_200(response)
    assert response.context["user_info"]["featured_badge"] is None
    assert response.context["profile_badges"] == []
    assert "badges-card__empty" in response.content.decode()
