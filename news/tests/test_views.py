import datetime

from django.utils.timezone import now
from model_bakery import baker

from ..forms import EntryForm
from ..models import Entry


def test_entry_list(tp, make_entry, regular_user, authenticated=False):
    """List published news for non authenticated users."""
    not_approved_news = make_entry(approved=False, title="needs moderation")
    yesterday_news = make_entry(
        approved=True, title="old news", publish_at=now() - datetime.timedelta(days=1)
    )
    today_news = make_entry(
        approved=True, title="current news", publish_at=now().today()
    )
    tomorrow_news = make_entry(
        approved=True,
        title="future news",
        publish_at=now() + datetime.timedelta(days=1),
    )

    if authenticated:
        tp.login(regular_user)

    response = tp.get("news")

    tp.response_200(response)
    expected = [today_news, yesterday_news]
    assert list(response.context.get("entry_list", [])) == expected

    content = str(response.content)
    for n in expected:
        assert n.get_absolute_url() in content
        assert n.title in content

    assert not_approved_news.get_absolute_url() not in content
    assert not_approved_news.title not in content
    assert tomorrow_news.get_absolute_url() not in content
    assert tomorrow_news.title not in content

    # If user is not authenticated, the Create News link should not be shown
    assert (tp.reverse("news-create") in content) == authenticated


def test_entry_list_authenticated(tp, make_entry, regular_user):
    test_entry_list(tp, make_entry, regular_user, authenticated=True)


def test_news_detail(tp, make_entry):
    """Browse details for a given news entry."""
    a_past_date = now() - datetime.timedelta(hours=10)
    news = make_entry(approved=True, publish_at=a_past_date)
    url = tp.reverse("news-detail", news.slug)

    response = tp.get(url)
    tp.response_200(response)

    content = str(response.content)
    assert news.title in content
    assert news.description in content
    assert tp.reverse("news-approve", news.slug) not in content

    # no next nor prev links
    assert "newer entries" not in content.lower()
    assert "older entries" not in content.lower()

    # create an older news
    older_date = a_past_date - datetime.timedelta(hours=1)
    older = make_entry(approved=True, publish_at=older_date)

    response = tp.get(url)
    tp.response_200(response)

    content = str(response.content)
    assert "newer entries" not in content.lower()
    assert "older entries" in content.lower()
    assert older.get_absolute_url() in content

    # create a newer news, but still older than now so it's shown
    newer_date = a_past_date + datetime.timedelta(hours=1)
    assert newer_date < now()
    newer = make_entry(approved=True, publish_at=newer_date)

    response = tp.get(url)
    tp.response_200(response)

    content = str(response.content)
    assert "newer entries" in content.lower()
    assert "older entries" in content.lower()
    assert newer.get_absolute_url() in content


def test_news_detail_404(tp):
    """No news is good news."""
    url = tp.reverse("news-detail", "not-there")
    response = tp.get(url)
    tp.response_404(response)


def test_news_detail_404_if_not_published(tp, make_entry, regular_user):
    """Details for a news entry are available if published or authored."""
    news = make_entry(published=False)
    response = tp.get(news.get_absolute_url())
    tp.response_404(response)

    # even if logged in, a regular user can not access the unpublished news
    with tp.login(regular_user):
        response = tp.get(news.get_absolute_url())
    tp.response_404(response)

    # but the entry author can access it even if unpublished
    with tp.login(news.author):
        response = tp.get(news.get_absolute_url())
    tp.response_200(response)


def test_news_detail_actions_author(tp, make_entry):
    """News entry is updatable by authors (if not approved)."""
    news = make_entry(approved=False)  # not approved entry
    with tp.login(news.author):
        response = tp.get(news.get_absolute_url())
    tp.response_200(response)

    content = str(response.content)
    assert tp.reverse("news-approve", news.slug) not in content

    news.approve(baker.make("users.User"))
    with tp.login(news.author):
        response = tp.get(news.get_absolute_url())
    tp.response_200(response)

    content = str(response.content)
    assert tp.reverse("news-approve", news.slug) not in content


def test_news_detail_actions_moderator(tp, make_entry, moderator_user):
    """Moderators can update, delete and approve a news entry."""
    news = make_entry(approved=False)  # approved entry
    with tp.login(moderator_user):
        response = tp.get(news.get_absolute_url())
    tp.response_200(response)

    content = str(response.content)
    assert tp.reverse("news-approve", news.slug) in content

    news.approve(baker.make("users.User"))
    with tp.login(moderator_user):
        response = tp.get(news.get_absolute_url())
    tp.response_200(response)

    content = str(response.content)
    assert tp.reverse("news-approve", news.slug) not in content


def test_news_create_get(tp, regular_user):
    url_name = "news-create"
    # assertLoginRequired expects a non resolved URL, that is an URL name
    # see https://github.com/revsys/django-test-plus/issues/202
    tp.assertLoginRequired(url_name)

    with tp.login(regular_user):
        # assertGoodView expects a resolved URL
        # see https://github.com/revsys/django-test-plus/issues/202
        url = tp.reverse(url_name)
        response = tp.assertGoodView(url, test_query_count=3, verbose=True)

    form = tp.get_context("form")
    assert isinstance(form, EntryForm)
    for field in form:
        tp.assertResponseContains(str(field), response)


def test_news_create_post(tp, regular_user):
    url = tp.reverse("news-create")
    data = {
        "title": "Lorem Ipsum",
        "description": "Lorem ipsum dolor sit amet, consectetur adipiscing.",
    }
    before = now()
    with tp.login(regular_user):
        response = tp.post(url, data=data, follow=True)
    after = now()

    entries = Entry.objects.filter(title=data["title"])
    assert len(entries) == 1
    entry = entries.get()
    assert entry.slug == "lorem-ipsum"
    assert entry.description == data["description"]
    assert entry.author == regular_user
    assert not entry.is_approved
    assert not entry.is_published
    # Avoid mocking `now()`, yet still ensure that the timestamps are
    # between `before` and `after`
    assert before <= entry.created_at <= after
    assert before <= entry.modified_at <= after

    tp.assertRedirects(response, entry.get_absolute_url())


def test_news_approve_get_method_not_allowed(
    tp, make_entry, regular_user, moderator_user
):
    entry = make_entry(approved=False)

    # login is required
    url_params = ("news-approve", entry.slug)
    tp.assertLoginRequired(*url_params)

    # regular users would get a 403
    with tp.login(regular_user):
        response = tp.get(*url_params)
    tp.response_403(response)

    # moderators users would get a 405 for GET
    with tp.login(moderator_user):
        response = tp.get(*url_params)
    tp.response_405(response)


def test_news_approve_post(tp, make_entry, regular_user, moderator_user):
    entry = make_entry(approved=False)
    url_params = ("news-approve", entry.slug)

    # regular users would still get a 403 on POST
    with tp.login(regular_user):
        response = tp.post(*url_params)
    tp.response_403(response)

    # moderators users can POST to the view to approve an entry
    with tp.login(moderator_user):
        before = now()
        response = tp.post(*url_params)
        after = now()

    tp.assertRedirects(response, entry.get_absolute_url())

    entry.refresh_from_db()
    assert entry.is_approved is True
    assert entry.moderator == moderator_user
    assert before <= entry.approved_at <= after
    assert before <= entry.modified_at <= after
