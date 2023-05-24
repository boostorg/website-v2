import datetime

import pytest
from django.utils.text import slugify
from django.utils.timezone import now
from model_bakery import baker


from ..forms import BlogPostForm, EntryForm, LinkForm, PollForm, VideoForm
from ..models import BlogPost, Entry, Link, Poll, Video


NEWS_MODELS = [Entry, BlogPost, Link, Poll, Video]


@pytest.mark.parametrize(
    "url_name, model_class",
    [
        ("news", Entry),
        ("news-blogpost-list", BlogPost),
        ("news-link-list", Link),
        ("news-poll-list", Poll),
        ("news-video-list", Video),
    ],
)
def test_entry_list(
    tp, make_entry, regular_user, url_name, model_class, authenticated=False
):
    """List published news for non authenticated users."""
    not_approved_news = make_entry(
        model_class, approved=False, title="needs moderation"
    )
    yesterday_news = make_entry(
        model_class,
        approved=True,
        title="old news",
        publish_at=now() - datetime.timedelta(days=1),
    )
    today_news = make_entry(
        model_class, approved=True, title="current news", publish_at=now().today()
    )
    tomorrow_news = make_entry(
        model_class,
        approved=True,
        title="future news",
        publish_at=now() + datetime.timedelta(days=1),
    )

    if authenticated:
        tp.login(regular_user)

    # 6 queries if authenticated, 4 otherwise
    response = tp.assertGoodView(tp.reverse(url_name), test_query_count=7, verbose=True)

    expected = [today_news, yesterday_news]
    assert list(response.context.get("entry_list", [])) == expected

    content = str(response.content)
    for n in expected:
        assert n.get_absolute_url() in content
        assert n.title in content
        assert model_class.__name__.lower() in content  # this is the tag

    assert not_approved_news.get_absolute_url() not in content
    assert not_approved_news.title not in content
    assert tomorrow_news.get_absolute_url() not in content
    assert tomorrow_news.title not in content

    # If user is not authenticated, the Create News link should not be shown
    assert (tp.reverse("news-create") in content) == authenticated
    assert (tp.reverse("news-blogpost-create") in content) == authenticated
    assert (tp.reverse("news-link-create") in content) == authenticated
    assert (tp.reverse("news-poll-create") in content) == authenticated
    assert (tp.reverse("news-video-create") in content) == authenticated


@pytest.mark.parametrize(
    "url_name, model_class",
    [
        ("news", Entry),
        ("news-blogpost-list", BlogPost),
        ("news-link-list", Link),
        ("news-poll-list", Poll),
        ("news-video-list", Video),
    ],
)
def test_entry_list_authenticated(tp, make_entry, url_name, model_class, regular_user):
    test_entry_list(
        tp, make_entry, regular_user, url_name, model_class, authenticated=True
    )


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_news_detail(tp, make_entry, model_class):
    """Browse details for a given news entry."""
    a_past_date = now() - datetime.timedelta(hours=10)
    news = make_entry(model_class, approved=True, publish_at=a_past_date)
    url = tp.reverse("news-detail", news.slug)

    response = tp.get(url)
    tp.response_200(response)

    content = str(response.content)
    assert news.title in content
    assert news.content in content
    assert tp.reverse("news-approve", news.slug) not in content
    assert tp.reverse("news-delete", news.slug) not in content
    assert tp.reverse("news-update", news.slug) not in content

    # no next nor prev links
    assert "newer entries" not in content.lower()
    assert "older entries" not in content.lower()

    # create an older news, likely different type
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


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_news_detail_404_if_not_published(tp, make_entry, regular_user, model_class):
    """Details for a news entry are available if published or authored."""
    news = make_entry(model_class, published=False)
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


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_news_detail_actions_author(tp, make_entry, model_class):
    """News entry is updatable by authors (if not approved)."""
    news = make_entry(model_class, approved=False)  # not approved entry
    with tp.login(news.author):
        response = tp.get(news.get_absolute_url())
    tp.response_200(response)

    content = str(response.content)
    assert tp.reverse("news-approve", news.slug) not in content
    assert tp.reverse("news-delete", news.slug) not in content
    assert tp.reverse("news-update", news.slug) in content

    news.approve(baker.make("users.User"))
    with tp.login(news.author):
        response = tp.get(news.get_absolute_url())
    tp.response_200(response)

    content = str(response.content)
    assert tp.reverse("news-approve", news.slug) not in content
    assert tp.reverse("news-delete", news.slug) not in content
    assert tp.reverse("news-update", news.slug) not in content


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_news_detail_actions_moderator(tp, make_entry, moderator_user, model_class):
    """Moderators can update, delete and approve a news entry."""
    news = make_entry(model_class, approved=False)  # not approved entry
    with tp.login(moderator_user):
        response = tp.get(news.get_absolute_url())
    tp.response_200(response)

    content = str(response.content)
    assert tp.reverse("news-approve", news.slug) in content
    assert tp.reverse("news-delete", news.slug) in content
    assert tp.reverse("news-update", news.slug) in content

    news.approve(baker.make("users.User"))
    with tp.login(moderator_user):
        response = tp.get(news.get_absolute_url())
    tp.response_200(response)

    content = str(response.content)
    assert tp.reverse("news-approve", news.slug) not in content
    assert tp.reverse("news-delete", news.slug) in content
    assert tp.reverse("news-update", news.slug) in content


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_news_detail_next_url(tp, make_entry, moderator_user, model_class):
    news = make_entry(model_class, approved=False)
    with tp.login(moderator_user):
        response = tp.get(news.get_absolute_url() + "?next=/foo")
    tp.response_200(response)
    tp.assertContext("next_url", "/foo")
    tp.assertResponseContains(
        '<input type="hidden" name="next" value="/foo" />', response
    )

    # unsafe URLs are not put in the context for future redirection
    with tp.login(moderator_user):
        response = tp.get(news.get_absolute_url() + "?next=http://example.com")
    tp.response_200(response)
    tp.assertNotIn("next_url", response.context)
    tp.assertResponseNotContains(
        '<input type="hidden" name="next" value="http://example.com" />', response
    )


