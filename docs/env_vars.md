# Environment Variables

This project uses environment variables to configure certain aspects of the application.

## `GITHUB_TOKEN`

- Used to authenticate with the GitHub API when making requests.
- For **local development**, you should set this variable to a valid personal access token that has the necessary permissions to access the relevant repositories. [Generate a new personal access token](https://github.com/settings/tokens) and replace the value for `GITHUB_TOKEN` in your `.env` file in order to connect to certain parts of the GitHub API.
- In **deployed environments**, this should be set to a valid access token associated with the GitHub organization. Edit `kube/boost/values.yaml` (or the environment-specific yaml file) to change this value.


## `ENVIRONMENT_NAME`

- Used to indicate the name of the environment where the application is running.
- For **local development**, set this to whatever you want.
- In **deployed environments**, change the value by editing `kube/boost/values.yaml` (or the environment-specific yaml file).


## `STATIC_CONTENT_AWS_ACCESS_KEY_ID`

- Used to authenticate with the Amazon Web Services (AWS) API when accessing static content from a specified bucket.
- For **local development**, obtain valid value from the Boost team.
- In **deployed environments**, the valid value is set as a kube secret and is defined in `kube/boost/values.yaml` (or the environment-specific yaml file).


## `STATIC_CONTENT_AWS_SECRET_ACCESS_KEY`

- Used to authenticate with the Amazon Web Services (AWS) API when accessing static content from a specified bucket.
- For **local development**, obtain valid value from the Boost team.
- In **deployed environments**, the valid value is set as a kube secret and is defined in `kube/boost/values.yaml` (or the environment-specific yaml file).


## `STATIC_CONTENT_BUCKET_NAME`

- Specifies the name of the Amazon S3 bucket where static content is stored
- For **local development**, obtain valid value from the Boost team.
- In **deployed environments**, the valid value is set in `kube/boost/values.yaml` (or the environment-specific yaml file).

## Boost Release Downloads Settings

### `ARTIFACTORY_URL` (deprecated)

- Base API endpoint for accessing the JFrog Artifactory release downloads. This is NOT the base URL for the downloads themselves.
- For **local development**, there is a default value in `config/settings.py`
- In **deployed environments**, the valid value is set in `kube/boost/values.yaml` (or the environment-specific yaml file).

### `ARCHIVES_URL`

- Base API endpoint for accessing the archives.boost.io release downloads.
- For **development and production**, there is a default value in `config/settings.py`
- Alternatively, the value can be set in `kube/boost/values.yaml`.

### `MIN_ARTIFACTORY_RELEASE`

- The lowest version of Boost with its downloads stored in JFrog Artifactory
- Hard-coded in `config/settings.py` in all environments

## Boost Google Calendar settings

### `BOOST_CALENDAR`

- Address for the Boost Google Calendar
- Hard-coded in `settings.py` in all environments
### `CALENDAR_API_KEY`

- API key for the Boost Google calendar
- For **local development**, obtain valid value from the Boost team.
- In **deployed environments**, the valid value is set in `kube/boost/values.yaml` (or the environment-specific yaml file).

### `EVENTS_CACHE_KEY` and `EVENTS_CACHE_TIMEOUT`

- The cache key and timeout length for the Google Calendar events
- Hard-coded in `settings.py` in all environments

### `CI`

- If set, will set SITE_ID to 1 in `settings.py`.

### `MAX_CELERY_CONNECTIONS`

- If set, will set the maximum number of connections to the Celery in `settings.py`. Defaults to 60.

### `SLACK_BOT_TOKEN`
- Used to authenticate with the Slack API for pulling data for release reports.

## AI Summarization (OpenRouter)

### `OPENROUTER_API_KEY`

- API key for [OpenRouter](https://openrouter.ai), used by the `openai` SDK to reach the LLM that powers two features:
  - News/blogpost/link entry summaries (`news/tasks.py`)
  - The Boost release-notes "What's New" draft summary (`versions/tasks.py`)
- Default model is `gpt-oss-120b`. To use a different model (e.g. a Claude model via OpenRouter), change `WHATS_NEW_MODEL` in `versions/tasks.py` and the per-handler model strings in `news/tasks.py`.
- For **local development**, set this in your `.env` file. Note: docker compose only loads `env_file` at container creation, so after adding the variable run `docker compose up -d --force-recreate web celery-worker celery-beat` to pick it up.
- In **deployed environments**, set as a kube secret in `kube/boost/values.yaml` (or the environment-specific yaml file).
- Without this variable set, OpenRouter responds with `401 No cookie auth credentials found` and Celery retries the task up to 3 times before giving up.

### `PLAUSIBLE_STATS_KEY`

- API key for the Plausible Analytics API, used to sync per-post page view counts into `Entry.page_views`.
- For **local development**, obtain a valid value from the Boost team.
- In **deployed environments**, the valid value is set in the environment-specific secrets.
- If not set (or set to `changeme`), the sync task is silently skipped.

### `POSTS_RANKING_GRAVITY`

- Controls the decay rate of the posts ranking algorithm (`score = views / (age_hours + 2) ^ gravity`).
- Higher values cause recent posts to decay faster and drop in ranking sooner.
- Defaults to `2.0` if not set.
