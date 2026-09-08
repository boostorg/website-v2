import datetime
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from model_bakery import baker
from libraries.mixins import ContributorMixin, VersionAlertMixin
from libraries.models import CommitAuthor
from libraries.utils import patch_commit_authors
from libraries.views import LibraryListBase


class MockView(LibraryListBase, VersionAlertMixin):
    pass


@pytest.mark.skip("TODO -- Test fails because we introduced beta releases")
@pytest.mark.django_db
def test_version_alert_mixin(version):
    latest_version = version
    old_version = baker.make("versions.Version", release_date=datetime.date(2000, 1, 1))

    # instantiate the mock view
    view = MockView()

    # create a mock request with no GET parameters
    request = RequestFactory().get("/")
    view.request = request

    # call get_context_data and check the context
    view.object_list = view.get_queryset()
    context = view.get_context_data()
    assert context["version"] == latest_version
    assert context["latest_version"] == latest_version
    assert not context["version_alert"]

    # create a mock request with a GET parameter for an old version
    request = RequestFactory().get(f"/?version={old_version.slug}")
    view.request = request

    # call get_context_data and check the context
    view.object_list = view.get_queryset()
    context = view.get_context_data()
    assert context["version"] == old_version
    assert context["latest_version"] == latest_version
    assert context["version_alert"]


def _alert_message(selected, current, url="/releases/latest/"):
    return VersionAlertMixin().get_version_alert_message(
        {
            "selected_version": selected,
            "current_version": current,
            "version_alert_url": url,
        }
    )


def test_version_alert_message_none_when_inputs_missing():
    from versions.models import Version

    assert VersionAlertMixin().get_version_alert_message({}) is None
    assert _alert_message(Version(name="boost-1.90.0"), None) is None


def test_version_alert_message_sticky_latest():
    from versions.models import Version

    current = Version(name="boost-1.90.0", full_release=True)
    msg = _alert_message(current, current)
    assert "You're viewing version 1.90.0." in msg
    assert "you'll remain on this version" in msg
    assert 'switch to the <a href="/releases/latest/">latest release</a>' in msg
    assert "not the new" not in msg


def test_version_alert_message_beta():
    from versions.models import Version

    current = Version(name="boost-1.90.0", full_release=True)
    selected = Version(name="boost-1.91.0-beta", beta=True, full_release=False)
    msg = _alert_message(selected, current)
    assert "beta version of Boost" in msg
    assert "current version" in msg


def test_version_alert_message_older_release():
    from versions.models import Version

    current = Version(name="boost-1.90.0", full_release=True)
    selected = Version(
        name="boost-1.70.0",
        full_release=True,
        release_date=datetime.date(2018, 1, 1),
    )
    msg = _alert_message(selected, current)
    assert "older version of Boost" in msg
    assert "2018" in msg


def test_version_alert_message_dev_branch():
    from versions.models import Version

    current = Version(name="boost-1.90.0", full_release=True)
    selected = Version(name="develop", beta=False, full_release=False)
    msg = _alert_message(selected, current)
    assert "under active development" in msg
    assert "develop" in msg


class _ContextBase:
    def get_context_data(self, **kwargs):
        return dict(self.base_context, **kwargs)


class _V3AlertView(VersionAlertMixin, _ContextBase):
    """Minimal v3-active view exercising VersionAlertMixin.get_context_data."""

    _v3_active = True

    def __init__(self, version_slug, selected, current):
        self.request = RequestFactory().get("/")
        self.request.resolver_match = SimpleNamespace(url_name="libraries-list")
        self.kwargs = {"version_slug": version_slug, "library_view_str": "grid"}
        self.base_context = {"selected_version": selected, "current_version": current}


def test_version_alert_hidden_on_latest_slug():
    from versions.models import Version

    current = Version(name="boost-1.92.0", full_release=True)
    context = _V3AlertView("latest", current, current).get_context_data()
    assert context["version_alert"] is False
    assert "version_alert_message" not in context


