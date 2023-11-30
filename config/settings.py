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

# Whether or not we're in local development mode
LOCAL_DEVELOPMENT = env.bool("LOCAL_DEVELOPMENT", default=False)

if DEBUG:
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    lh = logging.StreamHandler(sys.stderr)
    root.addHandler(lh)

    env.log_level("LOG_LEVEL", default="DEBUG")

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
    "core",
]

AUTH_USER_MODEL = "users.User"
CSRF_COOKIE_HTTPONLY = True
# See https://docs.djangoproject.com/en/4.2/ref/settings/#csrf-trusted-origins
csrf_trusted_origins = env.list(
    "CSRF_TRUSTED_ORIGINS", default="http://0.0.0.0, http://localhost"
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
                # Our stuff (see core.context_processors.py)
                "core.context_processors.current_release",
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

# This is the directory where all of the collected static files are put
# after running collectstatic
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
handler.setFormatter(jsonlogger.JsonFormatter())

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

# Mailman API credentials
MAILMAN_REST_API_URL = env("MAILMAN_REST_API_URL", default="http://localhost:8001")
MAILMAN_REST_API_USER = env("MAILMAN_REST_API_USER", default="restadmin")
MAILMAN_REST_API_PASS = env("MAILMAN_REST_API_PASS", default="restpass")
MAILMAN_ARCHIVER_KEY = env("MAILMAN_ARCHIVER_KEY", default="password")
MAILMAN_ELASTIC_INDEX = env("MAILMAN_ELASTIC_INDEX", default="haystack")
MAILMAN_HAYSTACK_URL = env("MAILMAN_HAYSTACK_URL", default="http://127.0.0.1:9200/")

# Must still be configured:
HAYSTACK_CONNECTIONS = {
    "default": {
        "ENGINE": "haystack.backends.elasticsearch7_backend.Elasticsearch7SearchEngine",
        "URL": MAILMAN_HAYSTACK_URL,
        "INDEX_NAME": MAILMAN_ELASTIC_INDEX,
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

AUTHENTICATION_BACKENDS = ("allauth.account.auth_backends.AuthenticationBackend",)

# GitHub settings

GITHUB_TOKEN = env("GITHUB_TOKEN", default=None)
JDOODLE_API_CLIENT_ID = env("JDOODLE_API_CLIENT_ID", "")
JDOODLE_API_CLIENT_SECRET = env("JDOODLE_API_CLIENT_SECRET", "")

# Django Allauth settings

SITE_ID = 1
ACCOUNT_EMAIL_VERIFICATION = "none"
LOGIN_REDIRECT_URL = "home"
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
SOCIALACCOUNT_QUERY_EMAIL = True
ACCOUNT_UNIQUE_EMAIL = True

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
        },
    }
}

# Allow Allauth to use HTTPS when deployed but HTTP for local dev
SECURE_PROXY_SSL_HEADER_NAME = env("SECURE_PROXY_SSL_HEADER_NAME", default=None)
SECURE_PROXY_SSL_HEADER_VALUE = env("SECURE_PROXY_SSL_HEADER_VALUE", default=None)
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT", default=False)

if not LOCAL_DEVELOPMENT:
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

if all(
    [SECURE_PROXY_SSL_HEADER_NAME, SECURE_PROXY_SSL_HEADER_VALUE, SECURE_SSL_REDIRECT]
):
    SECURE_PROXY_SSL_HEADER = (
        SECURE_PROXY_SSL_HEADER_NAME,
        SECURE_PROXY_SSL_HEADER_VALUE,
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
    "STATIC_CONTENT_AWS_S3_ENDPOINT_URL", default="https://s3.us-east-2.amazonaws.com"
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
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
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

# Artifactory settings
ARTIFACTORY_URL = env(
    "ARTIFACTORY_URL", default="https://boostorg.jfrog.io/artifactory/api/storage/main/"
)

# The min Boost version is the oldest version of Boost that our import scripts
# will retrieve. It's determined by the files we store in the archives/ in S3.
MINIMUM_BOOST_VERSION = "1.31.0"
