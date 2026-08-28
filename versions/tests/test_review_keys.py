"""Tests for the review fingerprint, now that two callers depend on it.

``import_reviews`` uses it to recognise a review it has already imported.
``Review.dedup_key`` uses it to name that review to the achievement engine. They
are two call sites of one function on purpose: if they ever disagree about what
counts as the same review, review grants duplicate and nothing says so.
"""

import pytest
from model_bakery import baker

from versions.review_keys import normalize, review_key

pytestmark = pytest.mark.django_db


def _review(**overrides):
    """A stored review, overriding any of the three fingerprinted fields."""
    fields = {
        "submission": "Boost.MP11",
        "submitter_raw": "Peter Dimov",
        "review_dates": "April 1-10, 2017",
    }
    fields.update(overrides)
    return baker.make("versions.Review", **fields)


def test_a_review_names_itself_the_way_the_importer_matches_it():
    """The model's key is the importer's fingerprint joined, not a second rule."""
    review = _review()

    assert review.dedup_key == "|".join(
        review_key(review.submission, review.submitter_raw, review.review_dates)
    )


def test_two_spellings_the_importer_would_collapse_share_one_key():
    """The importer keeps one row for these, so the engine must grant once.

    Accents and punctuation are stripped, which is what lets a re-import with
    tidied-up names match the review already on record.
    """
    accented = _review(submitter_raw="Joaquín M López Muñoz")
    plain = _review(submitter_raw="Joaquin M Lopez Munoz")

    assert accented.dedup_key == plain.dedup_key


def test_a_second_review_on_different_dates_keeps_its_own_key():
    """Dates are in the fingerprint so a library reviewed twice counts twice."""
    first = _review(review_dates="April 1-10, 2017")
    second = _review(review_dates="June 1-10, 2021")

    assert first.dedup_key != second.dedup_key


def test_the_separator_cannot_appear_inside_a_component():
    """Which is what makes joining on a pipe unambiguous rather than lossy.

    Normalisation drops every non-alphanumeric character, so no field can smuggle
    a separator in and make two different reviews produce one key.
    """
    review = _review(submission="a|b", submitter_raw="c|d", review_dates="e|f")

    assert review.dedup_key == "ab|cd|ef"
    assert normalize("a|b|c") == "abc"