def test_version_alert_hidden_when_numbered_version_is_current():
    from versions.models import Version

    current = Version(name="boost-1.92.0", full_release=True)
    context = _V3AlertView("boost-1-92-0", current, current).get_context_data()
    assert context["version_alert"] is False
    assert "version_alert_message" not in context


def test_version_alert_visible_for_older_version():
    from versions.models import Version

    current = Version(name="boost-1.92.0", full_release=True)
    selected = Version(
        name="boost-1.85.0",
        full_release=True,
        release_date=datetime.date(2024, 6, 1),
    )
    context = _V3AlertView("boost-1-85-0", selected, current).get_context_data()
    assert context["version_alert"] is True
    assert "older version of Boost" in context["version_alert_message"]
    assert context["version_alert_url"] == "/libraries/latest/grid/"


# ── build_all_contributors ──────────────────────────────────────────────────


def _make_linked_author(name, email):
    """User linked to a CommitAuthor via a matching CommitAuthorEmail."""
    user = baker.make(get_user_model(), display_name=name, email=email)
    author = baker.make(
        CommitAuthor,
        name=name,
        is_bot=False,
        avatar_url="https://example.com/a.png",
        github_profile_url="https://github.com/x",
    )
    baker.make("libraries.CommitAuthorEmail", author=author, email=email)
    return user, author


@pytest.mark.django_db
def test_build_all_contributors_linked_author_single_entry(library_version):
    """A linked author is labeled Author and not double-listed as a Contributor."""
    user, author = _make_linked_author("Ada Lovelace", "ada@example.com")
    baker.make("libraries.Commit", author=author, library_version=library_version)
    library_version.authors.add(user)

    authors = [user]
    patch_commit_authors(authors)
    result = ContributorMixin().build_all_contributors(library_version, authors, [])

    ada = [c for c in result if c["name"] == "Ada Lovelace"]
    assert len(ada) == 1
    assert ada[0]["role"] == "Author"


@pytest.mark.django_db
def test_build_all_contributors_unlinked_author_not_merged_by_name(library_version):
    """An unlinked author is NOT merged with a same-named CommitAuthor."""
    user = baker.make(get_user_model(), display_name="Jane Doe", email="jane@x.com")
    author = baker.make(CommitAuthor, name="Jane Doe", is_bot=False)
    baker.make("libraries.Commit", author=author, library_version=library_version)
    library_version.authors.add(user)

    authors = [user]
    patch_commit_authors(authors)  # no matching CommitAuthorEmail -> stub, no pk
    result = ContributorMixin().build_all_contributors(library_version, authors, [])

    janes = [c for c in result if c["name"] == "Jane Doe"]
    assert {c["role"] for c in janes} == {"Author", "Contributor"}


@pytest.mark.django_db
def test_build_all_contributors_bounded_by_selected_version(library, version):
    """Contributors up to the selected version are included; newer ones excluded."""
    older = baker.make("versions.Version", name="boost-1.70.0", fully_imported=True)
    newer = baker.make("versions.Version", name="boost-1.80.0", fully_imported=True)
    older_lv = baker.make("libraries.LibraryVersion", library=library, version=older)
    current_lv = baker.make(
        "libraries.LibraryVersion", library=library, version=version
    )
    newer_lv = baker.make("libraries.LibraryVersion", library=library, version=newer)

    past = baker.make(CommitAuthor, name="Past Dev", is_bot=False)
    current = baker.make(CommitAuthor, name="Current Dev", is_bot=False)
    future = baker.make(CommitAuthor, name="Future Dev", is_bot=False)
    baker.make("libraries.Commit", author=past, library_version=older_lv)
    baker.make("libraries.Commit", author=current, library_version=current_lv)
    baker.make("libraries.Commit", author=future, library_version=newer_lv)

    names = {
        c["name"] for c in ContributorMixin().build_all_contributors(current_lv, [], [])
    }
    assert "Past Dev" in names
    assert "Current Dev" in names
    assert "Future Dev" not in names
