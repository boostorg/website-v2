import logging
import os
import subprocess
import sys
from pathlib import Path

import environs
import structlog
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured
from pythonjsonlogger import jsonlogger

env = environs.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
if READ_DOT_ENV_FILE:
    env.read_env()
    print("The .env file has been loaded. See config/settings.py for more information")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DJANGO_DEBUG", default=False)
DEBUG_TOOLBAR = env.bool("DEBUG_TOOLBAR", default=False)

if DEBUG:
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    lh = logging.StreamHandler(sys.stderr)
    root.addHandler(lh)

    env.log_level("LOG_LEVEL", default="DEBUG")

# Whether or not we're in local development mode
LOCAL_DEVELOPMENT = env.bool("LOCAL_DEVELOPMENT", default=False)
CI = env.bool("CI", default=False)

if CI or LOCAL_DEVELOPMENT:
    # This is the default value for the development environment.
    # This enables the tests to run.
    SITE_ID = 1

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = Path(__file__).parent.parent
APPS_DIR = BASE_DIR.joinpath("config")


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")


host_list = env.list("ALLOWED_HOSTS", default="localhost")
ALLOWED_HOSTS = [el.strip() for el in host_list]


INSTALLED_APPS = [
    "django_admin_env_notice",  # Third-party
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.postgres",
]

# Third-party apps
INSTALLED_APPS += [
    "anymail",
    "rest_framework",
    "corsheaders",
    "django_extensions",
    "health_check",
    "health_check.db",
    "health_check.contrib.celery",
    "imagekit",
    # Allows authentication for Mailman
    "oauth2_provider",
    # Allauth dependencies:
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.github",
    "allauth.socialaccount.providers.google",
    "mptt",
    "haystack",
    "widget_tweaks",
]

# Our Apps
INSTALLED_APPS += [
    "ak",
    "users",
    "versions",
    "libraries",
    "mailing_list",
    "news",
    "reports",
    "core",
    "slack",
]

AUTH_USER_MODEL = "users.User"
CSRF_COOKIE_HTTPONLY = True
# See https://docs.djangoproject.com/en/4.2/ref/settings/#csrf-trusted-origins
csrf_trusted_origins = env.list(
    "CSRF_TRUSTED_ORIGINS", default=["http://0.0.0.0", "http://localhost"]
)
CSRF_TRUSTED_ORIGINS = [el.strip() for el in csrf_trusted_origins]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "tracer.middleware.RequestID",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "oauth2_provider.middleware.OAuth2TokenMiddleware",
]

if DEBUG:
    # These are necessary to turn on Whitenoise which will serve our static
    # files while doing local development
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")
    WHITENOISE_USE_FINDERS = True
    WHITENOISE_AUTOREFRESH = True

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            str(BASE_DIR.joinpath("templates")),
        ],
        "OPTIONS": {
            "context_processors": [
                # Django Admin Env Notice
                "django_admin_env_notice.context_processors.from_settings",
                # Django stuff
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.current_version",
                "core.context_processors.active_nav_item",
                "core.context_processors.debug",
            ],
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

try:
    DATABASES = {"default": env.dj_db_url("DATABASE_URL")}
except (ImproperlyConfigured, environs.EnvError):
    DATABASES = {
        "default": {
            "ENGINE": "django_db_geventpool.backends.postgresql_psycopg2",
            "HOST": env("PGHOST"),
            "NAME": env("PGDATABASE"),
            "PASSWORD": env("PGPASSWORD"),
            "PORT": env.int("PGPORT", default=5432),
            "USER": env("PGUSER"),
            "CONN_MAX_AGE": 0,
            "OPTIONS": {"MAX_CONNS": env("MAX_CONNECTIONS", default=20)},
        }
    }

# Password validation
# Only used in production
AUTH_PASSWORD_VALIDATORS = []

# Sessions

# Give each project their own session cookie name to avoid local development
# login conflicts
SESSION_COOKIE_NAME = "config-sessionid"

# Increase default cookie age from 2 to 12 weeks
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7 * 12

# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

# The relative URL of where we serve our static files from
STATIC_URL = "/static/"

# Additional directories from where we should collect static files from
STATICFILES_DIRS = [
    BASE_DIR.joinpath("static"),
]

# Directory where collectstatic puts static files
STATIC_ROOT = str(BASE_DIR.joinpath("static_deploy"))

# Directory where uploaded media is saved.
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
# Public URL at the browser
MEDIA_URL = "/media/"

# Logging setup
# Configure struct log
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.render_to_log_kwargs,
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Configure Python logging
root = logging.getLogger()
root.setLevel(logging.INFO)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    jsonlogger.JsonFormatter(
        "%(name)s %(levelname)s %(filename)s:%(lineno)d %(message)s"
    )
)

