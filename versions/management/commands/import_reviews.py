import html
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import djclick as click
import requests

from django.core.management.base import CommandError
from django.db import transaction

from badges.services import (
    discard_source_achievements,
    relink_source_achievements,
)
from libraries.models import CommitAuthor
from versions.models import Review, ReviewResult
from versions.review_keys import review_key

PAST_RESULTS_HEADING = "Past Review Results and Milestones"
PAST_RESULTS_HEADER = (
    "Submission",
    "Submitter",
    "Review Manager",
    "Review/Release Dates",
    "Result",
)
REQUEST_TIMEOUT_SECONDS = 30


@click.command()
@click.option(
    "--clean", is_flag=True, help="Start by deleting all previously imported reviews"
)
def command(clean):
    """Import Boost library reviews from boost.org table data"""
    click.secho("Starting review import from boost.org\n", fg="green")

    url = "https://www.boost.org/doc/formal-reviews/review-results.html"
    # Timed out because this now runs from a Celery task as well as by hand, and a
    # boost.org that accepts the connection and never answers would otherwise hold
    # a worker for as long as the process lives.
    response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    # boost.org serves the review-results page with `Content-Type: text/html`
    # and no charset, so `requests` falls back to ISO-8859-1 per the HTTP spec
    # and the actual UTF-8 body gets mojibake-decoded (e.g. "Joaquín M López
    # Muñoz" turns into "JoaquÃ­n M LÃ³pez MuÃ±oz"). Force UTF-8 so accented
    # names round-trip cleanly into the raw fields and FK lookup.
    response.encoding = "utf-8"

    # Raise rather than return on an unparseable page: this command runs from a
    # Celery task, and a quiet return would report success on an empty scrape.
    inner = _extract_inner_doc(response.text)
    if inner is None:
        raise CommandError(f"Could not find review content in {url}")

    # Locate every yearly results table in the section. The live page starts the
    # section with a navigation table, so position alone cannot distinguish the
    # result data from the surrounding page furniture.
    heading = inner.find(
        lambda t: t.name in ("h1", "h2", "h3", "h4")
        and t.get_text(strip=True) == PAST_RESULTS_HEADING
    )
    result_tables = _result_tables_under(heading) if heading else []
    if not result_tables:
        raise CommandError(
            f'Could not find review result tables under "{PAST_RESULTS_HEADING}" '
            f"in {url}"
        )

    past_reviews = [
        review
        for result_table in result_tables
        for review in _parse_table(result_table)
    ]

    click.echo(f"Found {len(past_reviews)} past reviews")

    # The page lists newest first. Create oldest-first so the newest review gets
    # the highest id; combined with the `-id` ordering on the admin and the
    # public past-reviews page, that keeps the newest reviews at the top, exactly
    # as they appear on the website.
    past_reviews.reverse()

    reviews_created = results_created = 0
    # Import everything in a transaction
    with transaction.atomic():
        doomed_ids = []
        if clean:
            # Parse before touching stored data, then make the deletion and its
            # replacement one atomic operation. The grants are settled after the
            # replacement rows exist, not before: see the end of this block.
            doomed_ids = list(Review.objects.values_list("pk", flat=True))
            delete_output = Review.objects.all().delete()
            click.secho(f"Deleted {delete_output}\n", fg="yellow")

        # Build a fingerprint -> Review map of what already exists so re-imports
        # update rows in place instead of creating near-duplicates. The
        # fingerprint is flexible (case/accents/punctuation are normalized away)
        # and spans multiple fields (submission + submitter + dates), so a row
        # whose spelling shifted slightly between imports still matches, while
        # genuinely distinct reviews - e.g. a library re-reviewed on different
        # dates - stay separate. Any pre-existing duplicates are collapsed.
        existing_by_key = {}
        removed_duplicates = 0
        for review in list(Review.objects.order_by("pk")):
            key = review_key(
                review.submission, review.submitter_raw, review.review_dates
            )
            if key in existing_by_key:
                # The survivor is the same review, so a grant naming it by
                # fingerprint follows the survivor instead of being thrown away.
                relink_source_achievements(
                    Review, {"|".join(key): existing_by_key[key].pk}
                )
                discard_source_achievements(Review, [review.pk])
                review.delete()
                removed_duplicates += 1
            else:
                existing_by_key[key] = review

        if removed_duplicates:
            click.secho(
                f"Removed {removed_duplicates} pre-existing duplicate reviews",
                fg="yellow",
            )

        for review_data, results in past_reviews:
            key = review_key(
                review_data["submission"],
                review_data["submitter_raw"],
                review_data["review_dates"],
            )
            review = existing_by_key.get(key)
            if review is None:
                review = Review.objects.create(**review_data)
                existing_by_key[key] = review
                reviews_created += 1
            else:
                for field, value in review_data.items():
                    setattr(review, field, value)
                review.save()

            for result in results:
                _, created = ReviewResult.objects.update_or_create(
                    review=review,
                    short_description=result["short_description"],
                    defaults=result,
                )
                results_created += int(created)

        if clean:
            # The same reviews are back under new ids, and a grant names its
            # evidence by fingerprint, so the pointers are rebuilt rather than
            # the grants dropped: dropping them would revoke the Reviewer badges
            # they justify and re-earn them dated today on the next sync.
            relink_source_achievements(
                Review,
                {"|".join(key): review.pk for key, review in existing_by_key.items()},
            )
            # Whatever still points into the deleted ids is evidence that did not
            # come back, so those grants really are stale.
            discard_source_achievements(Review, doomed_ids)

    click.secho("\nFinished importing reviews", fg="green")
    click.secho(
        f"Created {reviews_created} reviews and {results_created} results", fg="green"
    )

    users_linked = 0
    managers_linked = 0
    click.echo("\nAttempting to parse users\n")

    # Link users in separate transaction
    with transaction.atomic():
        for review in Review.objects.all():
            # Handle submitters
            submitter_names = _parse_raw_names(review.submitter_raw)
            for name in submitter_names:
                submitter = CommitAuthor.objects.filter(name=name).first()
                if submitter and not review.submitters.filter(pk=submitter.pk).exists():
                    review.submitters.add(submitter)
                    users_linked += 1
                    click.echo(f"Linked submitter {submitter} to {review.submission}")

            # Handle review manager
            if (
                review.review_manager_raw
                and review.review_manager_raw
                != Review._meta.get_field("review_manager_raw").default
            ):
                manager_names = _parse_raw_names(review.review_manager_raw)
                if manager_names:
                    name = manager_names[0]
                    manager = CommitAuthor.objects.filter(name=name).first()
                    if manager and review.review_manager_id != manager.pk:
                        review.review_manager = manager
                        review.save(update_fields=["review_manager"])
                        managers_linked += 1
                        click.echo(f"Linked manager {manager} to {review.submission}")

        click.secho(
            f"\nLinked {users_linked} submitters and {managers_linked} managers",
            fg="green",
        )

    click.secho("\nDone!", fg="green")


