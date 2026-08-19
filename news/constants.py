NEWS_APPROVAL_SALT = "news-approval"
MAGIC_LINK_EXPIRATION = 3600 * 24  # 24h
CONTENT_SUMMARIZATION_THRESHOLD = 1000  # characters
# Target length for the AI-generated Description. Kept under the 1000-char field
# cap so the model has some leeway and the result fits without truncation.
DESCRIPTION_SUMMARY_MAX_LENGTH = 900  # characters

# Shown to a user who has spent their daily generations. Returned by both
# generation endpoints so the copy can't drift between them and the template.
DESCRIPTION_RATE_LIMIT_MESSAGE = (
    "You've used all your description generations for today. The limit resets "
    "at midnight UTC. You can write the description yourself in the meantime "
    "— your draft is saved."
)

# Shown when someone tries to save a limit below one generation.
DAILY_LIMIT_MIN_MESSAGE = (
    "Enter a positive number of generations. To stop generation entirely, "
    "remove access to the create-post page instead."
)

# Wagtail log action recording a limit change with its old and new values.
AI_DESCRIPTION_LIMIT_CHANGED_ACTION = "news.ai_description_limit_changed"

# Group whose members skip the daily cap. Membership is managed in the Django
# admin so the exempt set can change without a deploy; the group is seeded with
# `BYPASS_DESCRIPTION_LIMIT_PERMISSION` by a data migration.
RATELIMIT_EXEMPT_GROUP = "ratelimit_exempt"
BYPASS_DESCRIPTION_LIMIT_PERMISSION = "bypass_description_generation_limit"
