from datetime import date, timedelta

from celery import shared_task, chain
from django.core.mail import EmailMultiAlternatives
from django.core.management import call_command
import structlog
from django.db.models.functions import ExtractWeek, ExtractIsoYear

from config.celery import app
from django.conf import settings
from django.db.models import Q, Count, Sum, OuterRef
from core.boostrenderer import get_content_from_s3
from core.htmlhelper import get_library_documentation_urls
from libraries.github import LibraryUpdater
from libraries.models import (
    Library,
    LibraryVersion,
    CommitAuthorEmail,
    CommitAuthor,
    ReleaseReport,
)
from mailing_list.models import EmailData, PostingData
from reports.generation import (
    generate_algolia_words,
    generate_wordcloud,
    get_algolia_search_stats,
    generate_mailinglist_words,
    global_new_contributors,
)
from users.tasks import User
from versions.models import Version
from .constants import (
    LIBRARY_DOCS_EXCEPTIONS,
    LIBRARY_DOCS_MISSING,
    VERSION_DOCS_MISSING,
    DOCKER_CONTAINER_URL_WEB,
)
from .utils import (
    version_within_range,
    update_base_tag,
    generate_release_report_filename,
)

logger = structlog.getLogger(__name__)


@app.task
def update_library_version_documentation_urls_all_versions():
    """Run the task to update all documentation URLs for all versions"""
    for version in Version.objects.all().order_by("-name"):
        get_and_store_library_version_documentation_urls_for_version(version.pk)


@app.task
def get_and_store_library_version_documentation_urls_for_version(version_pk):
    """
    Store the url paths to the documentation for each library in a given version.
    The url paths are retrieved from the `libraries.htm` file in the docs stored in
    S3 for the given version.

    Retrieve the libraries from the "Libraries Listed Alphabetically" section of the
    HTML file. Loop through the unordered list of libraries and save the url path
    to the docs for that library to the database.

    Background: There are enough small exceptions to how the paths to the docs for each
    library are generated, so the easiest thing to do is to access the list of libraries
    for a particular release, scrape the url paths to their docs, and save those to the
    database.
    """
    try:
        version = Version.objects.get(pk=version_pk)
    except Version.DoesNotExist:
        logger.error(f"Version does not exist for {version_pk=}")
        raise

    if version_missing_docs(version):
        # If we know the docs for this version are missing, update related records
        LibraryVersion.objects.filter(version=version, missing_docs=False).update(
            missing_docs=True
        )
        return

    base_path = f"doc/libs/{version.boost_url_slug}/libs/"
    boost_stripped_base_path = base_path.replace("doc/libs/boost_", "doc/libs/")
    key = f"{base_path}libraries.htm"
    result = get_content_from_s3(key)

    if not result:
        raise ValueError(f"Could not get content from S3 for {key}")

    content = result["content"]
    library_tags = get_library_documentation_urls(content)
    library_versions = LibraryVersion.objects.filter(version=version)

    for library_name, url_path in library_tags:
        try:
            # In most cases, the name matches close enough to get the correct object
            library_version = library_versions.get(library__name__iexact=library_name)
            library_version.documentation_url = f"/{boost_stripped_base_path}{url_path}"
            library_version.save()
        except LibraryVersion.DoesNotExist:
            logger.info(
                f"get_library_version_documentation_urls_version_does_not_exist"
                f"{library_name=} {version.slug=}",
            )
            continue
        except LibraryVersion.MultipleObjectsReturned:
            logger.info(
                "get_library_version_documentation_urls_multiple_objects_returned",
                library_name=library_name,
                version_slug=version.slug,
            )
            continue

    # See if we can load missing docs URLS another way
    library_versions = (
        LibraryVersion.objects.filter(missing_docs=False)
        .filter(version=version)
        .filter(Q(documentation_url="") | Q(documentation_url__isnull=True))
    )
    for library_version in library_versions:
        # Check whether we know this library-version doesn't have docs
        if library_version_missing_docs(library_version):
            # Record that the docs are missing, since we know they are
            library_version.missing_docs = True
            library_version.save()
            continue

        # Check whether this library-version stores its docs in another location
        exceptions = LIBRARY_DOCS_EXCEPTIONS.get(library_version.library.slug, [])
        documentation_url = None
        for exception in exceptions:
            if version_within_range(
                library_version.version.boost_url_slug,
                min_version=exception.get("min_version"),
                max_version=exception.get("max_version"),
            ):
                exception_url_generator = exception["generator"]
                # Some libs use slugs that don't conform to what we generate via slugify
                slug = exception.get(
                    "alternate_slug",
                    library_version.library.slug.lower().replace("-", "_"),
                )
                documentation_url = exception_url_generator(
                    version.boost_url_slug,
                    slug,
                )
                break  # Stop looking once a matching version is found

        if documentation_url:
            # validate this in S3
            key = documentation_url.split("#")
            content = get_content_from_s3(key[0])

            if content:
                library_version.documentation_url = documentation_url.replace(
                    "doc/libs/boost_", "doc/libs/"
                )
                library_version.save()
            else:
                logger.info(f"No valid docs in S3 for key {documentation_url}")


