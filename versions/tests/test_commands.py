import html
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.exceptions import Exit
from django.core.management import call_command
from model_bakery import baker

from core.models import RenderedContent
from versions.models import Review, ReviewResult

REVIEW_RESULTS_FIXTURE = Path(__file__).parent / "files" / "review-results-sample.html"


@pytest.fixture
def version_with_notes(db):
    v = baker.make(
        "versions.Version",
        name="boost-1.84.0",
        active=True,
        fully_imported=True,
    )
    baker.make(
        RenderedContent,
        cache_key=v.release_notes_cache_key,
        content_html="<p>notes</p>",
    )
    return v


@pytest.fixture
def version_with_notes_and_summary(db):
    v = baker.make(
        "versions.Version",
        name="boost-1.85.0",
        active=True,
        fully_imported=True,
        whats_new="- **New libraries** — already populated.",
    )
    baker.make(
        RenderedContent,
        cache_key=v.release_notes_cache_key,
        content_html="<p>notes</p>",
    )
    return v


@pytest.mark.django_db
def test_generate_whats_new_dry_run_does_not_dispatch(version_with_notes):
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command("generate_whats_new", "--all-missing", "--dry-run")

    mock_dispatch.assert_not_called()


@pytest.mark.django_db
def test_generate_whats_new_all_missing_skips_populated(
    version_with_notes, version_with_notes_and_summary
):
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command("generate_whats_new", "--all-missing")

    mock_dispatch.assert_called_once_with(version_with_notes.pk)


@pytest.mark.django_db
def test_generate_whats_new_force_includes_populated(
    version_with_notes, version_with_notes_and_summary
):
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command("generate_whats_new", "--all-missing", "--force")

    queued_pks = {call.args[0] for call in mock_dispatch.call_args_list}
    assert queued_pks == {version_with_notes.pk, version_with_notes_and_summary.pk}

    # --force only controls which versions are queued; the existing summary
    # is left intact until the chained save task lands its replacement.
    version_with_notes_and_summary.refresh_from_db()
    assert version_with_notes_and_summary.whats_new != ""


@pytest.mark.django_db
def test_generate_whats_new_version_skips_populated_without_force(
    version_with_notes_and_summary,
):
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command(
            "generate_whats_new", "--version", version_with_notes_and_summary.slug
        )

    mock_dispatch.assert_not_called()


@pytest.mark.django_db
def test_generate_whats_new_version_with_force_overrides_populated(
    version_with_notes_and_summary,
):
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command(
            "generate_whats_new",
            "--version",
            version_with_notes_and_summary.slug,
            "--force",
        )

    mock_dispatch.assert_called_once_with(version_with_notes_and_summary.pk)


@pytest.mark.django_db
def test_generate_whats_new_skips_versions_without_release_notes(db):
    baker.make(
        "versions.Version",
        name="boost-1.86.0",
        active=True,
        fully_imported=True,
    )
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command("generate_whats_new", "--all-missing")

    mock_dispatch.assert_not_called()


@pytest.mark.django_db
def test_generate_whats_new_single_version(version_with_notes):
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command("generate_whats_new", "--version", version_with_notes.slug)

    mock_dispatch.assert_called_once_with(version_with_notes.pk)


@pytest.mark.django_db
def test_generate_whats_new_requires_an_action():
    with pytest.raises(Exception):
        # djclick raises UsageError; pytest treats it as failure.
        call_command("generate_whats_new")


@pytest.fixture
def review_results_page():
    """Mock requests.get to serve the review-results fixture page."""
    html = REVIEW_RESULTS_FIXTURE.read_text()
    with patch("versions.management.commands.import_reviews.requests.get") as mock_get:
        mock_get.return_value = Mock(text=html)
        yield mock_get


@pytest.mark.django_db
def test_import_reviews_imports_past_table_only(review_results_page):
    """Every yearly result table is imported; navigation and schedule are skipped."""
    call_command("import_reviews")

    submissions = set(Review.objects.values_list("submission", flat=True))
    assert submissions == {
        "Boost 1.91.0 Released",
        "boost::container::hub",
        "Parser",
    }
    # The Current Schedule row must not be imported.
    assert not Review.objects.filter(submission="Upcoming Library").exists()
    # The section navigation table must not be imported either.
    assert not Review.objects.filter(submission="2026").exists()


@pytest.mark.django_db
def test_import_reviews_creates_milestone_with_notes(review_results_page):
    call_command("import_reviews")

    milestone = Review.objects.get(submission="Boost 1.91.0 Released")
    assert milestone.submitter_raw == "-"
    assert milestone.review_manager_raw == "Marshall Clow"
    assert milestone.review_dates == "April 22, 2026"
    assert milestone.github_link == ""

    result = milestone.results.get()
    assert result.short_description == "Notes"
    assert result.is_most_recent is True
    assert (
        result.announcement_link
        == "https://www.boost.org/users/history/version_1_91_0.html"
    )


