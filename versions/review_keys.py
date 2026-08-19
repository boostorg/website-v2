"""Fingerprinting used to deduplicate reviews.

Outside the import command so that a stored ``Review`` can name itself the same
way the importer does.
"""

import re
import unicodedata


def normalize(value: str) -> str:
    """Normalize a field for flexible matching.

    Strips accents, lowercases, and removes every non-alphanumeric character
    (spaces, punctuation, and any other special characters) so that minor
    spelling/formatting differences compare equal. Removing - rather than
    collapsing to a space - is what lets mojibake survivors such as
    ``Johan RÃ¥de`` match the correct ``Johan Råde`` (both become
    ``johanrade``), alongside cases like ``Joaquín M López Muñoz`` vs
    ``Joaquin M Lopez Munoz`` and ``boost::container::hub`` vs ``Boost Container Hub``.
    """
    decomposed = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", without_accents.lower())


def review_key(submission: str, submitter_raw: str, review_dates: str) -> tuple:
    """A flexible, multi-field fingerprint used to deduplicate reviews.

    Dates are part of the key so that a library reviewed more than once (on
    different dates) is kept as separate records, while the same review
    re-imported with minor spelling changes collapses to one.
    """
    return (
        normalize(submission),
        normalize(submitter_raw),
        normalize(review_dates),
    )