def version_missing_docs(version):
    """Returns True if we know the docs for this release are missing

    In this module to avoid a circular import"""
    # Check if the version is called out in VERSION_DOCS_MISSING
    if version.name in VERSION_DOCS_MISSING:
        return True

    # Check if the version is older than our oldest version
    # stored in S3
    return version_within_range(
        version.name, max_version=settings.MAXIMUM_BOOST_DOCS_VERSION
    )


def library_version_missing_docs(library_version):
    """Returns True if we know the docs for this lib-version
    are missing

    In this module to avoid a circular import
    """
    if library_version.missing_docs:
        return True

    missing_docs = LIBRARY_DOCS_MISSING.get(library_version.library.slug, [])
    version_name = library_version.version.name
    for entry in missing_docs:
        # Check if version is within specified range
        if version_within_range(
            version=version_name,
            min_version=entry.get("min_version"),
            max_version=entry.get("max_version"),
        ):
            return True
    return False


@app.task
def update_libraries():
    """Update local libraries from GitHub Boost libraries.

    Use the LibraryUpdater, which retrieves the active boost libraries from the
    Boost GitHub repo, to update the models with the latest information on that
    library (repo) along with its issues, pull requests, and related objects
    from GitHub.
    """
    updater = LibraryUpdater()
    updater.update_libraries()
    logger.info("libraries_tasks_update_all_libraries_finished")


@app.task
def update_authors_and_maintainers():
    call_command("update_authors")
    call_command("update_maintainers")
    call_command("update_library_version_authors", "--clean")


@app.task
def update_commits(token=None, clean=False, min_version=""):
    # dictionary of library_key: int
    commits_handled: dict[str, int] = {}
    updater = LibraryUpdater(token=token)
    all_libs = Library.objects.all()
    lib_count = len(all_libs)
    for idx, library in enumerate(all_libs):
        logger.info(f"Importing commits for library {library} ({idx}/{lib_count}).")
        commits_handled[library.key] = updater.update_commits(
            library=library, clean=clean, min_version=min_version
        )
    logger.info("update_commits finished.")
    return commits_handled


@app.task
def update_commit_author_github_data(token=None, clean=False):
    updater = LibraryUpdater(token=token)
    updater.update_commit_author_github_data(overwrite=clean)
    logger.info("update_commit_author_github_data finished.")


@app.task
def update_issues(clean=False):
    command = ["update_issues"]
    if clean:
        command.append("--clean")
    call_command(*command)


@app.task
def generate_release_report(user_id: int, params: dict, base_uri: str = None):
    """Generate a release report asynchronously and save it in RenderedContent."""
    logger.info(f"Starting generate_release_report task, {settings.LOCAL_DEVELOPMENT=}")
    from libraries.forms import CreateReportForm

    form = CreateReportForm(params)
    html = form.cache_html(base_uri=base_uri)
    # override the base uri to reference the internal container for local dev
    if settings.LOCAL_DEVELOPMENT:
        html = update_base_tag(html, DOCKER_CONTAINER_URL_WEB)

    release_report = ReleaseReport(
        created_by_id=user_id,
        report_configuration_id=params.get("report_configuration"),
    )
    logger.info(f"Saving release_report {params.get('report_configuration')=}")
    release_report.save()
    logger.info(f"generate release report pdf {release_report.pk=}")
    generate_release_report_pdf.delay(
        release_report.pk, html=html, publish=params.get("publish")
    )


