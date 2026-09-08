# News and Moderation

All of the code for news is [located here](https://github.com/cppalliance/temp-site/tree/develop/news) and the templates are [here](https://github.com/cppalliance/temp-site/tree/develop/templates/news) .

The model structure is a bit more advanced than many aspects of the Boost
website. All news items inherit from a base concrete class `Entry`. So a
particular type of news, for example Links, has a physical database table
named `news_link` that has a pointer type `ForeignKey` to the corresponding
item in `news_entry`.

This allows for fast/efficient listing of all News items in reverse chronological
order, but also allows for different types of news to add fields specific to
their type.  As of launch, only Polls take advantage of this feature but it
there to allow for better flexability in the future.

## Definition of Published

An item is considered published and visible to all users, logged in and anonymous,
if:

- The published date is in the past
- The item has been approved by a moderator

## Moderation

If a user is a moderator, when they create news the items are automatically
approved. This is to avoid an annoying scenario where a moderator enters a new
news item, then has to go to the Moderation List page to approve it.

However, this does mean moderators can publish things easily which might
for example include typos.

### Who can moderate?

Users can moderate if:

- The user posses the `change_entry` permission to the News Entry model
- The user is in a group which posses the `change_entry` permission to the News Entry model
- The user is a Superuser

## AI-generated entry summaries

When an `Entry` is saved without a `summary`, `news/tasks.py` dispatches a Celery task that asks an LLM (via [OpenRouter](https://openrouter.ai), default model `gpt-oss-120b`) to produce a short plain-text summary, then writes it back to the entry. Clearing the `summary` field and saving triggers regeneration.

This is the same OpenRouter integration used by the Boost release-notes "What's New" summary in `versions/tasks.py`. Both share `OPENROUTER_API_KEY` — see [Environment Variables](./env_vars.md).

## AI description generation

`v3-news-generate-description` and `v3-news-generate-link-description` call the summarization model synchronously for the create-post page. Both are capped per user per day; the limit, the day's usage and the change history live in the Wagtail admin under Settings -> AI Description Settings. See [admin.md](admin.md).

The automatic summarization that `PostPage.save()` and `Entry.save()` dispatch to Celery when a post has no summary is a separate path and is **not** capped: it only fires for a live page, so it follows moderation rather than a user button.