@pytest.mark.django_db
def test_import_reviews_captures_github_link(review_results_page):
    call_command("import_reviews")

    review = Review.objects.get(submission="boost::container::hub")
    assert review.github_link == "https://github.com/joaquintides/hub"
    result = review.results.get()
    assert result.short_description == "Accepted"
    assert result.is_most_recent is True


@pytest.mark.django_db
def test_import_reviews_ignores_a_non_github_submission_link(review_results_page):
    """A submission linking somewhere other than GitHub stores no link at all."""
    call_command("import_reviews")

    review = Review.objects.get(submission="Parser")
    assert review.github_link == ""
    assert review.documentation_link == ""


@pytest.mark.django_db
def test_import_reviews_never_touches_a_curated_documentation_link(review_results_page):
    """The field belongs to whoever filled it in, source link or not.

    Asserted on the one row whose submission cell *does* carry a link, because
    that is the case a scraper writing the field would overwrite.
    """
    existing = baker.make(
        Review,
        submission="Parser",
        submitter_raw="Zach Laine",
        review_dates="February 19, 2024 - February 28, 2024",
        documentation_link="https://example.com/curated-parser-docs",
    )

    call_command("import_reviews")

    existing.refresh_from_db()
    assert existing.documentation_link == "https://example.com/curated-parser-docs"


@pytest.mark.django_db
def test_import_reviews_preserves_links_when_source_has_none(review_results_page):
    existing = baker.make(
        Review,
        submission="Boost 1.91.0 Released",
        submitter_raw="-",
        review_dates="April 22, 2026",
        github_link="https://github.com/boostorg/boost",
        documentation_link="https://example.com/curated-release-notes",
    )

    call_command("import_reviews")

    existing.refresh_from_db()
    assert existing.github_link == "https://github.com/boostorg/boost"
    assert existing.documentation_link == "https://example.com/curated-release-notes"


@pytest.mark.django_db
def test_import_reviews_marks_superseded_result_not_recent(review_results_page):
    """A line-through result is superseded; the bare anchor is current."""
    call_command("import_reviews")

    review = Review.objects.get(submission="Parser")
    superseded = review.results.get(short_description="Pending")
    current = review.results.get(short_description="Conditionally Accepted")

    assert superseded.is_most_recent is False
    assert superseded.announcement_link == "https://lists.boost.org/pending"
    assert current.is_most_recent is True
    assert current.announcement_link == "https://lists.boost.org/conditional"


@pytest.mark.django_db
def test_import_reviews_links_submitters_and_managers(review_results_page):
    submitter = baker.make("libraries.CommitAuthor", name="Joaquin M Lopez Munoz")
    manager = baker.make("libraries.CommitAuthor", name="Marshall Clow")

    call_command("import_reviews")

    review = Review.objects.get(submission="boost::container::hub")
    assert list(review.submitters.all()) == [submitter]

    milestone = Review.objects.get(submission="Boost 1.91.0 Released")
    assert milestone.review_manager == manager


@pytest.mark.django_db
def test_import_reviews_reports_only_new_user_links(review_results_page, capsys):
    baker.make("libraries.CommitAuthor", name="Joaquin M Lopez Munoz")
    baker.make("libraries.CommitAuthor", name="Marshall Clow")

    call_command("import_reviews")
    first_output = capsys.readouterr().out
    call_command("import_reviews")
    second_output = capsys.readouterr().out

    assert "Linked 1 submitters and 2 managers" in first_output
    assert "Linked 0 submitters and 0 managers" in second_output


@pytest.mark.django_db
def test_import_reviews_clean_deletes_existing(review_results_page):
    stale = baker.make(Review, submission="Stale", submitter_raw="Someone")
    baker.make(ReviewResult, review=stale, short_description="Old")

    call_command("import_reviews", "--clean")

    assert not Review.objects.filter(submission="Stale").exists()
    assert Review.objects.count() == 3


@pytest.mark.django_db
def test_import_reviews_clean_rolls_back_delete_when_replacement_fails(
    review_results_page,
    catalogue,
):
    from badges.models import Achievement, UserAchievement
    from badges.tests.fixtures import grant_from_source

    stale = baker.make(Review, submission="Stale", submitter_raw="Someone")
    user = baker.make("users.User")
    grant, _ = grant_from_source(
        user, Achievement.objects.get(slug="library-review"), stale
    )

    with patch.object(
        Review.objects, "create", side_effect=RuntimeError("write failed")
    ):
        with pytest.raises(RuntimeError, match="write failed"):
            call_command("import_reviews", "--clean")

    assert Review.objects.filter(pk=stale.pk).exists()
    assert UserAchievement.objects.filter(pk=grant.pk).exists()