@app.task(bind=True, time_limit=300, soft_time_limit=240)
def generate_release_report_pdf(
    self, release_report_id: int, html: str, publish: bool = False
):
    """Generate a release report asynchronously and save it in PDF using Playwright."""
    from playwright.sync_api import sync_playwright
    from django.core.files.base import ContentFile

    release_report = ReleaseReport.objects.get(pk=release_report_id)

    logger.info(f"{release_report_id=}, task id: {self.request.id}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, executable_path="/usr/bin/chromium"
            )
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            # wait for fonts to be ready
            page.evaluate("document.fonts.ready")
            logger.info("Generating PDF")
            page.emulate_media(media="print")
            pdf_bytes = page.pdf(
                format="Letter",
                print_background=True,
                prefer_css_page_size=True,
                margin={
                    "top": "0.5in",
                    "right": "0.5in",
                    "bottom": "0.5in",
                    "left": "0.5in",
                },
            )
            browser.close()

        logger.info(f"PDF generated successfully, size: {len(pdf_bytes)} bytes")
        # to start, we have the draft file, so it can be moved later into the
        # final location by the ReleaseReport.save() process
        filename = generate_release_report_filename(
            release_report.report_configuration.get_slug(), published_format=False
        )
        release_report.file.save(filename, ContentFile(pdf_bytes), save=True)
        if publish:
            release_report.published = True
            release_report.save(allow_published_overwrite=True)
    except ValueError as e:
        logger.error(f"Failed to publish release: {e}")
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}", exc_info=True)
        raise


@app.task
def generate_library_report(params):
    """Generate a library report asynchronously and save it in RenderedContent."""
    from libraries.forms import CreateReportFullForm

    form = CreateReportFullForm(params)
    form.cache_html()


@app.task
def update_library_version_dependencies(token=None):
    command = ["update_library_version_dependencies"]
    if token:
        command.extend(["--token", token])
    call_command(*command)


@app.task
def release_tasks(base_uri, user_id=None, generate_report=False):
    """Call the release_tasks management command.

    @param base_uri should be in the format https://domain.tld
    If a user_id is given, that user will receive an email at the beginning
    and at the end of the task.

    """
    command = ["release_tasks", "--base_uri", base_uri]
    if user_id:
        command.extend(["--user_id", user_id])
    if generate_report:
        command.append("--generate_report")
    call_command(*command)


@app.task
def import_new_versions_tasks(user_id=None):
    """Call the import_new_versions management command.

    If a user_id is given, that user will receive an email at the beginning
    and at the end of the task.
    """
    command = ["import_new_versions"]
    if user_id:
        command.extend(["--user_id", user_id])
    call_command(*command)


@app.task
def synchronize_commit_author_user_data():
    logger.info("Starting synchronize_commit_author_user_data")
    chain(
        merge_commit_authors_by_github_url.si(),
        update_users_githubs.si(),
        update_commit_authors_users.si(),
    )()
    logger.info("synchronize_commit_author_user_data finished.")


@shared_task
def merge_commit_authors_by_github_url():
    # select all commit authors with duplicated github_profile_url, order the ones with a user id at the top, and if there's more than one with a userid, order by last_login
    logger.info("merging commit authors by github url")
    duplicated_author_urls = (
        CommitAuthor.objects.values("github_profile_url")
        .annotate(count=Count("id"))
        .filter(github_profile_url__isnull=False, count__gt=1)
    )
    logger.info(f"Found {duplicated_author_urls.count()} {duplicated_author_urls=}")
    for d in duplicated_author_urls:
        # this prioritizes a record which has a user associated, if there is one, and
        #  then the one with the most recent login if there are any. This is still
        #  more prioritization than when we merge manually
        duplicate_authors = CommitAuthor.objects.filter(
            github_profile_url=d["github_profile_url"]
        ).order_by("user_id", "-user__last_login")
        logger.debug(f"{duplicate_authors=}")
        primary = duplicate_authors.first()
        for da in duplicate_authors[1:]:
            logger.debug(f"{primary.id} {primary=} will have {da=} merged into it")
            primary.merge_author(da)
            logger.info(f"{primary.id} {primary=} has had {da.id=} merged into it")
    logger.info("merged commit authors by github url")


@shared_task
def update_users_githubs():
    logger.info("Linking contributors to users")
    for user in User.objects.filter(github_username=""):
        logger.info(f"Linking attempt: {user.email}")
        update_user_github_username(user.pk)


