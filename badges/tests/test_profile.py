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


def test_badges_held_but_none_picked_features_the_highest(plain_user):
    """No pick features the top rank held, per issue #2702.

    This reverses the earlier rule, which featured nothing without a deliberate
    save. Almost nobody makes that save, so a member with a full card of badges
    showed none beside their name and it read as a bug.
    """
    _grant(plain_user, "library-review", count=3)  # bronze, silver and gold
    plain_user = _reload(plain_user)

    assert plain_user.display_badge_id is None
    assert display.featured_badge(plain_user)["icon"] == BadgeToken.TIER_3
    assert plain_user.featured_badge["icon"] == BadgeToken.TIER_3
    assert plain_user.to_v3_profile_dict()["badge"] == BadgeToken.TIER_3
    # One badge climbed three rungs is one card, not three.
    assert len(display.badge_cards(plain_user)) == 1


def test_a_revoked_choice_falls_back_to_the_highest_held(plain_user):
    """A revoked pick is no pick, so the default applies rather than nothing.

    A revocation that left the name bare while the badges card stayed full is
    the same reported bug by another route.
    """
    _grant(plain_user, "library-review", count=3)
    picked = _pick(plain_user, TierRank.BRONZE)
    UserBadge.objects.filter(pk=picked.pk).update(revoked_at="2026-01-01T00:00:00Z")
    plain_user = _reload(plain_user)

    assert display.featured_badge(plain_user)["icon"] == BadgeToken.TIER_3


def test_the_picked_badge_leads_the_card(plain_user):
    """A pick is how a member says which badge represents them.

    Rank alone buried it: a pick is usually not the member's top rank, so the
    badge they chose to feature turned up mid-list and looked ignored.
    """
    _grant(plain_user, "library-review", count=5)  # reviewer, up to diamond
    _grant(plain_user, "library-authoring", count=1)  # library author, bronze
    _pick(plain_user, TierRank.BRONZE, slug="library-authoring")
    plain_user = _reload(plain_user)

    names = [card["name"] for card in display.badge_cards(plain_user)]

    assert names == ["Library Author", "Reviewer"]


def test_the_badges_behind_the_pick_keep_rank_order(plain_user):
    """Only the picked badge moves; the rest are still ranked."""
    _grant(plain_user, "library-review", count=5)  # diamond
    _grant(plain_user, "code-commits", count=12)  # silver
    _grant(plain_user, "library-authoring", count=1)  # bronze
    _pick(plain_user, TierRank.BRONZE, slug="library-authoring")
    plain_user = _reload(plain_user)

    names = [card["name"] for card in display.badge_cards(plain_user)]

    assert names == ["Library Author", "Reviewer", "Commits Master"]


def test_a_pick_below_the_top_rung_still_leads(plain_user):
    """The card shows one row per badge, and that row leads on a pick.

    The picker only offers the rung a member has reached, but a stored pick can
    fall behind when they climb. It is still the badge they chose.
    """
    _grant(plain_user, "library-review", count=5)
    _grant(plain_user, "code-commits", count=12)
    _pick(plain_user, TierRank.BRONZE)  # reviewer bronze, three rungs down
    plain_user = _reload(plain_user)

    cards = display.badge_cards(plain_user)

    assert cards[0]["name"] == "Reviewer"
    # The row is the rung reached, not the rung picked.
    assert cards[0]["icon"] == BadgeToken.TIER_5


def test_only_the_highest_rung_of_a_badge_gets_a_card(plain_user):
    """Climbing keeps the rungs below, and the card listed every one of them.

    Eleven rows for six badges on the profile in issue #2702. The rungs below
    stay in ``held_badges``, which is history and what a pick is checked against.
    """
    _grant(plain_user, "library-review", count=3)
    _grant(plain_user, "code-commits", count=12)
    plain_user = _reload(plain_user)

    cards = display.badge_cards(plain_user)

    assert len(display.held_badges(plain_user)) > len(cards)
    assert [card["name"] for card in cards] == ["Reviewer", "Commits Master"]


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
    assert plain_user.badge is None
    assert plain_user.badge_label == ""
    assert plain_user.to_v3_profile_dict()["badge"] is None


def test_an_unclaimed_stub_shows_no_badges(plain_user):
    """Stubs stand in for historical authors and nobody can log into them, so a
    badge on one credits a placeholder rather than a member."""
    plain_user = _feature(plain_user, "library-authoring")
    assert plain_user.featured_badge is not None

    plain_user.claimed = False
    plain_user.save(update_fields=["claimed"])
    plain_user = _reload(plain_user)

    assert display.held_badges(plain_user) == []
    assert display.featured_badge(plain_user) is None
    assert display.badge_cards(plain_user) == []
    assert plain_user.featured_badge is None
    assert plain_user.badge is None
    assert plain_user.badge_label == ""
    assert plain_user.to_v3_profile_dict()["badge"] is None