@pytest.mark.django_db
def test_import_reviews_is_idempotent(review_results_page):
    """Running the import twice does not create duplicate reviews."""
    call_command("import_reviews")
    call_command("import_reviews")

    assert Review.objects.count() == 3
    # The Parser row still has exactly its two results, not four.
    parser = Review.objects.get(submission="Parser")
    assert parser.results.count() == 2


@pytest.mark.django_db
def test_import_reviews_matches_existing_despite_spelling(review_results_page):
    """A near-duplicate (accents/punctuation) is updated, not duplicated."""
    existing = baker.make(
        Review,
        submission="boost::container::hub",
        # Accented spelling that differs from the ASCII fixture row.
        submitter_raw="Joaquín M López Muñoz",
        review_dates="April 16, 2026 - April 26, 2026",
    )

    call_command("import_reviews")

    assert Review.objects.count() == 3
    existing.refresh_from_db()
    # The same record was updated to the page's spelling.
    assert existing.submitter_raw == "Joaquin M Lopez Munoz"
    assert Review.objects.filter(submission="boost::container::hub").count() == 1


@pytest.mark.django_db
def test_import_reviews_collapses_preexisting_duplicates(review_results_page):
    """Pre-existing rows with the same fingerprint are collapsed to one."""
    for _ in range(2):
        baker.make(
            Review,
            submission="Parser",
            submitter_raw="Zach Laine",
            review_dates="February 19, 2024 - February 28, 2024",
        )

    call_command("import_reviews")

    assert Review.objects.filter(submission="Parser").count() == 1
    assert Review.objects.count() == 3


@pytest.mark.django_db
def test_import_reviews_dedupes_across_special_characters(review_results_page):
    """A DB row differing only by special characters/case dedupes against the page.

    Mirrors the real ``Johan Råde`` vs mojibake ``Johan RÃ¥de`` case: the special
    characters are stripped before comparison, so the existing row is matched
    and updated instead of duplicated.
    """
    existing = baker.make(
        Review,
        submission="BOOST::CONTAINER::HUB!!",
        submitter_raw="joaquin, m. lopez-muñoz",
        review_dates="April 16, 2026 - April 26, 2026",
    )

    call_command("import_reviews")

    assert Review.objects.filter(submission__icontains="hub").count() == 1
    existing.refresh_from_db()
    assert existing.submission == "boost::container::hub"
    assert existing.submitter_raw == "Joaquin M Lopez Munoz"


@pytest.mark.django_db
def test_import_reviews_orders_newest_first_by_id(review_results_page):
    """The newest row on the page gets the highest id (newest-first under -id)."""
    call_command("import_reviews")

    newest = Review.objects.get(submission="Boost 1.91.0 Released")  # first on page
    oldest = Review.objects.get(submission="Parser")  # last on page
    assert newest.id > oldest.id


class _CharsetlessResponse:
    """Minimal stand-in for the real boost.org response.

    The live server sends ``Content-Type: text/html`` with no charset, which
    makes ``requests`` fall back to ISO-8859-1 per RFC 2616 even though the
    body is actually UTF-8. Reading ``.text`` against that default mojibakes
    every accented character.
    """

    def __init__(self, content_bytes: bytes):
        self.content = content_bytes
        self.encoding = "ISO-8859-1"

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding)


@pytest.mark.django_db
def test_import_reviews_decodes_utf8_when_server_omits_charset():
    """Accented names survive an ISO-8859-1-defaulting response intact."""
    inner_html = (
        "<h2>Past Review Results and Milestones</h2>"
        "<table>"
        "  <tr><th>Submission</th><th>Submitter</th><th>Review Manager</th>"
        "<th>Review/Release Dates</th><th>Result</th></tr>"
        "  <tr><td>Foo</td><td>-</td><td>Joaquín M López Muñoz</td>"
        "<td>April 22, 2026</td><td>Released</td></tr>"
        "</table>"
    )
    outer_html = (
        f'<html><body><iframe srcdoc="{html.escape(inner_html)}">'
        "</iframe></body></html>"
    )
    response = _CharsetlessResponse(outer_html.encode("utf-8"))
    existing = baker.make(
        Review,
        submission="Foo",
        submitter_raw="-",
        review_manager_raw="Joaquín M López Muñoz",
        review_dates="April 22, 2026",
    )
    stale_result = baker.make(
        ReviewResult,
        review=existing,
        short_description="Released",
        is_most_recent=False,
        announcement_link="https://example.com/stale",
    )

    with patch("versions.management.commands.import_reviews.requests.get") as mock_get:
        mock_get.return_value = response
        call_command("import_reviews")

    review = Review.objects.get(submission="Foo")
    assert review.review_manager_raw == "Joaquín M López Muñoz"
    # Mojibake artefacts must not survive into the stored data.
    assert "Ã" not in review.review_manager_raw
    assert "Â" not in review.review_manager_raw
    stale_result.refresh_from_db()
    assert stale_result.is_most_recent is True
    assert stale_result.announcement_link == ""


