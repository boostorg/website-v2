from bs4 import BeautifulSoup
import djclick as click
import requests
from django.db import transaction

from versions.models import Review, ReviewResult


@click.command()
@click.option(
    "--dry-run", is_flag=True, help="Parse the data but don't save to database"
)
def command(dry_run):
    """Import Boost library reviews from boost.org table data"""

    url = "https://www.boost.org/community/review_schedule.html"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Parse both tables
    scheduled_review_table = soup.find("table", summary="Formal Review Schedule")
    past_review_table = soup.find("table", summary="Review Results")

    upcoming_reviews = parse_table(scheduled_review_table)
    past_reviews = parse_table(past_review_table, past_results=True)

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

    click.secho("Done!", fg="green")


def parse_table(table, past_results=False):
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