@pytest.mark.parametrize(
    "url_name, form_class",
    [
        ("news-create", EntryForm),
        ("news-blogpost-create", BlogPostForm),
        ("news-link-create", LinkForm),
        ("news-poll-create", PollForm),
        ("news-video-create", VideoForm),
    ],
)
def test_news_create_get(tp, regular_user, url_name, form_class):
    # assertLoginRequired expects a non resolved URL, that is an URL name
    # see https://github.com/revsys/django-test-plus/issues/202
    tp.assertLoginRequired(url_name)

    with tp.login(regular_user):
        # assertGoodView expects a resolved URL
        # see https://github.com/revsys/django-test-plus/issues/202
        url = tp.reverse(url_name)
        response = tp.assertGoodView(url, test_query_count=3, verbose=True)

    form = tp.get_context("form")
    assert isinstance(form, form_class)
    for field in form:
        tp.assertResponseContains(str(field), response)


@pytest.mark.parametrize(
    "url_name, model_class, data_fields",
    [
        ("news-create", Entry, EntryForm.Meta.fields),
        ("news-blogpost-create", BlogPost, BlogPostForm.Meta.fields),
        ("news-link-create", Link, LinkForm.Meta.fields),
        ("news-poll-create", Poll, PollForm.Meta.fields),
        ("news-video-create", Video, VideoForm.Meta.fields),
    ],
)
def test_news_create_post(tp, regular_user, url_name, model_class, data_fields):
    url = tp.reverse(url_name)

    data = {
        k: f"random-value-{k}" if "url" not in k else "http://example.com"
        for k in data_fields
    }
    before = now()
    with tp.login(regular_user):
        response = tp.post(url, data=data, follow=True)
    after = now()

    entries = model_class.objects.filter(title=data["title"])
    assert len(entries) == 1
    entry = entries.get()
    assert entry.slug == slugify(data["title"])
    for field, value in data.items():
        assert getattr(entry, field) == value
    assert entry.author == regular_user
    assert not entry.is_approved
    assert not entry.is_published
    # Avoid mocking `now()`, yet still ensure that the timestamps are
    # between `before` and `after`
    assert before <= entry.created_at <= after
    assert before <= entry.modified_at <= after

    tp.assertRedirects(response, entry.get_absolute_url())


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_news_approve_get_method_not_allowed(
    tp, make_entry, regular_user, moderator_user, model_class
):
    entry = make_entry(model_class, approved=False)

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


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_news_approve_post(tp, make_entry, regular_user, moderator_user, model_class):
    entry = make_entry(model_class, approved=False)
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


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_news_approve_post_redirects_to_next_if_available(
    tp, make_entry, moderator_user, model_class
):
    entry = make_entry(model_class, approved=False)
    url_params = ("news-approve", entry.slug)
    next_url = "/foo"

    with tp.login(moderator_user):
        response = tp.post(*url_params, data={"next": next_url}, follow=False)

    tp.assertRedirects(response, next_url, fetch_redirect_response=False)

    # a non relative/non safe next URL is not used for redirection
    with tp.login(moderator_user):
        response = tp.post(
            *url_params, data={"next": "http://google.com"}, follow=False
        )

    tp.assertRedirects(
        response, entry.get_absolute_url(), fetch_redirect_response=False
    )


def test_news_moderation_list(tp, regular_user, moderator_user):
    url_name = "news-moderate"

    # login required
    tp.assertLoginRequired(url_name)

    # regular users would get a 403 for news moderation list
    with tp.login(regular_user):
        response = tp.get(url_name)
    tp.response_403(response)

    # moderators users would get a 200
    with tp.login(moderator_user):
        response = tp.get(url_name)
    tp.response_200(response)


