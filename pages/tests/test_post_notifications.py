"""The "new posts" dot on the Posts nav item.

State lives entirely in the cache: one key naming the most recently published
post, one key per user naming the post they last acknowledged. The dot is on
while those disagree.
"""

import pytest
from django.core.cache import cache
from waffle.testutils import override_flag

from core.context_processors import header_context
from pages import notifications
from pages.models import PostPage
from pages.notifications import (
    LATEST_POST_KEY,
    has_unread_posts,
    latest_notified_post_id,
    mark_post_seen,
    mark_posts_seen,
    record_published_post,
)


@pytest.fixture(autouse=True)
def clean_notification_cache(user):
    """The suite runs against the shared Redis, so clear both keys either side."""

    def _clear():
        cache.delete(LATEST_POST_KEY)
        cache.delete(notifications._seen_key(user.pk))

    _clear()
    yield
    _clear()


def posts_nav_link(request):
    links = header_context(request)["nav_links"]
    return next(link for link in links if link.nav_id == "news")


class TestNotificationState:
    def test_no_dot_before_anything_is_published(self, user):
        assert latest_notified_post_id() is None
        assert has_unread_posts(user) is False

    def test_publishing_raises_the_dot(self, user):
        record_published_post(7)
        assert has_unread_posts(user) is True

    def test_visiting_the_feed_dismisses_it(self, user):
        record_published_post(7)
        mark_posts_seen(user)
        assert has_unread_posts(user) is False

    def test_the_next_publish_raises_it_again(self, user):
        record_published_post(7)
        mark_posts_seen(user)
        record_published_post(8)
        assert has_unread_posts(user) is True

    def test_dismissal_is_per_user(self, user, staff_user):
        record_published_post(7)
        mark_posts_seen(user)
        assert has_unread_posts(staff_user) is True
        cache.delete(notifications._seen_key(staff_user.pk))

    def test_a_publish_out_of_id_order_still_raises_it(self, user):
        """An older draft approved after a newer one is still a new post."""
        record_published_post(8)
        mark_posts_seen(user)
        record_published_post(7)
        assert has_unread_posts(user) is True

    def test_anonymous_visitors_never_see_it(self):
        from django.contrib.auth.models import AnonymousUser

        record_published_post(7)
        assert has_unread_posts(AnonymousUser()) is False
        assert has_unread_posts(None) is False

    def test_reading_the_newest_post_dismisses_it(self, user):
        record_published_post(7)
        mark_post_seen(user, 7)
        assert has_unread_posts(user) is False

    def test_reading_an_older_post_leaves_it_alone(self, user):
        record_published_post(7)
        mark_post_seen(user, 6)
        assert has_unread_posts(user) is True


@pytest.mark.django_db
class TestPublishSignal:
    def _publish(self, page):
        """Publish the way Wagtail's moderation workflow does, minus the perms."""
        page.save_revision().publish()
        page.refresh_from_db()

    def test_a_first_publish_raises_the_dot(self, post_index_page, user):
        page = PostPage(
            title="Fresh",
            content=[("news", "Body")],
            owner=user,
            summary="A summary",
        )
        post_index_page.add_child(instance=page)
        page.live = False
        page.first_published_at = None
        page.last_published_at = None
        page.save()

        self._publish(page)

        assert latest_notified_post_id() == page.pk

    def test_editing_a_live_post_does_not(self, make_post_page, user):
        page = make_post_page(title="Already Live", owner=user)
        cache.delete(LATEST_POST_KEY)

        page.title = "Already Live, Edited"
        self._publish(page)

        assert latest_notified_post_id() is None


@pytest.mark.django_db
class TestNavLink:
    @override_flag("v3", active=True)
    def test_the_nav_link_carries_the_dot(self, rf, post_index_page, user):
        record_published_post(7)
        request = rf.get("/")
        request.user = user
        assert posts_nav_link(request).is_unread is True

    @override_flag("v3", active=True)
    def test_the_nav_link_is_plain_for_anonymous_visitors(self, rf, post_index_page):
        record_published_post(7)
        assert posts_nav_link(rf.get("/")).is_unread is False


@pytest.mark.django_db
class TestFeedDismissal:
    @override_flag("v3", active=True)
    def test_loading_the_feed_clears_the_dot(
        self, client, wagtail_site, post_index_page, user
    ):
        record_published_post(7)
        client.force_login(user)

        response = client.get("/news/")

        assert response.status_code == 200
        assert has_unread_posts(user) is False

    @override_flag("v3", active=True)
    def test_loading_the_newest_post_clears_the_dot(
        self, client, wagtail_site, make_post_page, user
    ):
        page = make_post_page(title="Newest", owner=user)
        record_published_post(page.pk)
        client.force_login(user)

        response = client.get(page.url)

        assert response.status_code == 200
        assert has_unread_posts(user) is False

    @override_flag("v3", active=True)
    def test_loading_an_older_post_leaves_the_dot(
        self, client, wagtail_site, make_post_page, user
    ):
        older = make_post_page(title="Older", owner=user)
        record_published_post(older.pk + 1)
        client.force_login(user)

        response = client.get(older.url)

        assert response.status_code == 200
        assert has_unread_posts(user) is True
