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
        # Create or update upcoming reviews
        for review_data, _ in upcoming_reviews:
            Review.objects.update_or_create(
                submission=review_data["submission"],
                submitter=review_data["submitter"],
                defaults=review_data,
            )

        # Create or update past reviews
        for review_data, results in past_reviews:
            review = Review.objects.create(**review_data)
            for result in results:
                ReviewResult.objects.create(review=review, **result)

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
            "submitter": cells[1].text.strip(),
            "review_manager": cells[3].text.strip()
            if past_results
            else cells[3].text.strip(),
            "review_dates": cells[4].text.strip(),
        }

        # Handle links for upcoming reviews
        if not past_results:
            links = cells[2].find_all("a")
            if links:
                review_data["github_link"] = links[0].get("href", "")
                if len(links) > 1:
                    review_data["documentation_link"] = links[1].get("href", "")

        # Handle results for past reviews
        results_data = []
        if past_results:
            for element in cells[4].contents:
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

        reviews.append((review_data, results_data))

    return reviews
