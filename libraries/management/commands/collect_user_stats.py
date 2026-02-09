import djclick as click
from openpyxl import Workbook

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models import Q

from libraries.models import CommitAuthor


@click.command()
def command():
    User = get_user_model()
    user_qs = (
        User.objects.all()
        .annotate(
            library_versions_authored=Count("author_libraryversions", distinct=True),
            libraries_authored=Count("authors", distinct=True),
        )
        .order_by("-email")
        .exclude(Q(library_versions_authored=0) & Q(libraries_authored=0))
    )
    commit_author_qs = (
        CommitAuthor.objects.all()
        .annotate(
            commits_authored=Count("commit", distinct=True),
            reviews_submitted=Count("submitted_reviews", distinct=True),
            mailing_list_count=Count("emaildata", distinct=True),
        )
        .exclude(
            Q(commits_authored=0) & Q(reviews_submitted=0) & Q(mailing_list_count=0)
        )
    )
    wb = Workbook()
    ws = wb.active
    ws.title = "Library Authors and Versions"
    ws.append(
        [
            "Email",
            "Libraries Authored",
            "Library Versions Authored",
        ]
    )
    for user in user_qs:
        ws.append(
            [
                user.email,
                user.libraries_authored,
                user.library_versions_authored,
            ]
        )
    ws.freeze_panes = "A2"
    ws.print_title_rows = "1:1"
    wb.create_sheet("Commit Author Data")
    ws = wb["Commit Author Data"]
    ws.append(
        [
            "Email",
            "Commits Authored",
            "Reviews Submitted",
            "Mailing List Contributions",
        ]
    )
    for user in commit_author_qs:
        ws.append(
            [
                user.name,
                user.commits_authored,
                user.reviews_submitted,
                user.mailing_list_count,
            ]
        )
    ws.freeze_panes = "A2"
    ws.print_title_rows = "1:1"

    wb.save("badge_info.xlsx")