@pytest.mark.django_db
def test_import_reviews_discards_grants_for_collapsed_duplicates(
    review_results_page, catalogue
):
    """Deleting a duplicate review must not leave an achievement counting it.

    ``UserAchievement`` points at its source through a generic FK, so nothing in
    the database stops a grant from outliving the review that justified it.
    """
    from badges.models import Achievement, UserAchievement, UserBadge
    from badges.tests.fixtures import grant_from_source

    reviews = [
        baker.make(
            Review,
            submission="Parser",
            submitter_raw="Zach Laine",
            review_dates="February 19, 2024 - February 28, 2024",
        )
        for _ in range(2)
    ]
    user = baker.make("users.User")
    achievement = Achievement.objects.get(slug="library-review")
    for review in reviews:
        grant_from_source(user, achievement, review)
    assert UserAchievement.objects.count() == 2
    assert UserBadge.objects.filter(user=user, revoked_at__isnull=True).count() == 2

    call_command("import_reviews")

    assert Review.objects.filter(submission="Parser").count() == 1
    assert UserAchievement.objects.count() == 1
    # Reviewer tiers are 1/2/3/4/5, so dropping to one valid grant revokes silver.
    assert UserBadge.objects.filter(user=user, revoked_at__isnull=True).count() == 1


@pytest.mark.django_db
def test_import_reviews_clean_discards_grants(review_results_page, catalogue):
    """--clean wipes every review, so it must wipe their grants too."""
    from badges.models import Achievement, UserAchievement
    from badges.tests.fixtures import grant_from_source

    review = baker.make(Review, submission="Old", submitter_raw="Someone")
    user = baker.make("users.User")
    grant_from_source(user, Achievement.objects.get(slug="library-review"), review)

    call_command("import_reviews", "--clean")

    assert not UserAchievement.objects.filter(source_object_id=review.pk).exists()


@pytest.mark.django_db
def test_import_reviews_fails_when_the_page_has_no_iframe(capsys):
    """A silent return would let the Celery task report a successful no-op."""
    existing = baker.make(Review, submission="Existing", submitter_raw="Someone")
    with patch("versions.management.commands.import_reviews.requests.get") as mock_get:
        mock_get.return_value = Mock(text="<html><body>redesigned</body></html>")
        with pytest.raises(Exit):
            call_command("import_reviews", "--clean")

    assert "Could not find review content" in capsys.readouterr().err
    assert Review.objects.filter(pk=existing.pk).exists()


@pytest.mark.django_db
def test_import_reviews_fails_when_the_heading_is_missing(capsys):
    """The table is located by heading, so a renamed heading must not pass."""
    page = REVIEW_RESULTS_FIXTURE.read_text().replace(
        "Past Review Results and Milestones", "Archive"
    )
    with patch("versions.management.commands.import_reviews.requests.get") as mock_get:
        mock_get.return_value = Mock(text=page)
        with pytest.raises(Exit):
            call_command("import_reviews")

    assert "Could not find review result tables under" in capsys.readouterr().err


@pytest.mark.django_db
def test_import_reviews_clean_keeps_the_badges_it_would_have_revoked(
    review_results_page, catalogue
):
    """A clean re-import replaces the rows; it does not un-earn the badge.

    The fingerprint survives the swap, so the grant is re-pointed at the new row.
    Discarding it instead would cascade-revoke the Reviewer badge, record that
    revocation permanently, and re-earn it dated today on the next sync.
    """
    from badges.models import Achievement, UserAchievement, UserBadge
    from badges.services import recalculate_badges
    from badges.tests.fixtures import grant_from_source

    user = baker.make("users.User")
    submitter = baker.make(
        "libraries.CommitAuthor", user=user, name="Christian Mazakas"
    )
    achievement = Achievement.objects.get(slug="library-review")
    call_command("import_reviews")
    review = Review.objects.get(submission="boost::container::hub")
    review.submitters.add(submitter)
    grant, _ = grant_from_source(user, achievement, review, review.dedup_key)
    recalculate_badges(user.pk, achievement.pk)
    badges = set(UserBadge.objects.values_list("pk", "awarded_at", "revoked_at"))
    assert badges, "nothing was awarded, so the assertion below proves nothing"

    call_command("import_reviews", "--clean")

    replacement = Review.objects.get(submission="boost::container::hub")
    assert replacement.pk != review.pk
    survivor = UserAchievement.objects.get(pk=grant.pk)
    assert survivor.source_object_id == replacement.pk
    assert (
        set(UserBadge.objects.values_list("pk", "awarded_at", "revoked_at")) == badges
    )