def test_an_unclaimed_stub_is_not_bypassed_by_include_hidden(plain_user):
    """`include_hidden` lets an owner see their own hidden badges. A stub has no
    owner to be looking, so it is the one case the bypass must not reach."""
    plain_user = _feature(plain_user, "library-authoring")
    plain_user.claimed = False
    plain_user.save(update_fields=["claimed"])
    plain_user = _reload(plain_user)

    assert display.held_badges(plain_user, include_hidden=True) == []
    assert display.featured_badge(plain_user, include_hidden=True) is None
    assert display.badge_cards(plain_user, include_hidden=True) == []


def test_claiming_the_account_restores_its_badges(plain_user):
    """The badges were never revoked, only withheld while the stub was unowned."""
    plain_user = _feature(plain_user, "library-authoring")
    plain_user.claimed = False
    plain_user.save(update_fields=["claimed"])
    assert _reload(plain_user).featured_badge is None

    _reload(plain_user).claim()

    assert _reload(plain_user).featured_badge["icon"] == BadgeToken.TIER_1


def test_a_contributor_linked_to_an_unclaimed_stub_shows_no_badge(plain_user):
    """The case this filter exists for: contributor rows resolve their badge
    through the linked account, and some of those accounts are importer stubs."""
    plain_user = _feature(plain_user, "library-authoring")
    author = _commit_author(user=plain_user)
    assert author.to_v3_profile_dict("Contributor")["badge"] == BadgeToken.TIER_1

    plain_user.claimed = False
    plain_user.save(update_fields=["claimed"])
    author.refresh_from_db()

    profile = author.to_v3_profile_dict("Contributor")

    assert profile["badge"] is None
    assert profile["badge_label"] == ""


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
        cards = [entry.author.to_v3_profile_dict() for entry in entries]
    assert {card["badge_label"] for card in cards} == {"Library Author"}


def test_community_recent_post_badge_query_is_constant(plain_user):
    """The community page loads author badges once, not once per post card.

    The cards come from `get_latest_post_cards`, which reads legacy entries
    while the `v3` flag is off and Wagtail posts while it is on. Both arms
    prefetch the same way; this covers the entry arm the fixtures build.
    """
    from news.services import get_latest_post_cards

    plain_user = _feature(plain_user, "library-authoring")
    _published_entry(plain_user, 0)

    def recent_community_posts():
        return get_latest_post_cards(limit=4)

    one_card, one_badge_query = _badge_queries(recent_community_posts)

    for index in range(1, 4):
        author = baker.make("users.User", email=f"community-{index}@example.com")
        _feature(author, "library-authoring")
        _published_entry(author, index)
    four_cards, four_badge_queries = _badge_queries(recent_community_posts)

    assert one_badge_query == four_badge_queries == 1
    assert len(one_card) == 1
    assert len(four_cards) == 4
    assert {card["author"]["badge_label"] for card in four_cards} == {"Library Author"}


@waffle.testutils.override_flag("v3", active=True)
def test_homepage_ranked_post_badge_query_is_constant(plain_user, make_post_page):
    """The V3 homepage loads ranked-post author badges in one query.

    The ranked feed reads the Wagtail post tree rather than legacy entries,
    so the cards are built from `PostPage.owner`.
    """
    from ak.homepage import build_community_posts

    plain_user = _feature(plain_user, "library-authoring")
    make_post_page(title="Post 0", owner=plain_user)

    one_card, one_badge_query = _badge_queries(build_community_posts)

    for index in range(1, 4):
        author = baker.make("users.User", email=f"homepage-{index}@example.com")
        _feature(author, "library-authoring")
        make_post_page(title=f"Post {index}", owner=author)
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


def _commit_author(user=None, **kwargs):
    """A human commit author, optionally linked to a Boost account."""
    return baker.make("libraries.CommitAuthor", user=user, is_bot=False, **kwargs)


def test_a_commit_author_shows_its_linked_members_badge(plain_user):
    """Release and library contributor rows are CommitAuthors, not Users, and
    their card hardcoded no badge even for a linked account (#2708)."""
    plain_user = _feature(plain_user, "library-authoring")
    author = _commit_author(user=plain_user)

    profile = author.to_v3_profile_dict("Contributor")

    assert profile["badge"] == BadgeToken.TIER_1
    assert profile["badge_label"] == "Library Author"


