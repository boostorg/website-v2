import logging
from .settings import *  # noqa


# Disable migrations for all-the-things
class DisableMigrations(object):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

    def setdefault(self, key, default=None):
        return None


# Disable our logging
logging.disable(logging.CRITICAL)

CELERY_TASK_ALWAYS_EAGER = True

DEBUG = False

# Disable debug toolbar in tests
DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: False,
}

OAUTH2_PROVIDER_APPLICATION_MODEL = "oauth2_provider.Application"
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = "oauth2_provider.AccessToken"
OAUTH2_PROVIDER_ID_TOKEN_MODEL = "oauth2_provider.IDToken"
OAUTH2_PROVIDER_GRANT_MODEL = "oauth2_provider.Grant"
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = "oauth2_provider.RefreshToken"

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

MIGRATION_MODULES = DisableMigrations()

# User a faster password hasher
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

GITHUB_TOKEN = "changeme"

# Make content relative to the project root
BASE_CONTENT = BASE_DIR / "core/tests/content"  # noqa

# Don't use S3 in tests
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
