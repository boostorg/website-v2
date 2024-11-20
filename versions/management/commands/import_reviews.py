from bs4 import BeautifulSoup
import djclick as click
import requests

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from libraries.utils import generate_fake_email
from versions.models import Review, ReviewResult

User = get_user_model()


@click.command()
@click.option(
    "--dry-run", is_flag=True, help="Parse the data but don't save to database"
)
@click.option(
    "--dry-run-users", is_flag=True, help="Save reviews, but don't link users"
)
def command(dry_run, dry_run_users):
    """Import Boost library reviews from boost.org table data"""

    url = "https://www.boost.org/community/review_schedule.html"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Parse both tables
    scheduled_review_table = soup.find("table", summary="Formal Review Schedule")
    past_review_table = soup.find("table", summary="Review Results")

    upcoming_reviews = _parse_table(scheduled_review_table)
    past_reviews = _parse_table(past_review_table, past_results=True)

    click.secho(
        f"Found {len(upcoming_reviews)} upcoming and {len(past_reviews)} past reviews"
    )

    if dry_run:
        click.secho("Dry run - no changes made")
        return

    # Import everything in a transaction
    with transaction.atomic():
        # Create or update past reviews
        for review_data, results in past_reviews:
            review = Review.objects.create(**review_data)
            for result in results:
                ReviewResult.objects.create(review=review, **result)

        # Create or update upcoming reviews
        for review_data, _ in upcoming_reviews:
            Review.objects.update_or_create(
                submission=review_data["submission"],
                submitter_raw=review_data["submitter_raw"],
                defaults=review_data,
            )

    click.secho("\nFinished importing reviews\n", fg="green")
    click.secho("Attempting to parse users\n")

    # Link users in separate transaction
    with transaction.atomic():
        for review in Review.objects.all():
            # Handle submitters
            submitter_names = _parse_users_from_raw_names(review.submitter_raw)
            for first_name, last_name in submitter_names:
                if dry_run_users:
                    click.echo(
                        "Would link submitter: "
                        f"{first_name} {last_name} to {review.submission}"
                    )
                else:
                    user = _get_user_from_name(first_name, last_name)
                    if user:
                        review.submitters.add(user)

            # Handle review manager
            if (
                review.review_manager_raw
                and review.review_manager_raw
                != Review._meta.get_field("review_manager_raw").default
            ):
                manager_names = _parse_users_from_raw_names(review.review_manager_raw)
                if manager_names:
                    # Take first manager if multiple are returned
                    first_name, last_name = manager_names[0]
                    if dry_run_users:
                        click.echo(
                            "Would set manager: "
                            f"{first_name} {last_name} for {review.submission}"
                        )
                    else:
                        user = _get_user_from_name(first_name, last_name)
                        if user:
                            review.review_manager = user
                            review.save()

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


def _parse_users_from_raw_names(raw_name_string: str) -> list[tuple[str, str]]:
    """
    Parse a raw name string into a list of (first_name, last_name) tuples.

    Marked as private since this is a fairly narrow, clunky solution optimized for
    the names seen in the actual boost.org table.

    Handles inputs like:
        "John Doe"
        "John Doe & Jane Smith"
        "John Doe and Jane Smith"
        "John Doe, Jane Smith"
        "John Doe, Jane Smith, Joaquin M López Muñoz"

    Returns a list like:
        [("John", "Doe"), ("Jane", "Smith"), ("Joaquin M López", "Muñoz")]
    """
    # Clean up the string - normalize whitespace and separators
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
    names = [name.strip() for name in cleaned.split("&")]
    parsed_names = []

    for name in names:
        if not name:
            continue

        # Try to split into first and last name
        parts = name.split()
        if len(parts) == 1:
            # Just one name, treat as first name
            parsed_names.append((parts[0], ""))
        else:
            # Assume last word is last name, rest is first name
            parsed_names.append((" ".join(parts[:-1]), parts[-1]))

    return parsed_names


def _get_user_from_name(first_name, last_name):
    matching_users = User.objects.filter(
        Q(first_name__iexact=first_name, last_name__iexact=last_name)
        | Q(
            first_name__unaccent__iexact=first_name,
            last_name__unaccent__iexact=last_name,
        )
        | Q(display_name__unaccent__iexact=f"{first_name} {last_name}")
        | Q(display_name__iexact=f"{first_name} {last_name}")
    )
    if count := matching_users.count() == 1:
        return matching_users.first()
    elif count:
        click.secho(
            f"Found multiple users with the same name: {first_name} {last_name}",
            fg="red",
        )
        return None

    # No existing user by this name; create a fake "stub" user
    fake_email = generate_fake_email(f"{first_name} {last_name}")
    if user := User.objects.filter(email=fake_email).first():
        return user
    return User.objects.create_stub_user(
        fake_email.lower(), first_name=first_name, last_name=last_name
    )
