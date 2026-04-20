"""Identify commit-author records that represent automation accounts.

Detection is name-based. To exclude a newly discovered bot, add its GitHub
login to ``KNOWN_BOT_NAMES`` (or rely on the ``[bot]`` suffix convention used
by GitHub Apps). Existing ``CommitAuthor`` rows can also be flagged by an
admin via the ``is_bot`` field, which takes precedence regardless of name.
"""

# GitHub Apps commit under usernames suffixed with "[bot]", which the suffix
# check below handles on its own. This list is for the rarer case of bot
# accounts whose commit names do NOT end in "[bot]" -- add their lowercase
# GitHub login here.
KNOWN_BOT_NAMES: frozenset[str] = frozenset(
    {
        "jenkins nedprod ci",
    }
)


def is_bot_name(name: str | None) -> bool:
    if not name:
        return False
    normalized = name.strip().lower()
    if normalized.endswith("[bot]"):
        return True
    return normalized in KNOWN_BOT_NAMES