def test_news_moderation_filter_unapproved_news(tp, make_entry, moderator_user):
    unapproved_published = [
        make_entry(model_class, approved=False, published=True)
        for _ in range(3)
        for model_class in NEWS_MODELS
    ]
    # approved and published
    ignore = [
        make_entry(model_class, approved=True, published=True)
        for _ in range(3)
        for model_class in NEWS_MODELS
    ]
    unapproved_unpublished = [
        make_entry(model_class, approved=False, published=False)
        for _ in range(3)
        for model_class in NEWS_MODELS
    ]
    # approved and unpublished
    ignore.extend(
        make_entry(model_class, approved=True, published=False)
        for _ in range(3)
        for model_class in NEWS_MODELS
    )

    url = tp.reverse("news-moderate")
    with tp.login(moderator_user):
        # 5 queries
        # SELECT "django_session"...
        # SELECT "users_user"...
        # SELECT "django_content_type"... (perms)
        # SELECT "django_content_type"... (perms and groups, may need debugging)
        # SELECT "news_entry"...
        response = tp.assertGoodView(url, test_query_count=6, verbose=True)

    content = str(response.content)
    for e in unapproved_published + unapproved_unpublished:
        assert e.title in content
        assert e.author.email in content
        assert (e.get_absolute_url() + f"?next={url}") in content
    for e in ignore:
        assert e.title not in content
        assert e.author.email not in content
        assert e.get_absolute_url() not in content


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_news_update_acl(
    tp, make_entry, regular_user, moderator_user, method, model_class
):
    entry = make_entry(model_class, approved=False)
    url_params = ("news-update", entry.slug)

    # regular users would get a 404 for a news they don't own
    with tp.login(regular_user):
        response = tp.request(method.lower(), *url_params)
    tp.response_403(response)

    # owner would get a 200 response, and so will moderators
    with tp.login(entry.author):
        response = tp.request(method.lower(), *url_params)
    tp.response_200(response)

    with tp.login(moderator_user):
        response = tp.request(method.lower(), *url_params)
    tp.response_200(response)

    # but if the entry is approved, only moderator can access the update form
    entry.approve(baker.make("users.User"))

    with tp.login(entry.author):
        response = tp.request(method.lower(), *url_params)
    tp.response_403(response)

    with tp.login(moderator_user):
        response = tp.request(method.lower(), *url_params)
    tp.response_200(response)


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_news_update(tp, make_entry, model_class):
    entry = make_entry(model_class, approved=False, title="A news title")
    url_params = ("news-update", entry.slug)

    with tp.login(entry.author):
        response = tp.get(*url_params)
    tp.response_200(response)

    content = str(response.content)
    assert entry.title in content
    assert entry.content in content

    new_title = "This is a different title"
    data = {"title": new_title}
    with tp.login(entry.author):
        response = tp.post(*url_params, data=data, follow=True)
    tp.response_200(response)

    tp.assertRedirects(response, entry.get_absolute_url())
    content = str(response.content)
    assert new_title in content
    assert "A news title" not in content

    entry.refresh_from_db()
    assert entry.title == new_title


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_news_delete_acl(
    tp, make_entry, regular_user, moderator_user, method, model_class
):
    entry = make_entry(model_class, approved=False)
    url_params = ("news-delete", entry.slug)

    # regular users would get a 404 for a news they don't own
    with tp.login(regular_user):
        response = tp.request(method.lower(), *url_params)
    tp.response_403(response)

    # owner would get a 200 response, and so will moderators
    with tp.login(entry.author):
        response = tp.request(method.lower(), *url_params)
    tp.response_403(response)

    with tp.login(moderator_user):
        response = tp.request(method.lower(), *url_params, follow=True)
    tp.response_200(response)

    # but if the entry is approved, only moderator can access the delete form
    entry = make_entry(model_class, approved=True)
    url_params = ("news-delete", entry.slug)

    with tp.login(entry.author):
        response = tp.request(method.lower(), *url_params)
    tp.response_403(response)

    with tp.login(moderator_user):
        response = tp.request(method.lower(), *url_params, follow=True)
    tp.response_200(response)


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_news_delete(tp, make_entry, moderator_user, model_class):
    entry = make_entry(model_class, approved=False)
    url_params = ("news-delete", entry.slug)

    with tp.login(moderator_user):
        response = tp.get(*url_params)
    tp.response_200(response)

    content = str(response.content)
    assert "Please confirm your choice" in content
    assert entry.title in content
    tp.assertResponseContains(
        '<button type="submit" name="delete">Yes, delete</button>', response
    )
    # No entry removed just yet!
    assert Entry.objects.filter(pk=entry.pk).count() == 1

    with tp.login(moderator_user):
        response = tp.post(*url_params, follow=True)
    tp.response_200(response)
    tp.assertRedirects(response, tp.reverse("news"))
    assert Entry.objects.filter(pk=entry.pk).count() == 0