@shared_task
def update_user_github_username(user_id: int):
    logger.debug(f"Updating user github_username for {user_id=}")
    user = User.objects.get(pk=user_id)
    try:
        email = CommitAuthorEmail.objects.prefetch_related("author").get(
            email=user.email
        )
    except CommitAuthorEmail.DoesNotExist:
        logger.info(f"No commit author email found for {user.pk=} {user.email=}")
        return
    commit_author = email.author
    logger.debug(f"Found {user.pk=} for {commit_author=}")
    if not commit_author.github_profile_url:
        logger.info(f"No github username found on {commit_author.pk=}")
        return
    github_username = commit_author.github_profile_url.rstrip("/").split("/")[-1]
    logger.debug(f"Updating {user.pk=} from {email.author.pk=}, {github_username=}")
    user.github_username = github_username
    user.save()
    logger.info(f"Linked {user.pk=} to {commit_author.pk=} by github_username")


@shared_task
def update_commit_authors_users():
    logger.info("Linking commit authors to users")
    for commit_author in CommitAuthor.objects.filter(user__isnull=True):
        logger.info(f"Linking attempt: {commit_author=}")
        update_commit_author_user(commit_author.pk)
    logger.info("Finished linking commit authors to users.")


@shared_task
def update_commit_author_user(author_id: int):
    logger.info(f"{author_id=}")
    commit_author_emails = CommitAuthorEmail.objects.prefetch_related("author").filter(
        author_id=author_id
    )

    if not commit_author_emails:
        logger.info(f"No emails found for {author_id=}")
        return

    for email in commit_author_emails:
        user = User.objects.filter(email=email.email).first()
        if not user:
            logger.info(f"No user found for {email.pk=} {email.email=}")
            continue
        email.author.user = user
        email.author.save()
        logger.info(f"Linked {user=} {user.pk=} to {email=} {email.author.pk=}")