def test_a_git_only_contributor_has_no_badge():
    """Badges are awarded to the account, so an unlinked git identity has none.

    The empty case the template skips, not a placeholder medal.
    """
    profile = _commit_author().to_v3_profile_dict("Contributor")

    assert profile["badge"] is None
    assert profile["badge_label"] == ""


def test_a_contributor_matched_by_github_username_keeps_its_badge(plain_user):
    """`prefer_boost_profile_links` repoints a contributor at their Boost
    profile off the GitHub username when the commit email never matched. The
    badge has to travel with the link, or the same member renders as an
    account beside a badgeless stranger."""
    from libraries.utils import prefer_boost_profile_links

    plain_user.github_username = "vinniefalco"
    plain_user.claimed = True
    plain_user.save(update_fields=["github_username", "claimed"])
    plain_user = _feature(plain_user, "library-authoring")
    author = _commit_author(github_profile_url="https://github.com/VinnieFalco")

    profile = author.to_v3_profile_dict("Contributor")
    assert profile["badge"] is None, "unlinked, so nothing to show yet"

    prefer_boost_profile_links([profile])

    assert profile["profile_url"] == plain_user.profile_url
    assert profile["badge"] == BadgeToken.TIER_1
    assert profile["badge_label"] == "Library Author"


def test_release_contributor_badge_query_is_constant(plain_user, version):
    """The downloads page loads contributor badges once, not once per row.

    `user` is select_related on the contributor queryset, so the badges have to
    be asked for through the path - see `badges.display.active_badges_prefetch`.
    """
    from versions.views import VersionDetail

    def add_contributor(user):
        """One commit against this release, authored by `user`'s git identity."""
        baker.make(
            "libraries.Commit",
            library_version=baker.make("libraries.LibraryVersion", version=version),
            author=_commit_author(user=user),
        )

    plain_user = _feature(plain_user, "library-authoring")
    add_contributor(plain_user)

    def contributors():
        return VersionDetail().get_v3_contributors(version)

    one_row, one_badge_query = _badge_queries(contributors)

    for index in range(1, 4):
        user = baker.make("users.User", email=f"release-{index}@example.com")
        add_contributor(_feature(user, "library-authoring"))
    four_rows, four_badge_queries = _badge_queries(contributors)

    assert one_badge_query == four_badge_queries == 1
    assert len(one_row) == 1
    assert len(four_rows) == 4
    assert {row["badge_label"] for row in four_rows} == {"Library Author"}


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


def test_v3_profile_dict_without_badges(plain_user):
    """A badgeless user renders no badge rather than a placeholder medal."""
    profile = plain_user.to_v3_profile_dict()

    assert profile["badge"] is None
    assert profile["badge_label"] == ""


def test_v3_profile_dict_carries_the_badge_label(plain_user):
    """_user_profile.html shows the badge label on hover, so it must be set."""
    plain_user = _feature(plain_user, "library-authoring")

    profile = plain_user.to_v3_profile_dict()

    assert profile["badge"] == BadgeToken.TIER_1
    assert profile["badge_label"] == "Library Author"
    assert "badge_url" not in profile


@waffle.testutils.override_flag("v3", active=True)
def test_v3_news_list_renders_a_real_badge_for_the_sidebar_user(
    plain_user, tp, post_index_page, wagtail_site
):
    """The sidebar card showed a hardcoded "Bug Catcher" label for everyone.

    `post_index_page` because the v3 feed is served by the index page that owns
    the posts; without one /news/ falls back to the legacy list, which has no
    sidebar card at all and would pass the "Bug Catcher" half of this vacuously.
    """
    plain_user = _feature(plain_user, "library-authoring")
    tp.client.force_login(plain_user)

    response = tp.get(post_index_page.get_url())

    tp.response_200(response)
    body = response.content.decode()
    assert "Bug Catcher" not in body
    assert "Library Author" in body


@waffle.testutils.override_flag("v3", active=True)
def test_v3_news_list_renders_no_badge_without_one(
    plain_user, tp, post_index_page, wagtail_site
):
    """A badgeless user gets no badge chip rather than a placeholder label."""
    tp.client.force_login(plain_user)

    response = tp.get(post_index_page.get_url())

    tp.response_200(response)
    assert "user-card__badge" not in response.content.decode()


def test_a_user_fills_the_profile_component_badge_slots(plain_user):
    """`_user_profile.html` reads `badge` and `badge_label` off whatever it is
    handed, and the v3 post cards hand it a User rather than the dict
    `to_v3_profile_dict` builds. Both shapes have to answer the same (#2708)."""
    assert plain_user.badge is None
    assert plain_user.badge_label == ""

    plain_user = _feature(plain_user, "library-authoring")
    profile = plain_user.to_v3_profile_dict()

    assert plain_user.badge == BadgeToken.TIER_1 == profile["badge"]
    assert plain_user.badge_label == "Library Author" == profile["badge_label"]


