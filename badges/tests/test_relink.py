"""Tests for re-pointing a grant at evidence that was created again.

The commit importer's destructive mode deletes every row for a library and inserts
the same commits back under new ids. Discarding the grants instead of re-pointing
them revokes the badges they justify, records those revocations permanently, and
re-earns the badges dated today on the next sync - so a re-import would rewrite
history that nothing actually changed.
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from badges.models import Achievement, SourceType, UserAchievement
from badges.services import relink_source_achievements
from badges.tests.fixtures import grant_from_source

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _catalogue(catalogue):
    """Seed the real achievement catalogue for every test in this module."""


def _commit(user, sha):
    """One commit attributed to ``user``."""
    author = baker.make("libraries.CommitAuthor", user=user)
    return baker.make("libraries.Commit", author=author, sha=sha)


def test_a_grant_follows_its_evidence_to_the_new_row(plain_user):
    """The sha is what survives the swap, so the pointer is rebuilt from it."""
    from libraries.models import Commit

    achievement = Achievement.objects.get(slug="code-commits")
    old = _commit(plain_user, "cafe1234")
    grant_from_source(plain_user, achievement, old, dedup_info="cafe1234")
    replacement = baker.make("libraries.Commit", author=old.author, sha="cafe1234")
    assert replacement.pk != old.pk

    assert relink_source_achievements(Commit, {"cafe1234": replacement.pk}) == 1

    grant = UserAchievement.objects.get(dedup_info="cafe1234")
    assert grant.source_object_id == replacement.pk


def test_a_manual_grant_is_left_where_the_admin_put_it(plain_user):
    """The filter is on source type as well as key.

    An admin's row is not the engine's to move, even in the odd case where it
    carries a key: only automatic grants are derived from a source.
    """
    from libraries.models import Commit

    commit = _commit(plain_user, "cafe1234")
    manual = UserAchievement.objects.create(
        user=plain_user,
        achievement=Achievement.objects.get(slug="code-commits"),
        source_type=SourceType.MANUAL,
        source_content_type=ContentType.objects.get_for_model(Commit),
        source_object_id=commit.pk,
        dedup_info="cafe1234",
    )

    assert relink_source_achievements(Commit, {"cafe1234": commit.pk + 1_000}) == 0

    manual.refresh_from_db()
    assert manual.source_object_id == commit.pk


def test_a_grant_for_another_model_is_left_alone(plain_user):
    """Keyed on content type too, because key strings are per source.

    Nothing stops a review fingerprint colliding with a sha one day, and a
    commit re-import has no business touching a review's grant either way.
    """
    from libraries.models import Commit

    review = baker.make(
        "versions.Review",
        submission="Boost.MP11",
        submitter_raw="Peter Dimov",
        review_dates="April 1-10, 2017",
    )
    grant_from_source(
        plain_user,
        Achievement.objects.get(slug="library-review"),
        review,
        dedup_info="cafe1234",
    )

    assert relink_source_achievements(Commit, {"cafe1234": 999_999}) == 0

    assert UserAchievement.objects.get(dedup_info="cafe1234").source_object_id == (
        review.pk
    )


def test_a_pointer_that_has_not_moved_is_not_rewritten(plain_user):
    """A non-destructive import re-creates nothing, so there is nothing to move."""
    from libraries.models import Commit

    commit = _commit(plain_user, "cafe1234")
    grant_from_source(
        plain_user,
        Achievement.objects.get(slug="code-commits"),
        commit,
        dedup_info="cafe1234",
    )

    assert relink_source_achievements(Commit, {"cafe1234": commit.pk}) == 0


def test_an_empty_map_touches_the_database_not_at_all(django_assert_num_queries):
    """The importer calls this on every clean run, including ones with no grants."""
    from libraries.models import Commit

    with django_assert_num_queries(0):
        assert relink_source_achievements(Commit, {}) == 0