@shared_task
def send_commit_author_email_verify_mail(commit_author_email, url):
    logger.info(f"Sending verification email to {commit_author_email} with {url=}")

    text_content = (
        "Please verify your email address by clicking the following link: \n"
        f"\n\n {url}\n\n If you did not request a commit author verification "
        "you can safely ignore this email.\n"
    )
    html_content = (
        "<p>Please verify your email address at the following link:</p>"
        f"<p><a href='{url}'>Verify Email</a></p>"
        "<p>If you did not request a commit author verification you can safely ignore "
        "this email.</p>"
    )
    msg = EmailMultiAlternatives(
        subject="Please verify your email address",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[commit_author_email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    logger.info(f"Verification email to {commit_author_email} sent")


@shared_task
def count_mailinglist_contributors(prior_version_id: int, version_id: int):
    version = Version.objects.get(id=version_id)
    prior_version = Version.objects.get(id=prior_version_id)

    version_lt = list(
        Version.objects.minor_versions()
        .filter(version_array__lte=prior_version.cleaned_version_parts_int)
        .values_list("id", flat=True)
    )
    version_lte = version_lt + [version.id]
    current = (
        EmailData.objects.filter(version__in=version_lte).distinct("author_id").count()
    )
    prior = (
        EmailData.objects.filter(version__in=version_lt).distinct("author_id").count()
    )
    release = EmailData.objects.filter(version=version).count()
    return release, current - prior


@shared_task
def generate_mailinglist_cloud(prior_version_id: int, version_id: int):
    prior_version = Version.objects.get(id=prior_version_id)
    version = Version.objects.get(id=version_id)

    mailinglist_words = generate_mailinglist_words(prior_version, version)
    mailinglist_wordcloud_base64, mailinglist_wordcloud_top_words = generate_wordcloud(
        mailinglist_words, width=1400, height=700
    )
    return (
        mailinglist_words,
        mailinglist_wordcloud_base64,
        mailinglist_wordcloud_top_words,
    )


@shared_task
def generate_search_cloud(search_version_id: int):
    """
    Algolia search word cloud generation
    """
    search_version = Version.objects.get(id=search_version_id)
    from algoliasearch.analytics.client import AnalyticsClientSync

    client = AnalyticsClientSync(
        settings.ALGOLIA.get("app_id"),
        settings.ALGOLIA.get("analytics_api_key"),
        settings.ALGOLIA.get("region"),
    )
    # if the report is based on a live version, look for stats for that
    # version, otherwise use the stats for the prior (live) version
    search_list_words = generate_algolia_words(client, search_version)
    search_wordcloud_base64, search_wordcloud_top_words = generate_wordcloud(
        search_list_words, width=800, height=250
    )
    search_stats = get_algolia_search_stats(client, search_version)

    return search_wordcloud_base64, search_wordcloud_top_words, search_stats


@shared_task
def get_mailing_list_stats(prior_version_id: int, version_id: int):
    version = Version.objects.get(id=version_id)
    prior_version = Version.objects.get(id=prior_version_id)

    start_date: date = prior_version.release_date
    end_date: date = version.release_date or date.today()
    data = (
        PostingData.objects.filter(post_time__gt=start_date, post_time__lte=end_date)
        .annotate(week=ExtractWeek("post_time"), iso_year=ExtractIsoYear("post_time"))
        .values("iso_year", "week")
        .annotate(count=Count("id"))
        .order_by("iso_year", "week")
    )

    chart_data = []

    for row in data:
        week_number = row["week"]
        year_number = str(row["iso_year"])[2:]  # e.g. 25
        x = f"{week_number} ({year_number})"  # e.g., "51 (24)", "1 (25)"
        y = row["count"]
        chart_data.append({"x": x, "y": y})

    total_mailinglist_count = EmailData.objects.filter(version=version).aggregate(
        total=Sum("count")
    )["total"]
    return chart_data, total_mailinglist_count


@shared_task
def get_new_subscribers_stats(start_date: date, end_date: date):
    """Get new subscribers statistics for HyperKitty mailing list using raw SQL."""
    import psycopg2
    from django.conf import settings

    conn = psycopg2.connect(settings.HYPERKITTY_DATABASE_URL)

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    EXTRACT(ISOYEAR FROM date_joined) as iso_year,
                    EXTRACT(WEEK FROM date_joined) as iso_week,
                    COUNT(*) as count
                FROM auth_user
                WHERE date_joined::date >= %s
                    AND date_joined::date <= %s
                GROUP BY iso_year, iso_week
                ORDER BY iso_year, iso_week
            """,
                [start_date, end_date],
            )

            data = cursor.fetchall()

        # Convert data into a dict for easy lookup
        counts_by_week = {(int(row[0]), int(row[1])): row[2] for row in data}

        # Iterate through every ISO week in the date range
        current = start_date
        seen = set()
        chart_data = []
        while current <= end_date:
            iso_year, iso_week, _ = current.isocalendar()
            key = (iso_year, iso_week)
            if key not in seen:  # skip duplicate weeks in the same loop
                seen.add(key)
                year_suffix = str(iso_year)[2:]
                label = f"{iso_week} ({year_suffix})"
                count = counts_by_week.get(key, 0)
                chart_data.append({"x": label, "y": count})
            current += timedelta(days=7)  # hop by weeks

        return chart_data
    finally:
        conn.close()


@shared_task
def count_commit_contributors_totals(version_id: int, prior_version_id: int):
    """Get a count of contributors for this release, and a count of
    new contributors.

    """
    from libraries.forms import CreateReportFullForm

    prior_version = Version.objects.get(id=prior_version_id)
    version = Version.objects.get(id=version_id)

    version_lt = list(
        Version.objects.minor_versions()
        .filter(version_array__lte=prior_version.cleaned_version_parts_int)
        .values_list("id", flat=True)
    )
    version_lte = version_lt + [version.id]
    lt_subquery = LibraryVersion.objects.filter(
        version__in=version_lt,
        library=OuterRef("id"),
    ).values("id")
    lte_subquery = LibraryVersion.objects.filter(
        version__in=version_lte,
        library=OuterRef("id"),
    ).values("id")
    qs = CreateReportFullForm.library_queryset.aggregate(
        this_release_count=Count(
            "library_version__commit__author",
            filter=Q(library_version__version=version),
            distinct=True,
        ),
        authors_before_release_count=Count(
            "library_version__commit__author",
            filter=Q(library_version__in=lt_subquery),
            distinct=True,
        ),
        authors_through_release_count=Count(
            "library_version__commit__author",
            filter=Q(library_version__in=lte_subquery),
            distinct=True,
        ),
    )
    new_count = qs["authors_through_release_count"] - qs["authors_before_release_count"]
    this_release_count = qs["this_release_count"]
    return this_release_count, new_count


@shared_task
def get_new_contributors_count(version_id: int):
    """Get a count of contributors for this release"""
    version = Version.objects.get(id=version_id)
    return len(global_new_contributors(version))