@waffle.testutils.override_flag("v3", active=True)
def test_v3_news_list_renders_the_author_badge_on_a_post_card(
    plain_user, tp, post_index_page, wagtail_site, make_post_page
):
    """The feed lists PostPages, whose `author` is the owning User.

    Anonymous on purpose: the sidebar card renders the same label for a signed-in
    member, and would pass this whether or not the author card had a badge.
    """
    plain_user.display_name = "Vinnie Falco"
    plain_user.save(update_fields=["display_name"])
    plain_user = _feature(plain_user, "library-authoring")
    make_post_page(title="A Post", owner=plain_user)

    response = tp.get(post_index_page.get_url())

    tp.response_200(response)
    body = response.content.decode()
    assert "user-card__badge" not in body, "signed out, so no sidebar card badge"
    assert 'aria-label="Library Author"' in body
    assert "badge-v3--tier-1" in body


@waffle.testutils.override_flag("v3", active=True)
def test_v3_post_detail_renders_the_author_badge(
    plain_user, tp, wagtail_site, make_post_page
):
    """The detail page's own header reads `post_author`, which is the same User."""
    plain_user.display_name = "Vinnie Falco"
    plain_user.save(update_fields=["display_name"])
    plain_user = _feature(plain_user, "library-authoring")
    post = make_post_page(title="A Post", owner=plain_user)

    response = tp.get(post.get_url())

    tp.response_200(response)
    body = response.content.decode()
    assert 'aria-label="Library Author"' in body
    assert "badge-v3--tier-1" in body


@waffle.testutils.override_flag("v3", active=True)
def test_v3_post_detail_badge_query_is_constant(
    plain_user, tp, wagtail_site, make_post_page
):
    """A post detail page reads three sets of badges: the author's, the next
    post's and the related posts'. None may grow with how many posts exist.

    Wagtail resolves the page being viewed by itself, so its author is not part
    of the prefetched queryset the next and related cards come from. Prefetching
    that one user would cost exactly the query it saves, so the count is pinned
    here instead of adding a prefetch that buys nothing.
    """
    plain_user = _feature(plain_user, "library-authoring")
    post = make_post_page(title="Main Post", owner=plain_user)
    for index in range(3):
        author = baker.make("users.User", email=f"detail-a-{index}@example.com")
        make_post_page(
            title=f"Related A {index}", owner=_feature(author, "library-authoring")
        )

    def detail():
        return tp.get(post.get_url())

    few, few_badge_queries = _badge_queries(detail)

    for index in range(7):
        author = baker.make("users.User", email=f"detail-b-{index}@example.com")
        make_post_page(
            title=f"Related B {index}", owner=_feature(author, "library-authoring")
        )
    many, many_badge_queries = _badge_queries(detail)

    tp.response_200(few)
    tp.response_200(many)
    assert few_badge_queries == many_badge_queries == 3


@waffle.testutils.override_flag("v3", active=True)
def test_v3_feed_author_badge_query_is_constant(
    plain_user, tp, post_index_page, wagtail_site, make_post_page
):
    """The feed loads author badges once, not once per card.

    `owner` is select_related, so the badges have to be asked for through the
    path - see `badges.display.active_badges_prefetch`.
    """
    plain_user = _feature(plain_user, "library-authoring")
    make_post_page(title="Post 0", owner=plain_user)

    def feed():
        return tp.get(post_index_page.get_url())

    one_post, one_badge_query = _badge_queries(feed)

    for index in range(1, 4):
        author = baker.make("users.User", email=f"feed-{index}@example.com")
        author = _feature(author, "library-authoring")
        make_post_page(title=f"Post {index}", owner=author)
    four_posts, four_badge_queries = _badge_queries(feed)

    assert one_badge_query == four_badge_queries == 1
    assert len(one_post.context["entry_list"]) == 1
    assert len(four_posts.context["entry_list"]) == 4


@waffle.testutils.override_flag("v3", active=True)
def test_own_profile_page_renders_without_badges(plain_user, tp):
    """The empty state must render; featured_badge is None, not a blank dict."""
    tp.client.force_login(plain_user)

    response = tp.get(tp.reverse("profile-account"))

    tp.response_200(response)
    assert response.context["user_info"]["featured_badge"] is None
    assert response.context["profile_badges"] == []
    assert "badges-card__empty" in response.content.decode()
