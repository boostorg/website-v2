import structlog
from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from fastcore.xtras import obj2dict

from core.githubhelper import GithubAPIClient, GithubDataParser


from .models import Category, Issue, Library, PullRequest
from .utils import generate_fake_email, parse_date

logger = structlog.get_logger()

User = get_user_model()


now = timezone.now()
FIRST_OF_MONTH_ONE_YEAR_AGO = timezone.make_aware(
    timezone.datetime(year=now.year - 1, month=now.month, day=1)
)
FIRST_OF_CURRENT_MONTH = timezone.make_aware(
    timezone.datetime(year=now.year, month=now.month, day=1)
) - relativedelta(days=1)


class LibraryUpdater:
    """
    This class is used to sync Libraries from the list of git submodules
    and their `libraries.json` file metadata.
    """

    def __init__(self, client=None, token=None):
        if client:
            self.client = client
        else:
            self.client = GithubAPIClient()
        self.api = self.client.initialize_api(token=token)
        self.parser = GithubDataParser()
        self.logger = structlog.get_logger()

        # Modules we need to skip as they are not really Boost Libraries
        self.skip_modules = [
            "inspect",
            "boostbook",
            "bcp",
            "build",
            "quickbook",
            "litre",
            "auto_index",
            "boostdep",
            "check_build",
            "headers",
            "boost_install",
            "docca",
            "cmake",
            "more",
        ]
        # Libraries to skip that are not "modules", but appear as child-libraries
        # of other modules. Identified by the key used in the libraries.json file.
        self.skip_libraries = ["chrono/stopwatch"]

    def get_library_list(self, gitmodules=None):
        """
        Retrieve the full list of library data for Boost libraries from their Github
        repos.

        Included libraries are rrtrieved from the list of modules in .gitmodules in the
        main Boost repo. The libraries.json file is retrieved from each module and
        parsed to get the library metadata. Most libraries.json files contain info
        about individual libraries, but a few such as "system", "functional", etc.
        contain multiple libraries.
        """
        libraries = []
        for gitmodule in gitmodules:
            if gitmodule["module"] in self.skip_modules:
                continue

            libraries_json = self.client.get_libraries_json(
                repo_slug=gitmodule["module"]
            )
            github_data = self.client.get_repo(repo_slug=gitmodule["module"])
            extra_data = {
                "github_url": github_data.get("html_url", ""),
            }

            if type(libraries_json) is list:
                for library in libraries_json:
                    data = self.parser.parse_libraries_json(library)
                    if data["key"] in self.skip_libraries:
                        continue
                    libraries.append({**data, **extra_data})

            elif type(libraries_json) is dict:
                data = self.parser.parse_libraries_json(libraries_json)
                if data["key"] in self.skip_libraries:
                    continue
                libraries.append({**data, **extra_data})

        return libraries

    def update_libraries(self):
        """
        Update all libraries with the metadata from their libraries.json file.
        """
        raw_gitmodules = self.client.get_gitmodules()
        gitmodules = self.parser.parse_gitmodules(raw_gitmodules.decode("utf-8"))
        library_data = self.get_library_list(gitmodules=gitmodules)

        self.logger.info(
            "update_all_libraries_metadata", library_count=len(library_data)
        )

        for lib in library_data:
            obj = self.update_library(lib)
            if not obj:
                continue

            self.update_categories(obj, categories=lib["category"])
            # self.update_authors(obj, authors=lib["authors"])

    def update_library(self, library_data: dict) -> Library:
        """Update an individual library"""
        logger = self.logger.bind(library=library_data)
        try:
            obj, created = Library.objects.update_or_create(
                key=library_data["key"],
                defaults={
                    "name": library_data["name"],
                    "github_url": library_data["github_url"],
                    "description": library_data["description"],
                    "cpp_standard_minimum": library_data["cxxstd"],
                    "data": library_data,
                },
            )

            logger = logger.bind(obj_created=created)
            obj.save()
            logger.info("library_udpated")
            return obj

        except Exception:
            logger.exception("library_update_failed")

    def update_categories(self, obj, categories):
        """Update all of the categories for an object"""

        obj.categories.clear()
        for cat_name in categories:
            cat, _ = Category.objects.get_or_create(name=cat_name)
            obj.categories.add(cat)

    def update_authors(self, obj, authors=None):
        """
        Receives a list of strings from the libraries.json of a Boost library, and
        an object with an "authors" attribute.

        Processes that string into a User object that is added as an
        Author to the Library.
        """
        if not authors:
            return obj

        for author in authors:
            person_data = self.parser.extract_contributor_data(author)
            email = person_data["email"]
            user = User.objects.find_contributor(
                email=person_data["email"],
                first_name=person_data["first_name"],
                last_name=person_data["last_name"],
            )

            if not user:
                email = person_data.pop("email")
                if not email:
                    email = generate_fake_email(
                        f"{person_data['first_name']} {person_data['last_name']}"
                    )
                    # With a new email, we may have a user record
                    user = User.objects.find_contributor(email=email)

            # If still no user, generate a fake one
            if not user:
                user = User.objects.create_stub_user(email.lower(), **person_data)
                self.logger.info(f"User {user.email} created.")

            obj.authors.add(user)

        return obj

    def update_maintainers(self, obj, maintainers=None):
        """
        Receives a list of strings from the libraries.json of a Boost library, and
        an object with a M2M "maintainers" attribute.

        Processes the list of strings into User objects and adds them as Maintainers
        to the object.
        """
        if not maintainers:
            return

        for maintainer in maintainers:
            person_data = self.parser.extract_contributor_data(maintainer)
            user = User.objects.find_contributor(
                email=person_data["email"],
                first_name=person_data["first_name"],
                last_name=person_data["last_name"],
            )

            if not user:
                email = person_data.pop("email")
                if not email:
                    email = generate_fake_email(
                        f"{person_data['first_name']} {person_data['last_name']}"
                    )
                user = User.objects.create_stub_user(email.lower(), **person_data)
                self.logger.info(f"User {user.email} created.")

            obj.maintainers.add(user)
            self.logger.info(f"User {user.email} added as a maintainer of {obj}")

    def update_monthly_commit_counts(
        self,
        branch: str = "master",
        since=FIRST_OF_MONTH_ONE_YEAR_AGO,
        until=FIRST_OF_CURRENT_MONTH,
    ):
        """Update the monthly commit data for all libraries

        :param branch: Branch to update commit data for. Defaults to "master".
        :param since: Year to update commit data for. Defaults to a year ago
        :param until: Year to update commit data for. Defaults to present year

        Note: Overrides CommitData objects for the library; does not increment
        the count.
        """
        self.logger.info("updating_monthly_commit_data")
        for library in Library.objects.all():
            self.update_monthly_commit_counts_for_library(
                library, branch=branch, since=since, until=until
            )

    def update_monthly_commit_counts_for_library(
        self,
        obj,
        branch: str = "master",
        since=FIRST_OF_MONTH_ONE_YEAR_AGO,
        until=FIRST_OF_CURRENT_MONTH,
    ):
        """Update the commit counts for a specific library."""
        commits = self.client.get_commits(
            repo_slug=obj.github_repo, branch=branch, since=since, until=until
        )
        commit_data = self.parser.get_commits_per_month(commits)

        for month_year, commit_count in commit_data.items():
            data_obj, created = obj.commit_data.update_or_create(
                month_year=month_year,
                branch=branch,
                defaults={"commit_count": commit_count},
            )
            self.logger.info(
                "commit_data_updated",
                commit_data_pk=data_obj.pk,
                obj_created=created,
                library=obj.name,
                branch=branch,
            )

    def update_issues(self, obj):
        """Import GitHub issues for the library and update the database"""
        self.logger.info("updating_repo_issues")

        issues_data = self.client.get_repo_issues(
            self.client.owner, obj.github_repo, state="all", issues_only=True
        )
        for issue_dict in issues_data:
            # Get the date information
            closed_at = None
            created_at = None
            modified_at = None

            if issue_dict.get("closed_at"):
                closed_at = parse_date(issue_dict["closed_at"])

            if issue_dict.get("created_at"):
                created_at = parse_date(issue_dict["created_at"])

            if issue_dict.get("updated_at"):
                modified_at = parse_date(issue_dict["updated_at"])

            # Create or update the Issue object
            try:
                issue, created = Issue.objects.update_or_create(
                    library=obj,
                    github_id=issue_dict["id"],
                    defaults={
                        "title": issue_dict["title"][:255],
                        "number": issue_dict["number"],
                        "is_open": issue_dict["state"] == "open",
                        "closed": closed_at,
                        "created": created_at,
                        "modified": modified_at,
                        "data": obj2dict(issue_dict),
                    },
                )
                self.logger.info(
                    "issue_updated_successfully",
                    issue_id=issue.id,
                    created_issue=created,
                    issue_github_id=issue.github_id,
                )
            except Exception as e:
                self.logger.exception(
                    "update_issues_error_skipped_issue",
                    issue_github_id=issue_dict.get("id"),
                    exc_msg=str(e),
                )
                continue

    def update_prs(self, obj):
        """Update all PRs for a library"""
        self.logger.info("updating_repo_prs")

        prs_data = self.client.get_repo_prs(obj.github_repo, state="all")

        for pr_dict in prs_data:
            # Get the date information
            closed_at = None
            merged_at = None
            created_at = None
            modified_at = None

            if pr_dict.get("closed_at"):
                closed_at = parse_date(pr_dict["closed_at"])

            if pr_dict.get("merged_at"):
                merged_at = parse_date(pr_dict["merged_at"])

            if pr_dict.get("created_at"):
                created_at = parse_date(pr_dict["created_at"])

            if pr_dict.get("updated_at"):
                modified_at = parse_date(pr_dict["updated_at"])

            try:
                pull_request, created = PullRequest.objects.update_or_create(
                    library=obj,
                    github_id=pr_dict["id"],
                    defaults={
                        "title": pr_dict["title"][:255],
                        "number": pr_dict["number"],
                        "is_open": pr_dict["state"] == "open",
                        "closed": closed_at,
                        "merged": merged_at,
                        "created": created_at,
                        "modified": modified_at,
                        "data": obj2dict(pr_dict),
                    },
                )
                self.logger.info(
                    "pull_request_updated_successfully",
                    pr_id=pull_request.id,
                    created_pr=created,
                    pr_github_id=pull_request.github_id,
                )
            except Exception as e:
                self.logger.exception(
                    "update_prs_error_skipped_pr",
                    pr_github_id=pr_dict.get("id"),
                    exc_msg=str(e),
                )
