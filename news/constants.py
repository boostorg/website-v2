NEWS_APPROVAL_SALT = "news-approval"
MAGIC_LINK_EXPIRATION = 3600 * 24  # 24h
CONTENT_SUMMARIZATION_THRESHOLD = 1000  # characters
# Target length for the AI-generated Description. Kept under the 1000-char field
# cap so the model has some leeway and the result fits without truncation.
DESCRIPTION_SUMMARY_MAX_LENGTH = 970  # characters
