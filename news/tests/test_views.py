import datetime

from django.utils.timezone import now
from model_bakery import baker


def test_entry_list(tp):
    """List published news."""
    yesterday_news = baker.make(
        "Entry", title="old news", publish_at=now() - datetime.timedelta(days=1)
    )
    today_news = baker.make("Entry", title="current news", publish_at=now().today())
    tomorrow_news = baker.make(
        "Entry", title="future news", publish_at=now() + datetime.timedelta(days=1)
    )

    response = tp.get("news")

    tp.response_200(response)
    expected = [today_news, yesterday_news]
    assert list(response.context.get("entry_list", [])) == expected

    content = str(response.content)
    for n in expected:
        assert n.get_absolute_url() in content
        assert n.title in content

    assert tomorrow_news.get_absolute_url() not in content
    assert tomorrow_news.title not in content


def test_news_detail(tp):
    """Browse details for a given news entry."""
    a_past_date = now() - datetime.timedelta(hours=10)
    news = baker.make("Entry", publish_at=a_past_date)
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
    older = baker.make("Entry", publish_at=older_date)

    response = tp.get(url)
    tp.response_200(response)

    content = str(response.content)
    assert "newer entries" not in content.lower()
    assert "older entries" in content.lower()
    assert older.get_absolute_url() in content

    # create a newer news, but still older than now so it's shown
    newer_date = a_past_date + datetime.timedelta(hours=1)
    assert newer_date < now()
    newer = baker.make("Entry", publish_at=newer_date)

    response = tp.get(url)
    tp.response_200(response)

    content = str(response.content)
    assert "newer entries" in content.lower()
    assert "older entries" in content.lower()
    assert newer.get_absolute_url() in content