def _extract_inner_doc(page_html):
    """Return the parsed inner document embedded in the page's content iframe.

    The review-results page is an Antora/AsciiDoc doc whose real content is
    HTML-escaped inside an ``<iframe srcdoc="...">``. The content iframe is the
    one with the longest ``srcdoc`` value; unescape it and parse the result.
    Returns ``None`` if no such iframe is present.
    """
    outer = BeautifulSoup(page_html, "html.parser")
    iframes = [f for f in outer.find_all("iframe") if f.get("srcdoc")]
    if not iframes:
        return None
    iframe = max(iframes, key=lambda f: len(f["srcdoc"]))
    return BeautifulSoup(html.unescape(iframe["srcdoc"]), "html.parser")


def _result_tables_under(heading):
    """Return result tables after ``heading`` and before the next ``h2``."""
    tables = []
    for element in heading.find_all_next(("h2", "table")):
        if element.name == "h2":
            break
        header_row = element.find("tr")
        header = (
            tuple(cell.get_text(" ", strip=True) for cell in header_row.find_all("th"))
            if header_row
            else ()
        )
        if header == PAST_RESULTS_HEADER:
            tables.append(element)
    return tables


def _parse_table(table):
    """Parse the past-results table and return ``(review_data, results)`` tuples.

    Rows are both reviews and release milestones. Each ``<a>`` in the Result
    cell becomes a ``ReviewResult``; anchors wrapped in
    ``<span class="line-through">`` are superseded (``is_most_recent=False``),
    the bare anchor is the current result (``is_most_recent=True``).
    """
    rows = table.find_all("tr")[1:]  # Skip header row
    reviews = []

    for row in rows:
        cells = row.find_all("td")
        if not cells or not cells[0].get_text(strip=True):
            continue
        if len(cells) < 5:
            raise CommandError(
                f"Expected 5 columns in the past-results table, found {len(cells)}: "
                f"{[cell.get_text(strip=True) for cell in cells]}"
            )

        submission_cell = cells[0]
        review_data = {
            "submission": submission_cell.get_text(strip=True),
            "submitter_raw": cells[1].get_text(strip=True),
            "review_manager_raw": cells[2].get_text(strip=True),
            "review_dates": cells[3].get_text(strip=True),
        }

        # Only a GitHub repository, and only when the cell has one: the key is
        # left out otherwise so a re-import cannot erase a link somebody entered
        # in the admin. ``documentation_link`` is never written at all - the
        # submission cell also carries project pages and announcement posts, and
        # guessing which of those is documentation is not this command's job.
        submission_link = submission_cell.find("a", href=True)
        if submission_link and _is_github_link(submission_link["href"]):
            review_data["github_link"] = submission_link["href"]

        results_data = []
        result_cell = cells[4]
        for link in result_cell.find_all("a"):
            results_data.append(
                {
                    "short_description": link.get_text(strip=True),
                    "announcement_link": link.get("href", ""),
                    "is_most_recent": not _is_superseded(link, result_cell),
                }
            )

        # If no linked results were found, fall back to the cell's text.
        if not results_data and (description := result_cell.get_text(strip=True)):
            results_data.append(
                {
                    "short_description": description,
                    "announcement_link": "",
                    "is_most_recent": True,
                }
            )

        reviews.append((review_data, results_data))

    return reviews


