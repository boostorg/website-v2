import datetime

from django.utils.timezone import now
from model_bakery import baker


def test_entry_list(tp, make_entry):
    """List published news."""
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


def test_news_detail_404_if_not_published(tp, make_entry):
    """Details for a news entry are available if published or authored."""
    news = make_entry(published=False)
    response = tp.get(news.get_absolute_url())
    tp.response_404(response)

    # even if logged in, a regular user can not access the unpublished news
    user = baker.make("users.User")
    user.set_password("password")
    user.save()
    with tp.login(user):
        response = tp.get(news.get_absolute_url())
    tp.response_404(response)

    # but the entry author can access it even if unpublished
    user = news.author
    user.set_password("password")
    user.save()
    with tp.login(user):
        response = tp.get(news.get_absolute_url())
    tp.response_200(response)
