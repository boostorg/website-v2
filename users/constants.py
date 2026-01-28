from django.utils import timezone

LOGIN_METHOD_SESSION_FIELD_NAME = "boost_login_method"

UNVERIFIED_CLEANUP_DAYS = 14
UNVERIFIED_CLEANUP_BEGIN = timezone.datetime(2025, 11, 21, 0, 0, 0)