if LOCAL_DEVELOPMENT:
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

root.addHandler(handler)

# Configure Redis
REDIS_HOST = env("REDIS_HOST", default="redis")

# Configure Celery
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:6379"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:6379"
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "max_connections": env.int("MAX_CELERY_CONNECTIONS", default=60)
}
CELERY_RESULT_BACKEND_THREAD_SAFE = True
CELERY_TASK_ALWAYS_EAGER = env("CELERY_TASK_ALWAYS_EAGER", False)

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:6379",
    },
    "static_content": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:6379/2",
        "TIMEOUT": env(
            "STATIC_CACHE_TIMEOUT", default="60"
        ),  # Cache timeout in seconds: 1 minute
    },
}

ENABLE_DB_CACHE = env.bool("ENABLE_DB_CACHE", default=False)

# Default interval by which to clear the static content cache
CLEAR_STATIC_CONTENT_CACHE_DAYS = 7

# Hyperkitty
HYPERKITTY_DATABASE_NAME = env("HYPERKITTY_DATABASE_NAME", default="")
if HYPERKITTY_DATABASE_NAME:
    HYPERKITTY_DATABASE_URL = "postgresql://{}:{}@{}:{}/{}".format(
        DATABASES["default"]["USER"],
        DATABASES["default"]["PASSWORD"],
        DATABASES["default"]["HOST"],
        DATABASES["default"]["PORT"],
        HYPERKITTY_DATABASE_NAME,
    )
else:
    HYPERKITTY_DATABASE_URL = ""

MAILMAN_CORE_DATABASE = env("MAILMAN_CORE_DATABASE", default="unknown")

# Fastly API credentials
FASTLY_SERVICE = env("FASTLY_SERVICE", default="empty")
FASTLY_SERVICE2 = env("FASTLY_SERVICE2", default="empty")
FASTLY_API_TOKEN = env("FASTLY_API_TOKEN", default="empty")

HAYSTACK_CONNECTIONS = {
    "default": {
        "ENGINE": "haystack.backends.simple_backend.SimpleEngine",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

AUTHENTICATION_BACKENDS = (
    "allauth.account.auth_backends.AuthenticationBackend",
    "oauth2_provider.backends.OAuth2Backend",
)

# GitHub settings

GITHUB_TOKEN = env("GITHUB_TOKEN", default=None)
JDOODLE_API_CLIENT_ID = env("JDOODLE_API_CLIENT_ID", "")
JDOODLE_API_CLIENT_SECRET = env("JDOODLE_API_CLIENT_SECRET", "")

# Django Allauth settings

ACCOUNT_EMAIL_VERIFICATION = "mandatory"
LOGIN_REDIRECT_URL = "home"
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_LOGIN_ON_GET = True
ACCOUNT_UNIQUE_EMAIL = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# Allow us to override some of allauth's forms
ACCOUNT_FORMS = {
    "reset_password_from_key": "users.forms.CustomResetPasswordFromKeyForm",
}

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
            "prompt": "select_account",
        },
        "OAUTH_PKCE_ENABLED": True,
    },
    "github": {},
}
if LOCAL_DEVELOPMENT:
    github_oauth_client_id = env("GITHUB_OAUTH_CLIENT_ID", default=None)
    github_oauth_secret = env("GITHUB_OAUTH_CLIENT_SECRET", default=None)
    if not github_oauth_client_id or not github_oauth_secret:
        logging.warning("Github OAuth credentials not set")
    else:
        SOCIALACCOUNT_PROVIDERS["github"] = {
            "APPS": [
                {
                    "client_id": github_oauth_client_id,
                    "secret": github_oauth_secret,
                }
            ]
        }
    google_oauth_client_id = env("GOOGLE_OAUTH_CLIENT_ID", default=None)
    google_oauth_secret = env("GOOGLE_OAUTH_CLIENT_SECRET", default=None)
    if not google_oauth_client_id or not google_oauth_secret:
        logging.warning("Google OAuth credentials not set")
    else:
        SOCIALACCOUNT_PROVIDERS["google"]["APPS"] = [
            {
                "client_id": google_oauth_client_id,
                "secret": google_oauth_secret,
            },
        ]


