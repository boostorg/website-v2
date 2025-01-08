from libraries.constants import (
    LATEST_RELEASE_URL_PATH_STR,
    LEGACY_LATEST_RELEASE_URL_PATH_STR,
    VERSION_SLUG_PREFIX,
    DEVELOP_RELEASE_URL_PATH_STR,
    MASTER_RELEASE_URL_PATH_STR,
)


def to_python(value):
    if value in (LATEST_RELEASE_URL_PATH_STR, LEGACY_LATEST_RELEASE_URL_PATH_STR):
        return LATEST_RELEASE_URL_PATH_STR
    if value in (DEVELOP_RELEASE_URL_PATH_STR, MASTER_RELEASE_URL_PATH_STR):
        return value
    return f"{VERSION_SLUG_PREFIX}{value.replace('.', '-')}"


def to_url(value):
    if value == LATEST_RELEASE_URL_PATH_STR:
        return LATEST_RELEASE_URL_PATH_STR
    if value:
        value = value.replace(VERSION_SLUG_PREFIX, "").replace("-", ".")
    return value


class BoostVersionSlugConverter:
    regex = r"[a-zA-Z0-9\-\.]+"

    def to_python(self, value):
        return to_python(value)

    def to_url(self, value):
        return to_url(value)
