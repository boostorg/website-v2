from enum import Enum
from urllib.parse import urlparse

from config.settings import MAILMAN_REST_API_URL


def get_domain_with_subdomains(url: str) -> str:
    """
    Extracts the full domain (including subdomains) from a given URL.
    """
    # If the URL doesn't start with a scheme, urlparse might not parse it correctly.
    # We prepend '//' to handle scheme-less URLs properly.
    if not url.startswith(("http://", "https://", "//")):
        url = "//" + url

    parsed_url = urlparse(url)

    # .netloc extracts the network location (domain + port if present)
    # We split by ':' to remove the port number just in case it's included.
    domain = parsed_url.netloc.split(":")[0]

    return domain


MAILMAN_DOMAIN = get_domain_with_subdomains(MAILMAN_REST_API_URL)


def build_mailing_list_address(list_name: str) -> str:
    return f"{list_name}@{MAILMAN_DOMAIN}"


class MailingLists(Enum):
    BOOST = "boost"
    BOOST_ANNOUNCE = "boost-announce"
    BOOST_USERS = "boost-users"


MAILING_LIST_LABELS = {
    MailingLists.BOOST.value: {
        "id": f"{MailingLists.BOOST.value}.{MAILMAN_DOMAIN}",
        "name": "Boost Developers",
        "address": build_mailing_list_address(MailingLists.BOOST.value),
        "description": (
            "The primary discussion list for Boost library developers. Topics cover "
            "library submission, development, review, and project-wide decisions. "
            "Posts from non-subscribers are automatically rejected, and first-time "
            "posts are moderated. Please read the discussion policy before posting: "
            "https://www.boost.org/doc/user-guide/discussion-policy.html"
        ),
    },
    MailingLists.BOOST_ANNOUNCE.value: {
        "id": f"{MailingLists.BOOST_ANNOUNCE.value}.{MAILMAN_DOMAIN}",
        "name": "Boost Announcements",
        "address": build_mailing_list_address(MailingLists.BOOST_ANNOUNCE.value),
        "description": (
            "A low-volume, announce-only list for upcoming Boost formal reviews and "
            "new software releases. A good fit if you want to stay informed without "
            "following the high-volume developer discussion."
        ),
    },
    MailingLists.BOOST_USERS.value: {
        "id": f"{MailingLists.BOOST_USERS.value}.{MAILMAN_DOMAIN}",
        "name": "Boost Users",
        "address": build_mailing_list_address(MailingLists.BOOST_USERS.value),
        "description": (
            "Discussion list for developers using the Boost C++ libraries. The right "
            "place to ask questions, share solutions, and get help integrating Boost "
            "into your projects. Please read the discussion policy before posting: "
            "https://www.boost.org/doc/user-guide/discussion-policy.html"
        ),
    },
}

MAILMAN_LISTS = [_l["id"] for _l in MAILING_LIST_LABELS.values()]

# we only want boost devel for now, leaving the others in case that changes.
ML_STATS_URLS = [
    "https://lists.boost.org/Archives/boost/{:04}/{:02}/author.php",
    # "https://lists.boost.org/boost-users/{:04}/{:02}/author.php",
    # "https://lists.boost.org/boost-announce/{:04}/{:02}/author.php",
]
ARG_DATE_REGEX = r"^([0-9]+)(?:$|(?:-|/)([0-9]+)(?:$|(?:-|/)([0-9]+)$))"
AUTHOR_PATTERN_REGEX = r"<li><strong>(.*)</strong>"
DATE_PATTERN_REGEX = r".*<em>\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)</em>"

# used to map latin-1 characters to their utf-8 equivalents in the mailing list
# page html parser
LATIN_1_EQUIVS = {
    8364: 128,
    8218: 130,
    402: 131,
    8222: 132,
    8230: 133,
    8224: 134,
    8225: 135,
    710: 136,
    8240: 137,
    352: 138,
    8249: 139,
    338: 140,
    381: 142,
    8216: 145,
    8217: 146,
    8220: 147,
    8221: 148,
    8226: 149,
    8211: 150,
    8212: 151,
    732: 152,
    8482: 153,
    353: 154,
    8250: 155,
    339: 156,
    382: 158,
    376: 159,
}
