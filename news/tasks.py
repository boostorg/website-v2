from textwrap import dedent
from openai import OpenAI, OpenAIError
import requests
import structlog

from config.celery import app
from config.settings import OPENROUTER_API_KEY, OPENROUTER_URL
from news.constants import CONTENT_SUMMARIZATION_THRESHOLD
from news.helpers import extract_content
from news.utils import set_video_thumbnail

logger = structlog.get_logger(__name__)


@app.task(bind=True, max_retries=3, autoretry_for=(OpenAIError,))
def summarize_content(self, content: str, title: str, model: str) -> str:
    """Summarize content using an LLM model."""
    if not content:
        logger.warning("No content provided to summarize, skipping.")
        raise ValueError("No content provided to summarize.")
    logger.info(f"Summarizing {content[:100]=}... with {model=}")
    max_length = 256
    system_prompt = dedent(
        f"""
        You are an experienced technical writer tasked with summarizing content. Provide
        a brief description of what the content after the "----" is discussing.
        The title is also provided and may be in the content, repeating it in the
        summary would be redundant so should be avoided.
        Your summary should be concise, clear, and capture the main points of the
        content. It should be less than {max_length} characters, with a single paragraph
        of text, without going into detail. Before returning your response, check if
        it's less than {max_length} characters, if not, shorten it until it is.
        Write summaries in an impersonal, passive voice, never attributing actions to
        'the author' or similar.
        If no content is provided, do not return anything at all.
        Don't format with markdown, html, or any other markup, just plain text.
        Avoid adding any personal opinions or extraneous information.
        Do not allow any NSFW content such as profanity, sexual content, or violence to
        be returned in the summary, work around it.
        Do not allow any security vulnerabilities to be returned in the summary, work
        around them.
        """
    )
    user_prompt = dedent(
        f"""
        Please provide a summary of the following content:
        ----
        Title: {title}
        Content: {content}
        """
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    logger.debug(f"{messages=}")
    content = None
    try:
        client = OpenAI(base_url=OPENROUTER_URL, api_key=OPENROUTER_API_KEY)
        response = client.chat.completions.create(model=model, messages=messages)
        content = response.choices[0].message.content
        logger.info(
            f"Received summarized content for {content[:100]=}: {len(content)=}..."
        )
    except (AttributeError, IndexError) as e:
        logger.error(f"Error getting summarized content: {e=}")
    return content


@app.task
def save_entry_summary_value(summary: str, pk: int):
    from news.models import Entry

    entry = Entry.objects.get(pk=pk)
    entry.summary = summary
    entry.save()


@app.task
def summary_dispatcher(pk: int):
    from news.models import Entry

    entry = Entry.objects.get(pk=pk)
    logger.info(f"Dispatching {pk=} with {entry.news_type=}")
    handler = {
        "news": set_summary_for_event_entry,
        "blogpost": set_summary_for_event_entry,
        "link": set_summary_for_link_entry,
        "video": set_summary_for_video_entry,
        "poll": set_summary_for_poll_entry,
    }[entry.determined_news_type]
    logger.info(f"Dispatching summary task for {pk=} to {handler.__name__=}")
    handler.delay(pk)


@app.task
def set_summary_for_event_entry(pk: int):
    from news.models import Entry

    entry = Entry.objects.get(pk=pk)
    logger.info(f"dispatching summarize task for {pk=} with {entry.content[:40]=}...")
    if entry.content and len(entry.content) < CONTENT_SUMMARIZATION_THRESHOLD:
        logger.warning(f"Content too short to summarize for {pk=}, skipping.")
        return
    logger.info(f"handing off {pk=} to summarize_content task")
    summarize_content.apply_async(
        (entry.content, entry.title, "gpt-oss-120b"),
        link=save_entry_summary_value.s(pk),
    )


@app.task
def set_summary_for_link_entry(pk: int):
    logger.info(f"Setting summary for link entry {pk=}")
    from news.models import Entry

    entry = Entry.objects.get(pk=pk)
    try:
        logger.info(f"Fetching content from {entry.external_url=} for entry.{pk=}")
        response = requests.get(entry.external_url, timeout=10)
        response.raise_for_status()
        markup = response.text
        logger.debug(f"Fetched {len(markup)=} for entry.{pk=}...")
        content = extract_content(markup)
        logger.info(f"extracted content from {entry.external_url=}, {markup[:100]=}")
    except requests.RequestException as e:
        logger.error(f"Error fetching content from {entry.external_url=}: {e=}")
        return

    logger.info(f"dispatching summarize task for {pk=} with {content[:40]=}...")
    summarize_content.apply_async(
        (content, entry.title, "gpt-oss-120b"), link=save_entry_summary_value.s(pk)
    )


@app.task
def set_summary_for_video_entry(pk: int):
    logger.info("Summarization not implemented")


@app.task
def set_summary_for_poll_entry(pk: int):
    logger.info("Summarization not implemented")


@app.task
def set_thumbnail_for_video_entry(pk: int):
    from news.models import Video

    video = Video.objects.get(pk=pk)
    set_video_thumbnail(video)


@app.task
def sync_post_views_from_plausible():
    """Sync per-post page view counts from Plausible into Entry.page_views."""
    from django.conf import settings

    import requests as http
    from news.models import Entry
    from reports.constants import WEB_ANALYTICS_API_URL_V2, WEB_ANALYTICS_DOMAIN

    if not settings.PLAUSIBLE_STATS_KEY or settings.PLAUSIBLE_STATS_KEY == "changeme":
        logger.info(
            "sync_post_views.skipped", reason="PLAUSIBLE_STATS_KEY not configured"
        )
        return

    news_entry_prefix = "/news/entry/"
    payload = {
        "site_id": WEB_ANALYTICS_DOMAIN,
        "metrics": ["pageviews"],
        "dimensions": ["event:page"],
        "filters": [["contains", "event:page", [news_entry_prefix]]],
        "date_range": "all",
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {settings.PLAUSIBLE_STATS_KEY}",
    }

    response = http.post(url=WEB_ANALYTICS_API_URL_V2, json=payload, headers=headers)
    if not response.ok:
        logger.error(
            "sync_post_views.api_error",
            status=response.status_code,
            body=response.text,
        )
        return

    data = response.json()
    if not data or "results" not in data:
        logger.error("sync_post_views.unexpected_response", data=data)
        return

    slug_views: dict[str, int] = {}
    for result in data["results"]:
        path = result["dimensions"][0]
        if not path.startswith(news_entry_prefix):
            continue
        slug = path[len(news_entry_prefix) :].rstrip("/")
        if slug:
            slug_views[slug] = int(result["metrics"][0])

    if not slug_views:
        logger.info("sync_post_views.no_results")
        return

    entries = list(Entry.objects.filter(slug__in=slug_views.keys()))
    for entry in entries:
        entry.page_views = slug_views[entry.slug]
    Entry.objects.bulk_update(entries, ["page_views"])
    logger.info("sync_post_views.done", updated=len(entries))