if not LOCAL_DEVELOPMENT:
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        ACCOUNT_DEFAULT_HTTP_PROTOCOL,
    )

# Admin banner configuration
ENV_NAME = env("ENVIRONMENT_NAME", default="Unknown Environment")
IMAGE_TAG = env("IMAGE_TAG", default="Unknown Version")

if LOCAL_DEVELOPMENT:
    try:
        output = subprocess.check_output(
            ["git", "describe", "--tags"], universal_newlines=True
        )
        IMAGE_TAG = str(output.strip())
    except Exception:
        print("WARNING: Unable to run git, unable to determine local image tag")
        IMAGE_TAG = "UNKNOWN-VERSION"

ENVIRONMENT_NAME = f"{ENV_NAME} - {IMAGE_TAG}"

ENVIRONMENT_COLOR = "#718096"  # Gray for unknown

if ENV_NAME == "Development Environment":
    ENVIRONMENT_COLOR = "#38A169"  # Green
elif ENV_NAME == "Production Environment":
    ENVIRONMENT_COLOR = "#E53E3E"

# S3 Compatiable Storage Settings
if not LOCAL_DEVELOPMENT:
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="changeme")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="changeme")
    MEDIA_BUCKET_NAME = env("MEDIA_BUCKET_NAME", default="changeme")
    AWS_STORAGE_BUCKET_NAME = MEDIA_BUCKET_NAME
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    AWS_DEFAULT_ACL = None
    AWS_S3_ENDPOINT_URL = env(
        "AWS_S3_ENDPOINT_URL", default="https://sfo2.digitaloceanspaces.com"
    )
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="sfo2")
    STORAGES = {
        "default": {"BACKEND": "core.storages.MediaStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
    MEDIA_URL = f"{AWS_S3_ENDPOINT_URL}/{MEDIA_BUCKET_NAME}/"

# Staticly rendered content from S3 such as Antora docs, etc
STATIC_CONTENT_AWS_ACCESS_KEY_ID = env(
    "STATIC_CONTENT_AWS_ACCESS_KEY_ID", default="changeme"
)
STATIC_CONTENT_AWS_SECRET_ACCESS_KEY = env(
    "STATIC_CONTENT_AWS_SECRET_ACCESS_KEY", default="changeme"
)
STATIC_CONTENT_BUCKET_NAME = env("STATIC_CONTENT_BUCKET_NAME", default="changeme")

STATIC_CONTENT_REGION = env("STATIC_CONTENT_REGION", default="us-east-2")

STATIC_CONTENT_AWS_S3_ENDPOINT_URL = env(
    "STATIC_CONTENT_AWS_S3_ENDPOINT_URL",
    default="https://s3.dualstack.us-east-2.amazonaws.com",
)

# LinkPreview API Key
# LINK_PREVIEW_API_KEY = env(
#     "LINK_PREVIEW_API_KEY", default="changeme"
# )

# JSON configuration of how we map static content in the S3 buckets to URL paths
STATIC_CONTENT_MAPPING = env(
    "STATIC_CONTENT_MAPPING", default="stage_static_config.json"
)

# Markdown content
BASE_CONTENT = env("BOOST_CONTENT_DIRECTORY", "/website")

# News: list of users who are allowed to post without requiring moderation.
# This complements the 'moderator' Group that also have posting privileges.
NEWS_MODERATION_ALLOWLIST = [
    # Add either a user's email address or a User instance PK. Mixing emails
    # with PKs is safe since users.User's PKs are integers.
]

# EMAIL SETTINGS -- THESE NEED ADJUSTMENT WHEN DECIDED WHICH ESP WILL BE USED
EMAIL_HOST = "maildev"
EMAIL_PORT = 1025
DEFAULT_FROM_EMAIL = "boost@cppalliance.org"
SERVER_EMAIL = "errors@cppalliance.org"

# Deployed email configuration
if LOCAL_DEVELOPMENT:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
    ANYMAIL = {
        "MAILGUN_API_KEY": env("MAILGUN_API_KEY", default="changeme"),
        "MAILGUN_SENDER_DOMAIN": env(
            "MAILGUN_SENDER_DOMAIN", default="boost.revsys.dev"
        ),
    }

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
SESSION_COOKIE_HTTPONLY = False

CORS_ALLOW_METHODS = (
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
)

CORS_ALLOW_HEADERS = (
    *default_headers,
    "hx-request",
    "hx-target",
    "hx-current-url",
    "credentials",
)

# Legacy Artifactory settings
# Please note that these settings are not used in the current version of the site,
# but are kept here for reference.
ARTIFACTORY_URL = env(
    "ARTIFACTORY_URL", default="https://boostorg.jfrog.io/artifactory/api/storage/main/"
)
MIN_ARTIFACTORY_RELEASE = "boost-1.63.0"

# archives.boost.io settings
# This is the URL where the archives.boost.io site is hosted.
ARCHIVES_URL = env("ARCHIVES_URL", default="https://archives.boost.io/")
MIN_ARCHIVES_RELEASE = "boost-1.63.0"

# The min Boost version is the oldest version of Boost that our import scripts
# will retrieve.
MINIMUM_BOOST_VERSION = "1.16.1"
# The highest Boost version with its docs stored in S3
MAXIMUM_BOOST_DOCS_VERSION = "boost-1.30.2"

# In Progress Release Notes URL
RELEASE_NOTES_IN_PROGRESS_URL = "https://raw.githubusercontent.com/boostorg/website/master/users/history/in_progress.html"
RELEASE_NOTES_IN_PROGRESS_CACHE_KEY = "release-notes-in-progress"

# Boost Google Calendar
BOOST_CALENDAR = "5rorfm42nvmpt77ac0vult9iig@group.calendar.google.com"
CALENDAR_API_KEY = env("CALENDAR_API_KEY", default="changeme")
EVENTS_CACHE_KEY = "homepage_events"
EVENTS_CACHE_TIMEOUT = 300  # 5 min

# OAuth settings
OAUTH_APP_NAME = (
    "Boost OAuth Concept"  # Stored in the admin; replicated for convenience
)

# Frame loading
X_FRAME_OPTIONS = "SAMEORIGIN"

SLACK_BOT_TOKEN = env("SLACK_BOT_TOKEN", default="")

ACCOUNT_DELETION_GRACE_PERIOD_DAYS = 10

if DEBUG_TOOLBAR:
    INSTALLED_APPS += ["debug_toolbar"]
    INTERNAL_IPS = ["127.0.0.1", "localhost"]
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": lambda x: True,
        "ROOT_TAG_EXTRA_ATTRS": "hx-preserve",
    }
    MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")

BOOST_BRANCHES = ["master", "develop"]
