from django.utils.crypto import get_random_string
from django.utils.text import slugify

ROUTING_KEY_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
ROUTING_KEY_SUFFIX_LENGTH = 4
# A name with no ASCII slug leaves nothing identifying in the key, so the
# random part carries the whole thing and is longer to match.
ROUTING_KEY_FALLBACK_BASE = "user"
ROUTING_KEY_FALLBACK_SUFFIX_LENGTH = 8


def routing_key_base(display_name, max_length):
    """The kebab-case stem of a routing key, or "" if the name has no slug.

    Truncation can land mid-word and leave a trailing hyphen, which would
    otherwise render as "jane-doe--k3f9".
    """
    return slugify(display_name or "")[:max_length].rstrip("-")


def generate_routing_key(display_name, max_length):
    """A public profile URL segment for a user with this display name.

    The random suffix is what makes the key unique: display_name has no
    unique constraint, and unvalidated write paths (social login, admin) can
    duplicate it. It also keeps a key from ever colliding with a reserved
    segment under /users/, such as "me".
    """
    suffix_length = ROUTING_KEY_SUFFIX_LENGTH
    base = routing_key_base(display_name, max_length - suffix_length - 1)
    if not base:
        base = ROUTING_KEY_FALLBACK_BASE
        suffix_length = ROUTING_KEY_FALLBACK_SUFFIX_LENGTH
    return f"{base}-{get_random_string(suffix_length, ROUTING_KEY_ALPHABET)}"


def humanize_link_lifetime(delta):
    """Return a short phrase for a link lifetime, e.g. "3 days" or "1 hour".

    Picks the largest whole unit so the copy reads naturally for whole-day or
    whole-hour settings, and pluralizes correctly (so a one-day or one-hour
    timeout never renders as "1 days" / "0 days").
    """
    seconds = int(delta.total_seconds())
    for unit_seconds, name in ((86400, "day"), (3600, "hour"), (60, "minute")):
        count = seconds // unit_seconds
        if count:
            return f"{count} {name}{'' if count == 1 else 's'}"
    return f"{seconds} second{'' if seconds == 1 else 's'}"