def _is_github_link(link: str) -> bool:
    hostname = (urlparse(link).hostname or "").lower()
    return hostname == "github.com" or hostname.endswith(".github.com")


def _is_superseded(link, result_cell):
    """True if ``link`` is wrapped in a ``<span class="line-through">``."""
    node = link.parent
    while node is not None and node is not result_cell:
        if node.name == "span" and "line-through" in (node.get("class") or []):
            return True
        node = node.parent
    return False


def _parse_raw_names(raw_name_string: str) -> list[str]:
    """
    Parse a raw name string into a list of individual names.

    Marked as private since this is a fairly narrow, clunky solution optimized for
    the names seen in the actual boost.org table.

    Handles inputs like:
        "John Doe"
        "John Doe & Jane Smith"
        "John Doe and Jane Smith"
        "John Doe, Jane Smith"
        "John Doe, Jane Smith, Joaquin M López Muñoz"

    Returns a list like:
        ["John Doe", "Jane Smith", "Joaquin M López Muñoz"]
    """
    # Clean up the string - normalize whitespace and separators,
    # and strip known weird characters and strings
    cleaned = (
        raw_name_string.replace("\n", " & ")
        .replace("\t", " ")
        .replace(" and ", " & ")
        .replace(",", " & ")
        .replace("ª", "")  # special character observed
        .replace("OvermindDL1", "")  # replaced review manager observed
    )

    # Collapse multiple `&` separators
    while " & & " in cleaned:
        cleaned = cleaned.replace(" & & ", " & ")

    # Collapse multiple spaces
    cleaned = " ".join(cleaned.split())

    # Split on & and clean up each name
    return [name.strip() for name in cleaned.split("&") if name.strip()]
