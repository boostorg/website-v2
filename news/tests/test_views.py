import os
import uuid
from datetime import date, timedelta
from io import BytesIO

import pytest
from django.core import mail
from django.utils.text import slugify
from django.utils.timezone import now
from model_bakery import baker

from ..forms import BlogPostForm, LinkForm, NewsForm, PollForm, VideoForm
from ..models import NEWS_MODELS, BlogPost, Entry, Link, News, Poll, Video
from ..notifications import (
    send_email_news_approved,
    send_email_news_needs_moderation,
    send_email_news_posted,
)
from ..views import datefilter, display_publish_at


pytest.skip(allow_module_level=True)


def test_display_publish_at_now():
    since = now()
    # Now or future
    assert display_publish_at(since, since) == "now"
    assert display_publish_at(since + timedelta(seconds=1), since) == "now"
    assert display_publish_at(since - timedelta(seconds=1), since) == "now"
    assert display_publish_at(since - timedelta(minutes=30), since) == "now"


@pytest.mark.parametrize(
    "publish_at, expected",
    [
        # An hour ago (up to 24 hours)
        (timedelta(minutes=31), "an hour ago"),
        (timedelta(minutes=59), "an hour ago"),
        (timedelta(hours=1), "an hour ago"),
        (timedelta(hours=1, seconds=1), "an hour ago"),
        (timedelta(hours=1, minutes=31), "2 hours ago"),
        (timedelta(hours=1, minutes=59), "2 hours ago"),
        (timedelta(hours=1, minutes=60), "2 hours ago"),
        (timedelta(hours=23, minutes=29), "23 hours ago"),
        # 3 days ago (up to 7 days)
        (timedelta(hours=23, minutes=31), "1 day ago"),
        (timedelta(hours=24, minutes=00), "1 day ago"),
        (timedelta(days=1), "1 day ago"),
        (timedelta(days=1, hours=24), "2 days ago"),
        (timedelta(days=6, hours=23, minutes=29), "6 days ago"),
    ],
)
def test_display_publish_at_days_ago(publish_at, expected):
    since = now()
    assert display_publish_at(since - publish_at, since) == expected


@pytest.mark.parametrize(
    "publish_at",
    [
        timedelta(days=6, hours=24),
        timedelta(days=7),
        timedelta(days=7, seconds=1),
        timedelta(days=20),
    ],
)
def test_display_publish_at_datefilter(publish_at):
    since = now()
    # June 13th, 2023 (after 7 days)
    target = since - publish_at
    assert display_publish_at(target, since) == datefilter(target, "M jS, Y")


