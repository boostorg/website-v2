import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from ak.homepage import build_community_posts

pytestmark = pytest.mark.django_db


def routing_key_queries(queries):
    return [
        query["sql"]
        for query in queries.captured_queries
        if "users_userprofileroutingkey" in query["sql"]
    ]


def test_community_posts_fetch_routing_keys_in_one_query(make_post_page):
    """Each card links its author's profile, which reads that author's routing
    keys. Those are prefetched, so more posts must not mean more queries.

    The ranked feed reads the Wagtail post tree, so the cards are built from
    `PostPage.owner` rather than from legacy entries.
    """
    for i in range(3):
        make_post_page(
            title=f"Post {i}",
            owner=baker.make("users.User", display_name=f"User {i}", image=None),
        )

    with CaptureQueriesContext(connection) as queries:
        posts = build_community_posts(limit=3)

    assert len(posts) == 3
    assert all(post["author"]["profile_url"] for post in posts)
    assert len(routing_key_queries(queries)) == 1
