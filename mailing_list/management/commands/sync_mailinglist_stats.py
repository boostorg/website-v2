from datetime import date
from itertools import pairwise
import djclick as click
import psycopg2
from psycopg2._psycopg import connection as Connection

from django.db.models.functions import Lower
from django.conf import settings
from django.db import transaction

from libraries.models import CommitAuthor, CommitAuthorEmail
from mailing_list.models import EmailData
from versions.models import Version


@click.command()
@click.option(
    "--clean",
    is_flag=True,
    help="Delete all EmailData objects before importing.",
)
def command(clean):
    if not settings.HYPERKITTY_DATABASE_NAME:
        click.echo("HYPERKITTY_DATABASE_NAME setting is empty. Not syncing.")
        return
    conn = psycopg2.connect(settings.HYPERKITTY_DATABASE_URL)
    with transaction.atomic():
        if clean:
            click.echo("Deleting all EmailData objects.")
            EmailData.objects.all().delete()
        click.echo("Creating CommitAuthors for emails.")
        create_commitauthors(conn)
        click.echo("Creating EmailData aggregated stats.")
        create_emaildata(conn)


def create_emaildata(conn: Connection):
    def bulk_create(rows, version):
        author_emails = {
            x.lower_email: x
            for x in CommitAuthorEmail.objects.annotate(lower_email=Lower("email"))
            .filter(lower_email__in=[x["email"] for x in rows])
            .select_related("author")
        }
        # group EmailData by CommitAuthor
        authors = {}
        for row in rows:
            author = author_emails[row["email"]].author
            if author not in authors:
                authors[author] = EmailData(version=version, author=author, count=0)
            authors[author].count += row["count"]
        EmailData.objects.bulk_create(
            authors.values(),
            update_conflicts=True,
            unique_fields=["author", "version"],
            update_fields=["count"],
        )

    versions = Version.objects.minor_versions().order_by("version_array")
    columns = ["email", "name", "count"]
    versions = list(versions) + [Version.objects.with_partials().get(name="master")]
    for a, b in pairwise(versions):
        start = a.release_date
        end = b.release_date or date.today()
        if not (start and end):
            msg = (
                "All x.x.0 versions must have a release date."
                f" {a=} {b=} {a.release_date=} {b.release_date=}"
            )
            raise ValueError(msg)
        with conn.cursor(name=f"emaildata_sync_{b.name}") as cursor:
            cursor.execute(
                """
                    SELECT
                        LOWER(sender_id) AS email
                        , (ARRAY_AGG(distinct(sender_name)))[1] as name
                        , count(*) AS count
                    FROM hyperkitty_email
                    WHERE date >= %(start)s AND date < %(end)s
                    GROUP BY LOWER(sender_id);
                """,
                {"start": start, "end": end},
            )
            rows = [{x: data[i] for i, x in enumerate(columns)} for data in cursor]
            bulk_create(rows, b)


def create_commitauthors(conn: Connection):
    """Create CommitAuthor and CommitAuthorEmail objects for
    all emails in hyperkitty.
    """

    def bulk_create(rows):
        emails = {x["email"]: x for x in rows}
        commitauthoremails = {
            x.lower_email: x.author_id
            for x in CommitAuthorEmail.objects.annotate(
                lower_email=Lower("email")
            ).filter(lower_email__in=emails)
        }
        authors_to_create = []
        author_emails_to_create = []
        for email_lower, row in emails.items():
            if email_lower not in commitauthoremails:
                new_author = CommitAuthor(name=row["name"])
                authors_to_create.append(new_author)
                author_emails_to_create.append(
                    CommitAuthorEmail(email=row["email"], author=new_author)
                )
        CommitAuthor.objects.bulk_create(authors_to_create)
        CommitAuthorEmail.objects.bulk_create(author_emails_to_create)

    columns = ["email", "name"]
    # Uses a named cursor to use a serverside postgres cursor
    with conn.cursor(name="commitauthor_sync") as cursor:
        cursor.execute(
            """
                SELECT
                    LOWER(sender_id) AS email
                    , (ARRAY_AGG(distinct(sender_name)))[1] as name
                FROM hyperkitty_email
                GROUP BY LOWER(sender_id);
            """
        )
        rows = []
        for i, data in enumerate(cursor):
            row = {x: data[j] for j, x in enumerate(columns)}
            rows.append(row)
            if i % 2000 == 0 and i != 0:
                bulk_create(rows)
                rows = []
        if rows:
            bulk_create(rows)
