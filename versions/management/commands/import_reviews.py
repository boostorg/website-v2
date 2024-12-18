from bs4 import BeautifulSoup
import djclick as click
import requests

from django.contrib.auth import get_user_model
from django.db import transaction

from libraries.models import CommitAuthor
from versions.models import Review, ReviewResult

User = get_user_model()


@click.command()
@click.option(
    "--clean", is_flag=True, help="Start by deleting all previously imported reviews"
)
def command(clean):
    """Import Boost library reviews from boost.org table data"""
    if clean:
        click.secho(f"Deleted {Review.objects.all().delete()}\n", fg="yellow")

    click.secho("Starting review import from boost.org\n", fg="green")

    url = "https://www.boost.org/community/review_schedule.html"
    response = requests.get(url)

    soup = BeautifulSoup(response.text, "html.parser")

    # Parse both tables
    scheduled_review_table = soup.find("table", summary="Formal Review Schedule")
    past_review_table = soup.find("table", summary="Review Results")

    if not scheduled_review_table or not past_review_table:
        click.secho("Could not find review tables in page content", fg="red", err=True)
        return

    upcoming_reviews = _parse_table(scheduled_review_table)
    past_reviews = _parse_table(past_review_table, past_results=True)

    click.echo(
        f"Found {len(upcoming_reviews)} upcoming and {len(past_reviews)} past reviews"
    )

    reviews_created = results_created = 0
    # Import everything in a transaction
    with transaction.atomic():
        # Create or update past reviews
        for review_data, results in past_reviews:
            review, created = Review.objects.update_or_create(
                submission=review_data["submission"],
                submitter_raw=review_data["submitter_raw"],
                defaults=review_data,
            )
            reviews_created += int(created)
            for result in results:
                _, created = ReviewResult.objects.update_or_create(
                    review=review,
                    short_description=result["short_description"],
                    defaults=result,
                )
                results_created += int(created)

        # Create or update upcoming reviews
        for review_data, _ in upcoming_reviews:
            _, created = Review.objects.update_or_create(
                submission=review_data["submission"],
                submitter_raw=review_data["submitter_raw"],
                defaults=review_data,
            )
            reviews_created += int(created)

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
                if submitter:
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
                    if manager:
                        review.review_manager = manager
                        review.save()
                        managers_linked += 1
                        click.echo(f"Linked manager {manager} to {review.submission}")

        click.secho(
            f"\nLinked {users_linked} submitters and {managers_linked} managers",
            fg="green",
        )

    click.secho("\nDone!", fg="green")


def _parse_table(table, past_results=False):
    """Parse a review table and return review data"""
    rows = table.find_all("tr")[1:]  # Skip header row
    reviews = []

    for row in rows:
        cells = row.find_all("td")
        if not cells or not cells[0].text.strip():
            continue

        review_data = {
            "submission": cells[0].text.strip(),
            "submitter_raw": cells[1].text.strip(),
            "review_manager_raw": cells[2 if past_results else 3].text.strip(),
            "review_dates": cells[3 if past_results else 4].text.strip(),
            "github_link": "",
            "documentation_link": "",
        }

        # Handle links for upcoming reviews
        if not past_results:
            links = cells[2].find_all("a")
            for link in links:
                if "github" in link.text.lower():
                    review_data["github_link"] = link.get("href", "")
                elif "documentation" in link.text.lower():
                    review_data["documentation_link"] = link.get("href", "")

        # Handle results for past reviews
        results_data = []
        if past_results:
            result_cell = cells[4]

            # First handle any linked results
            for element in result_cell.contents:
                if element.name == "del":
                    link = element.find("a")
                    if link:
                        results_data.append(
                            {
                                "short_description": link.text.strip(),
                                "announcement_link": link.get("href", ""),
                                "is_most_recent": False,
                            }
                        )
                elif element.name == "a":
                    results_data.append(
                        {
                            "short_description": element.text.strip(),
                            "announcement_link": element.get("href", ""),
                            "is_most_recent": True,
                        }
                    )

            # If no results were found, use the text content of the cell
            if not results_data and (description := result_cell.text.strip()):
                results_data.append({"short_description": description})

        reviews.append((review_data, results_data))

    return reviews


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
