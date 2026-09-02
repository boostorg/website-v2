"""The six-hour window in which a post's author may still edit or delete it.

Measured from the *first* revision, so the clock starts when the author first
submits and is not restarted by later edits or by a moderator approving.
"""

from datetime import timedelta

import pytest
from django.utils.timezone import now

from pages.models import PostPage


@pytest.fixture
def post_with_first_revision(make_post_page, user):
    """A live post owned by `user`, with a back-datable first revision."""

    def _make_it(age=timedelta(0)):
        page = make_post_page(owner=user)
        revision = page.save_revision()
        # created_at is auto_now_add, so it has to be written after the fact.
        revision.created_at = now() - age
        revision.save(update_fields=["created_at"])
        return page

    return _make_it


class TestEditWindowRemaining:
    def test_a_fresh_post_has_nearly_the_whole_window(self, post_with_first_revision):
        page = post_with_first_revision()
        remaining = page.edit_window_remaining
        assert remaining is not None
        # Allow for the seconds the test itself takes.
        assert timedelta(hours=5, minutes=59) < remaining <= PostPage.EDIT_WINDOW

    def test_it_closes_once_the_window_has_passed(self, post_with_first_revision):
        page = post_with_first_revision(age=timedelta(hours=6, seconds=1))
        assert page.edit_window_remaining is None

    def test_it_is_measured_from_the_first_revision_not_the_latest(
        self, post_with_first_revision
    ):
        """A later edit must not hand the author a fresh six hours."""
        page = post_with_first_revision(age=timedelta(hours=5, minutes=30))
        page.save_revision()
        remaining = page.edit_window_remaining
        assert remaining is not None
        assert remaining < timedelta(minutes=31)

    def test_a_page_with_no_revisions_is_closed(self, make_post_page, user):
        page = make_post_page(owner=user)
        assert page.revisions.count() == 0
        assert page.edit_window_remaining is None

    def test_it_is_not_cached_across_reads(self, post_with_first_revision):
        """A cached_property here would freeze the value for the request."""
        page = post_with_first_revision()
        first = page.edit_window_remaining
        second = page.edit_window_remaining
        assert second <= first


class TestEditWindowRemainingDisplay:
    # Ages sit mid-minute on purpose. The display floors, so an age exactly on a
    # minute boundary drops a minute for the fraction of a second the test spends
    # between writing `created_at` and reading the value back.
    @pytest.mark.parametrize(
        "age,expected",
        [
            (timedelta(seconds=30), "5h 59m"),
            (timedelta(hours=4, minutes=59, seconds=30), "1h 0m"),
            (timedelta(hours=5, seconds=30), "59m"),
            (timedelta(hours=5, minutes=58, seconds=30), "1m"),
            # Would floor to "0m" unclamped, while still editable.
            (timedelta(hours=5, minutes=59, seconds=30), "1m"),
            (timedelta(hours=6, seconds=1), ""),
        ],
    )
    def test_it_formats_the_window(self, post_with_first_revision, age, expected):
        page = post_with_first_revision(age=age)
        assert page.edit_window_remaining_display == expected

    def test_it_never_renders_zero_minutes_while_the_window_is_open(
        self, post_with_first_revision
    ):
        page = post_with_first_revision(age=PostPage.EDIT_WINDOW - timedelta(seconds=5))
        assert page.edit_window_remaining is not None
        assert page.edit_window_remaining_display == "1m"


class TestPermissionsFollowTheWindow:
    def test_the_owner_may_edit_and_delete_inside_the_window(
        self, post_with_first_revision
    ):
        page = post_with_first_revision()
        assert page.user_can_edit(page.owner)
        assert page.user_can_delete(page.owner)

    def test_the_owner_may_not_once_it_has_closed(self, post_with_first_revision):
        page = post_with_first_revision(age=timedelta(hours=6, seconds=1))
        assert not page.user_can_edit(page.owner)
        assert not page.user_can_delete(page.owner)

    def test_a_different_user_may_not_even_inside_the_window(
        self, post_with_first_revision, staff_user
    ):
        page = post_with_first_revision()
        assert page.owner != staff_user
        assert not page.user_can_edit(staff_user)
        assert not page.user_can_delete(staff_user)
