import logging

from .settings import *  # noqa


# Disable migrations for all-the-things
class DisableMigrations(object):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


# Disable our logging
logging.disable(logging.CRITICAL)

CELERY_TASK_ALWAYS_EAGER = True

DEBUG = False

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

MIGRATION_MODULES = DisableMigrations()

# User a faster password hasher
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

GITHUB_TOKEN = "changeme"

BASE_CONTENT = "/code/core/tests/content"
