import re
from enum import Enum, StrEnum


class SourceDocType(Enum):
    ASCIIDOC = "asciidoc"
    ANTORA = "antora"


class BadgeToken(StrEnum):
    """Tokens accepted by templates/v3/includes/_badge_v3.html.

    Keep in sync with the conditional branches in that template.
    """

    TIER_1 = "badge-tier-1"
    TIER_2 = "badge-tier-2"
    TIER_3 = "badge-tier-3"
    TIER_4 = "badge-tier-4"
    TIER_5 = "badge-tier-5"
    STAR_TIER_1 = "star-tier-1"
    STAR_TIER_2 = "star-tier-2"
    STAR_TIER_3 = "star-tier-3"
    STAR_TIER_4 = "star-tier-4"
    STAR_TIER_5 = "star-tier-5"
    BOOST_DAY = "boost-day"
    ACHIEVEMENT_COUNT = "achievement-count"


# Rows shown in the Achievements and Badges dialogs, transcribed from Figma.
# These explain how recognition works rather than reporting one user's standing.
# That's why they are static copy.
ACHIEVEMENTS_DIALOG_ITEMS = [
    {
        "token": BadgeToken.ACHIEVEMENT_COUNT,
        "count": 1,
        "name": "Library Author",
        "description": "Earned through number of libraries authored.",
    },
    {
        "token": BadgeToken.ACHIEVEMENT_COUNT,
        "count": 1,
        "name": "Commits Master",
        "description": "Earned through number of code commits authored",
    },
    {
        "token": BadgeToken.ACHIEVEMENT_COUNT,
        "count": 1,
        "name": "Version Author",
        "description": "Earned through number of library versions authored",
    },
    {
        "token": BadgeToken.ACHIEVEMENT_COUNT,
        "count": 1,
        "name": "Reviewer",
        "description": (
            "Earned through formal mailing list reviews of library proposals, "
            "awarded by Review Managers for substantive contributions."
        ),
    },
    {
        "token": BadgeToken.BOOST_DAY,
        "name": "Boost day celebration",
        "description": (
            "A celebration of the day you joined Boost. Awarded annually to "
            "mark another year as part of the community."
        ),
    },
    {
        "token": BadgeToken.ACHIEVEMENT_COUNT,
        "count": 1,
        "name": "Publisher",
        "description": "Earned through number of posts published.",
    },
]

BADGES_DIALOG_ITEMS = [
    {
        "token": BadgeToken.TIER_1,
        "name": "Achievement-based",
        "description": (
            "Reflects the depth of your contributions. Accumulate achievements "
            "to unlock five tiers; Bronze, Silver, Gold, Platinum and Diamond."
        ),
    },
    {
        "token": BadgeToken.STAR_TIER_1,
        "name": "Tenure-based",
        "description": (
            "Awarded in recognition of your time on the platform. The longer "
            "you've been part of the Boost community, the higher the tier you "
            "unlock."
        ),
    },
]

ACHIEVEMENTS_DIALOG_DESCRIPTION = (
    "Achievements capture your contributions to Boost — automatically tracked "
    "where possible, manually verified for high-value activities."
)

BADGES_DIALOG_DESCRIPTION = (
    "Badges recognize your journey on Boost — from the contributions you make "
    "to the time you've invested and the milestones you've reached along the way."
)

SLACK_URL = "https://cpplang.slack.com"
SLACK_JOIN_URL = "https://cppalliance.org/slack/"  # URL to join the Slack workspace, not the Slack workspace itself
SLACK_MEMBER_COUNT = "24,000+"
STATIC_CONTENT_EARLY_EXIT_PATH_PREFIXES = ("releases/",)
# possible library versions are: boost_1_53_0_beta1, 1_82_0, 1_55_0b1
BOOST_LIB_PATH_RE = re.compile(r"^(boost_){0,1}([0-9_]*[0-9]+[^/]*)/(.*)")
BOOST_VERSION_REGEX = r"(boost_){0,1}([0-9_]*[0-9]+[^/]*)"
NO_PROCESS_LIBS = [
    # Do nothing with these - just render contents directly
    "libs/filesystem",
    "libs/gil",
    "libs/hana",
    "libs/locale",
    "libs/iostreams",
    "libs/preprocessor",
    "libs/serialization",
    "libs/wave",
]
NO_WRAPPER_LIBS = [
    # Add a header to these, but no wrapper.
    "libs/array",
    "libs/assert",
    "libs/bloom",
    "libs/charconv",
    "libs/cobalt",
    "libs/compat",
    "libs/container_hash",
    "libs/describe",
    "libs/endian",
    "libs/exception",
    "libs/hash2",
    "libs/io",
    "libs/lambda2",
    "libs/leaf",
    "libs/mp11",
    "libs/predef",
    "libs/process",
    "doc/html/process",
    "libs/property_map_parallel",
    "libs/qvm",
    "libs/redis",
    "libs/smart_ptr",
    "libs/system",
    "libs/throw_exception",
    "libs/unordered",
    "libs/uuid",
    "libs/variant2",
]
FULLY_MODERNIZED_LIB_VERSIONS = [
    # FIXME: we should have a way to opt-in via a flag on the library/lib-version.
    #  Hard-coding these here as a quick fix for now.
    # TODO: create a ticket for this
    "tools/",  # Not a library version, but tools are somewhat analogous
    "1_87_0/libs/charconv",
    "1_88_0/libs/charconv",
    "1_89_0/libs/charconv",
    "latest/libs/charconv",
    "develop/libs/charconv",
    "master/libs/charconv",
    "1_89_0/libs/redis",
    "latest/libs/redis",
    "develop/libs/redis",
    "master/libs/redis",
    "doc/antora/url",
]
RENDERED_CONTENT_BATCH_DELETE_SIZE = 10000

# How many popular search terms the V3 homepage renders.
HOMEPAGE_POPULAR_TERMS_DISPLAY = 10
