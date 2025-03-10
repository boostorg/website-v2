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
