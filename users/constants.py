from datetime import timedelta

from django.utils import timezone

LOGIN_METHOD_SESSION_FIELD_NAME = "boost_login_method"

GITHUB_PROVIDER = "github"
GITHUB_ACTIVITY_CARD_TITLE = "Latest Boost Github activity"
# Stored GitHub activity older than this is refreshed on the next profile load.
GITHUB_ACTIVITY_STALE_AFTER = timedelta(hours=24)
# Guards against re-queueing a refresh on every page load while one is running,
# and against hammering GitHub when a refresh is failing.
GITHUB_ACTIVITY_REFRESH_LOCK_SECONDS = 300
# The card polls itself while a refresh runs, then gives up and asks the user to
# reload, so a failing refresh cannot poll forever.
GITHUB_ACTIVITY_POLL_INTERVAL_SECONDS = 5
GITHUB_ACTIVITY_POLL_MAX_ATTEMPTS = 12

UNVERIFIED_CLEANUP_DAYS = 14
UNVERIFIED_CLEANUP_BEGIN = timezone.datetime(2025, 11, 21, 0, 0, 0)

# Advisory-lock key serializing recompute_displayed_profile_roles (arbitrary,
# must not collide with other pg_advisory_lock callers).
PROFILE_ROLE_RECOMPUTE_LOCK = 4815162
