import base64
import io
import json
import logging
import random
from datetime import datetime, timedelta, date

import psycopg2
from django.conf import settings
from django.contrib.staticfiles import finders
from django.db.models import Count
from django.db.models.functions import ExtractWeek, ExtractIsoYear
from matplotlib import pyplot as plt
from wordcloud import WordCloud, STOPWORDS
from algoliasearch.analytics.client import AnalyticsClientSync

from core.models import SiteSettings
from libraries.constants import RELEASE_REPORT_SEARCH_TOP_COUNTRIES_LIMIT
from libraries.models import WordcloudMergeWord  # TODO: move model to this app
from mailing_list.models import PostingData, SubscriptionData
from reports.constants import WORDCLOUD_FONT
from versions.models import Version

logger = logging.getLogger(__name__)


def generate_mailinglist_words(
    prior_version: Version, version: Version
) -> dict[str, int]:
    """Generates word frequencies from mailing list content between two versions."""
    word_frequencies = {}
    for content in get_mail_content(version, prior_version):
        for key, val in WordCloud().process_text(content).items():
            if len(key) < 2:
                continue
            key_lower = key.lower()
            if key_lower not in word_frequencies:
                word_frequencies[key_lower] = 0
            word_frequencies[key_lower] += val

    return word_frequencies


def generate_algolia_words(
    client: AnalyticsClientSync, version: Version
) -> dict[str, int]:
    args = {
        "index": version.stripped_boost_url_slug,
        "limit": 100,
    }
    search_results = client.get_top_searches(**args).to_json()
    search_data = json.loads(search_results)
    return {r["search"]: r["count"] for r in search_data["searches"] if r["count"] > 1}


def generate_wordcloud(
    word_frequencies: dict[str, int], width: int, height: int
) -> tuple[str | None, list]:
    """Generates a wordcloud png and returns it as a base64 string and word frequencies.

    Returns:
        Tuple of (base64_encoded_png_string, wordcloud_top_words)
    """
    if not word_frequencies:
        return None, []
    font_relative_path = f"font/{WORDCLOUD_FONT}"
    font_full_path = finders.find(font_relative_path)

    if not font_full_path:
        raise FileNotFoundError(f"Could not find font at {font_relative_path}")

    wc = WordCloud(
        mode="RGBA",
        background_color=None,
        width=width,
        height=height,
        stopwords=STOPWORDS | SiteSettings.load().wordcloud_ignore_set,
        font_path=font_full_path,
    )
    word_frequencies = boost_normalize_words(
        word_frequencies,
        {x.from_word: x.to_word for x in WordcloudMergeWord.objects.all()},
    )
    # first sort by number, then sort the top 200 alphabetically
    word_frequencies = {
        key: val
        for key, val in sorted(
            word_frequencies.items(),
            key=lambda x: x[1],
            reverse=True,
        )
    }
    wordcloud_top_words = sorted(list(word_frequencies.keys())[:200])

    wc.generate_from_frequencies(word_frequencies)
    plt.figure(figsize=(14, 7), facecolor=None)
    plt.imshow(
        wc.recolor(color_func=grey_color_func, random_state=3),
        interpolation="bilinear",
    )
    plt.axis("off")
    image_bytes = io.BytesIO()
    plt.savefig(
        image_bytes,
        format="png",
        dpi=100,
        bbox_inches="tight",
        pad_inches=0,
        transparent=True,
    )
    image_bytes.seek(0)
    return base64.b64encode(image_bytes.read()).decode(), wordcloud_top_words


def boost_normalize_words(frequencies, word_map):
    # from word, to word
    for o, n in word_map.items():
        from_count = frequencies.get(o, 0)
        if not from_count:
            continue
        to_count = frequencies.get(n, 0)
        frequencies[n] = from_count + to_count
        del frequencies[o]
    return frequencies


def grey_color_func(*args, **kwargs):
    return "hsl(0, 0%%, %d%%)" % random.randint(10, 80)


def get_mail_content(version: Version, prior_version: Version):
    if not prior_version or not settings.HYPERKITTY_DATABASE_NAME:
        return []
    conn = psycopg2.connect(settings.HYPERKITTY_DATABASE_URL)
    with conn.cursor(name="fetch-mail-content") as cursor:
        cursor.execute(
            """
                SELECT content FROM hyperkitty_email
                WHERE date >= %(start)s AND date < %(end)s;
            """,
            {
                "start": prior_version.release_date,
                "end": version.release_date or date.today(),
            },
        )
        for [content] in cursor:
            yield content


def get_mailing_list_post_stats(start_date: datetime, end_date: datetime):
    data = (
        PostingData.objects.filter(post_time__gt=start_date, post_time__lte=end_date)
        .annotate(week=ExtractWeek("post_time"), iso_year=ExtractIsoYear("post_time"))
        .values("iso_year", "week")
        .annotate(count=Count("id"))
        .order_by("iso_year", "week")
    )

    chart_data = []

    for row in data:
        week_number = row["week"]
        year_number = str(row["iso_year"])[2:]  # e.g. 25
        x = f"{week_number} ({year_number})"  # e.g., "51 (24)", "1 (25)"
        y = row["count"]
        chart_data.append({"x": x, "y": y})

    return chart_data


def get_new_subscribers_stats(start_date: datetime, end_date: datetime):
    data = (
        SubscriptionData.objects.filter(
            subscription_dt__gte=start_date,
            subscription_dt__lte=end_date,
            list="boost",
        )
        .annotate(
            week=ExtractWeek("subscription_dt"),
            iso_year=ExtractIsoYear("subscription_dt"),
        )
        .values("iso_year", "week")
        .annotate(count=Count("id"))
        .order_by("iso_year", "week")
    )

    # Convert data into a dict for easy lookup
    counts_by_week = {(row["iso_year"], row["week"]): row["count"] for row in data}

    # Iterate through every ISO week in the date range
    current = start_date
    seen = set()
    chart_data = []
    while current <= end_date:
        iso_year, iso_week, _ = current.isocalendar()
        key = (iso_year, iso_week)
        if key not in seen:  # skip duplicate weeks in the same loop
            seen.add(key)
            year_suffix = str(iso_year)[2:]
            label = f"{iso_week} ({year_suffix})"
            count = counts_by_week.get(key, 0)
            chart_data.append({"x": label, "y": count})
        current += timedelta(days=7)  # hop by weeks

    return chart_data


def get_algolia_search_stats(client: AnalyticsClientSync, version: Version) -> dict:
    default_args = {"index": version.stripped_boost_url_slug}
    # search data
    search_response = client.get_searches_count(**default_args).to_json()
    search_data = json.loads(search_response)
    # country data
    country_results = client.get_top_countries(**default_args, limit=100).to_json()
    country_data = json.loads(country_results)
    country_stats = {r["country"]: r["count"] for r in country_data["countries"]}
    return {
        "total_searches": search_data.get("count"),
        "country_stats": country_stats,
        "top_countries": list(country_stats.items())[
            :RELEASE_REPORT_SEARCH_TOP_COUNTRIES_LIMIT
        ],
    }