@pytest.mark.parametrize(
    "url_name, model_class",
    [
        ("news", Entry),
        ("news-blogpost-list", BlogPost),
        ("news-link-list", Link),
        ("news-news-list", News),
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
        publish_at=now() - timedelta(days=1),
    )
    today_news = make_entry(
        model_class, approved=True, title="current news", publish_at=now()
    )
    tomorrow_news = make_entry(
        model_class,
        approved=True,
        title="future news",
        publish_at=now() + timedelta(days=1),
    )

    if authenticated:
        tp.login(regular_user)

    # 10 queries if authenticated, less otherwise
    response = tp.assertGoodView(
        tp.reverse(url_name), test_query_count=10, verbose=True
    )

    expected = [today_news, yesterday_news]
    assert list(response.context.get("entry_list", [])) == expected

    content = str(response.content)
    for entry in expected:
        assert entry.title in content
        formatted_date = str(display_publish_at(entry.publish_at))
        assert formatted_date in content
        # link_with_date = f'<a href="{entry.get_absolute_url()}">{formatted_date}</a>'
        # tp.assertResponseContains(link_with_date, response)
        if entry.tag:
            assert entry.tag in content  # this is the tag

    assert not_approved_news.get_absolute_url() not in content
    assert not_approved_news.title not in content
    assert tomorrow_news.get_absolute_url() not in content
    assert tomorrow_news.title not in content

    # If user is not authenticated, the Create News link should not be shown
    assert (tp.reverse("news-create") in content) == authenticated


def test_entry_list_queries(tp, make_entry):
    expected = [
        make_entry(model_class)
        for model_class in NEWS_MODELS
        for i in range(len(model_class.__name__))
    ]

    # 4 queries
    response = tp.assertGoodView(tp.reverse("news"), test_query_count=29, verbose=True)

    entry_list = response.context.get("entry_list", [])
    assert set(e.id for e in entry_list) == set(e.id for e in expected)

    content = str(response.content)
    for entry in expected:
        assert entry.get_absolute_url() in content
        assert entry.title in content
        news_link = f'href="/news/{entry.tag}/"' if entry.tag else 'href="/news/"'
        assert news_link in content


@pytest.mark.parametrize(
    "url_name, model_class",
    [
        ("news", Entry),
        ("news-blogpost-list", BlogPost),
        ("news-link-list", Link),
        ("news-news-list", News),
        ("news-poll-list", Poll),
        ("news-video-list", Video),
    ],
)
def test_entry_list_authenticated(tp, make_entry, url_name, model_class, regular_user):
    test_entry_list(
        tp, make_entry, regular_user, url_name, model_class, authenticated=True
    )


@pytest.mark.parametrize("model_class", NEWS_MODELS)
@pytest.mark.parametrize("with_image", [False, True])
def test_news_detail(tp, make_entry, model_class, with_image):
    """Browse details for a given news entry."""
    a_past_date = now() - timedelta(hours=10)
    news = make_entry(
        model_class,
        approved=True,
        publish_at=a_past_date,
        _fill_optional=True,
        _create_files=with_image,
    )
    url = tp.reverse("news-detail", news.slug)

    response = tp.get(url)
    tp.response_200(response)

    content = str(response.content)
    assert news.title in content
    assert news.content in content
    if with_image:
        assert news.image
        assert f'<img src="{news.image.url}"' in content
    else:
        assert not news.image
        assert '<img src="' not in content
    assert tp.reverse("news-approve", news.slug) not in content
    assert tp.reverse("news-delete", news.slug) not in content
    assert tp.reverse("news-update", news.slug) not in content

    # no next nor prev links
    assert "newer entries" not in content.lower()
    assert "older entries" not in content.lower()

    # create an older news, likely different type
    older_date = a_past_date - timedelta(hours=1)
    older = make_entry(approved=True, publish_at=older_date)

    response = tp.get(url)
    tp.response_200(response)

    content = str(response.content)
    assert "newer entries" not in content.lower()
    assert "older entries" in content.lower()
    assert older.get_absolute_url() in content

    # create a newer news, but still older than now so it's shown
    newer_date = a_past_date + timedelta(hours=1)
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


@pytest.mark.parametrize("user_type", ["user", "moderator_user"])
def test_news_create_multiplexer(tp, user_type, request):
    url_name = "news-create"
    url = tp.reverse(url_name)
    tp.assertLoginRequired(url_name)

    user = request.getfixturevalue(user_type)
    with tp.login(user):
        tp.assertGoodView(url, test_query_count=5, verbose=True)

    expected = [BlogPostForm, LinkForm, NewsForm, VideoForm]
    if "moderator" in user_type:
        expected.append(PollForm)
    items = tp.get_context("items")
    assert len(items) == len(expected)

    for item, form_class in zip(items, expected):
        assert isinstance(item["form"], form_class)
        model_class = form_class.Meta.model
        # assert item["add_url_name"] == f"news-{model_class.news_type}-create"
        # assert model_class.__name__ in item["add_label"]
        assert model_class.__name__ == item["model_name"]


def test_news_create_require_profile_photo(tp, user):
    """Users must have a profile photo before they can post news."""
    url_name = "news-create"
    url = tp.reverse(url_name)

    # Test with the image
    with tp.login(user):
        response = tp.get(url)
        tp.response_200(response)

    # Delete the user's image and confirm they can access the page
    user.image.delete()
    user.refresh_from_db()
    with tp.login(user):
        response = tp.get(url)
        tp.response_302(response)
        assert response.url == tp.reverse("profile-account")


@pytest.mark.parametrize(
    "method", ["DELETE", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
)
def test_news_create_multiplexer_method_not_allowed(tp, user, method):
    # Any HTTP method other than GET is a 405
    with tp.login(user):
        response = tp.request(method_name=method.lower(), url_name="news-create")

    tp.response_405(response)


@pytest.mark.parametrize(
    "url_name, form_class",
    [
        ("news-news-create", NewsForm),
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
        tp.assertGoodView(url, test_query_count=4, verbose=True)

    form = tp.get_context("form")
    assert isinstance(form, form_class)
    # for field in form:
    #    tp.assertResponseContains(str(field), response)


@pytest.mark.parametrize(
    "url_name, model_class, data_fields",
    [
        ("news-news-create", News, NewsForm.Meta.fields),
        ("news-blogpost-create", BlogPost, BlogPostForm.Meta.fields),
        ("news-link-create", Link, LinkForm.Meta.fields),
        ("news-poll-create", Poll, PollForm.Meta.fields),
        ("news-video-create", Video, VideoForm.Meta.fields),
    ],
)
@pytest.mark.parametrize("with_image", [False, True])
def test_news_create_post(
    tp,
    url_name,
    model_class,
    data_fields,
    with_image,
    regular_user,
    moderator_user,
    settings,
):
    data = {
        k: f"random-value-{k}" if "url" not in k else "http://example.com"
        for k in data_fields
        if k not in ("image", "publish_at")
    }

    img = None
    if with_image:
        img = BytesIO(
            b"GIF89a\x01\x00\x01\x00\x00\x00\x00!\xf9\x04\x01\x00\x00\x00"
            b"\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x01\x00\x00"
        )
        img.name = f"random-value-{uuid.uuid4()}.png"
        data["image"] = img

    data["publish_at"] = right_now = now()

    before = now()
    with tp.login(regular_user):
        response = tp.post(url_name, data=data, follow=True)
    after = now()

    entries = model_class.objects.filter(title=data["title"])
    assert len(entries) == 1
    entry = entries.get()
    assert entry.slug == slugify(data["title"])
    for field, value in data.items():
        if field != "image":
            assert getattr(entry, field) == value
        elif with_image:
            assert entry.image
            expected = os.path.join(
                settings.MEDIA_ROOT,
                date.today().strftime(Entry.image.field.upload_to),
                img.name,
            )
            assert entry.image.path == expected
        else:
            assert not entry.image
    assert entry.author == regular_user
    assert not entry.is_approved
    assert not entry.is_published
    # Avoid mocking `now()`, yet still ensure that the timestamps are
    # between `before` and `after`
    assert before <= entry.created_at <= after
    assert before <= entry.modified_at <= after
    assert entry.publish_at == right_now
    # email to moderators was sent
    assert len(mail.outbox) == 1
    actual = mail.outbox[0]
    # render the same email using the notifications' method to assert equality
    assert send_email_news_needs_moderation(response.wsgi_request, entry) == 1
    expected = mail.outbox[1]
    assert actual.subject == expected.subject
    assert actual.body == expected.body
    assert actual.from_email == expected.from_email
    assert actual.recipients() == expected.recipients()
    assert actual.recipients() == [moderator_user.email]
    # success message is shown
    messages = [(m.level_tag, m.message) for m in tp.get_context("messages")]
    assert messages == [("success", "The news entry was successfully created.")]

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
def test_news_approve_post(
    tp, make_entry, regular_user, moderator_user, make_user, model_class
):
    entry = make_entry(model_class, approved=False)
    url_params = ("news-approve", entry.slug)

    # user does not allow notifications
    make_user(email="u1@example.com", allow_notification_others_news_posted=[])
    # allows nofitications for all news type
    make_user(
        email="u2@example.com",
        allow_notification_others_news_posted=[m.news_type for m in NEWS_MODELS],
    )
    # allows only for the same type as entry
    make_user(email="u3@example.com", allow_notification_others_news_posted=[entry.tag])
    # allows for any other type except entry's
    make_user(
        email="u4@example.com",
        allow_notification_others_news_posted=[
            m.news_type for m in NEWS_MODELS if m.news_type != entry.tag
        ],
    )

    # regular users would still get a 403 on POST
    with tp.login(regular_user):
        response = tp.post(*url_params)
    tp.response_403(response)

    # moderators users can POST to the view to approve an entry
    with tp.login(moderator_user):
        before = now()
        response = tp.post(*url_params, follow=True)
        after = now()

    tp.assertRedirects(response, entry.get_absolute_url())

    entry.refresh_from_db()
    assert entry.is_approved is True
    assert entry.moderator == moderator_user
    assert before <= entry.approved_at <= after
    assert before <= entry.modified_at <= after
    # email was sent, one to author, one to other users
    assert len(mail.outbox) == 2
    # approval email to author
    actual = mail.outbox[0]
    # render the same email using the notifications' method to assert equality
    assert send_email_news_approved(response.wsgi_request, entry) == 1
    expected = mail.outbox[2]
    assert actual.subject == expected.subject
    assert actual.body == expected.body
    assert actual.from_email == expected.from_email
    assert actual.recipients() == expected.recipients()
    # news posted email to other users
    actual = mail.outbox[1]
    # render the same email using the notifications' method to assert equality
    assert send_email_news_posted(response.wsgi_request, entry) == 1
    expected = mail.outbox[3]
    assert actual.subject == expected.subject
    assert actual.body == expected.body
    assert actual.from_email == expected.from_email
    assert actual.recipients() == expected.recipients()
    # success message is shown
    messages = [(m.level_tag, m.message) for m in tp.get_context("messages")]
    assert messages == [("success", "The entry was successfully approved.")]


@pytest.mark.parametrize("model_class", NEWS_MODELS)
def test_news_approve_already_approved(tp, make_entry, moderator_user, model_class):
    entry = make_entry(model_class, approved=True)
    url_params = ("news-approve", entry.slug)

    with tp.login(moderator_user):
        before = now()
        response = tp.post(*url_params, follow=True)
        now()

    tp.assertRedirects(response, entry.get_absolute_url())

    entry.refresh_from_db()
    # approval information was not changed
    assert entry.is_approved is True
    assert entry.moderator is not moderator_user
    assert entry.approved_at <= before
    assert entry.modified_at <= before
    # email was not sent
    assert mail.outbox == []
    # error message is shown
    messages = [(m.level_tag, m.message) for m in tp.get_context("messages")]
    assert messages == [("error", "The entry was already approved.")]


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
        response = tp.assertGoodView(url, test_query_count=7, verbose=True)

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
    data = {"title": new_title, "publish_at": entry.publish_at}
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
    # No entry removed just yet!
    assert Entry.objects.filter(pk=entry.pk).count() == 1

    with tp.login(moderator_user):
        response = tp.post(*url_params, follow=True)
    tp.response_200(response)
    tp.assertRedirects(response, tp.reverse("news"))
    assert Entry.objects.filter(pk=entry.pk).count() == 0
