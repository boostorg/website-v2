import base64
import io
import logging
import random
from datetime import datetime

import psycopg2
from django.conf import settings
from django.contrib.staticfiles import finders
from django.db.models import Count
from django.db.models.functions import ExtractWeek, ExtractIsoYear
from matplotlib import pyplot as plt
from wordcloud import WordCloud, STOPWORDS

from core.models import SiteSettings
from libraries.models import WordcloudMergeWord  # TODO: move model to this app
from mailing_list.models import PostingData, SubscriptionData
from reports.constants import WORDCLOUD_FONT
from versions.models import Version

logger = logging.getLogger(__name__)


def generate_wordcloud(version: Version) -> tuple[str | None, list]:
    """Generates a wordcloud png and returns it as a base64 string and word frequencies.

    Returns:
        Tuple of (base64_encoded_png_string, wordcloud_top_words)
    """
    font_relative_path = f"font/{WORDCLOUD_FONT}"
    font_full_path = finders.find(font_relative_path)

    if not font_full_path:
        raise FileNotFoundError(f"Could not find font at {font_relative_path}")

    wc = WordCloud(
        mode="RGBA",
        background_color=None,
        width=1400,
        height=700,
        stopwords=STOPWORDS | SiteSettings.load().wordcloud_ignore_set,
        font_path=font_full_path,
    )
    word_frequencies = {}
    for content in get_mail_content(version):
        for key, val in wc.process_text(content).items():
            if len(key) < 2:
                continue
            key_lower = key.lower()
            if key_lower not in word_frequencies:
                word_frequencies[key_lower] = 0
            word_frequencies[key_lower] += val
    if not word_frequencies:
        return None, []

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


def get_mail_content(version: Version):
    prior_version = (
        Version.objects.minor_versions()
        .filter(version_array__lt=version.cleaned_version_parts_int)
        .order_by("-release_date")
        .first()
    )
    if not prior_version or not settings.HYPERKITTY_DATABASE_NAME:
        return []
    conn = psycopg2.connect(settings.HYPERKITTY_DATABASE_URL)
    with conn.cursor(name="fetch-mail-content") as cursor:
        cursor.execute(
            """
                SELECT content FROM hyperkitty_email
                WHERE date >= %(start)s AND date < %(end)s;
            """,
            {"start": prior_version.release_date, "end": version.release_date},
        )
        for [content] in cursor:
            yield content


def get_mailing_list_post_stats(start_date: datetime, end_date: datetime):
    logger.info(f"from {start_date} to {end_date}")
    data = (
        PostingData.objects.filter(post_time__gt=start_date, post_time__lte=end_date)
        .annotate(week=ExtractWeek("post_time"), iso_year=ExtractIsoYear("post_time"))
        .values("week")
        .annotate(count=Count("id"))
        .order_by("iso_year", "week")
    )
    return [{"y": s.get("count"), "x": s.get("week")} for s in data]


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
        .values("week", "list")
        .annotate(count=Count("id"))
        .order_by("iso_year", "week")
    )

    formatted_data = [{"x": s.get("week"), "y": s.get("count")} for s in data]
    referenced_weeks = [x.get("week") for x in data]
    # account for weeks that no data is retrieved
    for w in range(start_date.isocalendar().week, end_date.isocalendar().week + 1):
        if w not in referenced_weeks:
            formatted_data.append({"x": w, "y": 0})
    return formatted_data
