import base64
import io
import random

import psycopg2
from django.conf import settings
from matplotlib import pyplot as plt
from wordcloud import WordCloud, STOPWORDS

from core.models import SiteSettings
from libraries.models import WordcloudMergeWord  # TODO: move model to this app
from versions.models import Version


class ReportVisualization:
    @staticmethod
    def generate_wordcloud(version: Version) -> tuple[str | None, dict]:
        """Generates a wordcloud png and returns it as a base64 string and word frequencies.

        Returns:
            Tuple of (base64_encoded_png_string, word_frequencies_dict)
        """
        wc = WordCloud(
            mode="RGBA",
            background_color=None,
            width=1400,
            height=700,
            stopwords=STOPWORDS | SiteSettings.load().wordcloud_ignore_set,
            font_path=settings.BASE_DIR / "static" / "font" / "notosans_mono.woff",
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
            return None, {}

        word_frequencies = boost_normalize_words(
            word_frequencies,
            {x.from_word: x.to_word for x in WordcloudMergeWord.objects.all()},
        )

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
        return base64.b64encode(image_bytes.read()).decode(), word_frequencies


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
