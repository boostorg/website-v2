"""The targeted, per-release library data synchronization.

Three things are asserted here, because a repair that reaches further than the
release it was pointed at is worse than no repair at all: that
``update_library_version_authors --release`` touches one release and leaves the
retroactive backfill alone, that the task runs the import before the authors it
feeds, and that the changelist button cannot be submitted without a release.
"""

from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.urls import reverse
from model_bakery import baker

from libraries.tasks import synchronize_release_library_data
from versions.exceptions import PostImportStepFailed

pytestmark = pytest.mark.django_db

BUTTON_URL = "admin:release_tools_releaselibrarydata_synchronize_release_library_data"
CHANGELIST_URL = "admin:release_tools_releaselibrarydata_changelist"
TASK_PATH = "release_tools.admin.synchronize_release_library_data.delay"


@pytest.fixture(autouse=True)
def _clear_task_button_locks():
    """The changelist buttons lock through the cache; isolate tests."""
    cache.clear()


def make_library_version(library, version_name, authors=None, slug=None):
    """A LibraryVersion at ``version_name`` carrying ``authors`` in its data."""
    version = baker.make(
        "versions.Version",
        name=version_name,
        slug=slug or version_name.replace("boost-", "").replace(".", "-"),
        fully_imported=True,
        active=True,
    )
    return baker.make(
        "libraries.LibraryVersion",
        library=library,
        version=version,
        data={"authors": authors} if authors is not None else {},
    )


def test_release_scope_leaves_the_other_releases_alone(library):
    """The named release gains its authors; its neighbour gains nothing.

    The neighbour is the assertion that matters: without the scope the
    retroactive backfill would copy 1.92.0's authors onto 1.90.0.
    """
    older = make_library_version(library, "boost-1.90.0")
    newer = make_library_version(
        library, "boost-1.92.0", ["Jane Smith <jane -at- x.com>"]
    )

    call_command("update_library_version_authors", "--release", "1.92.0")

    assert newer.authors.count() == 1
    assert newer.authors.filter(email="jane@x.com").exists()
    assert older.authors.count() == 0


def test_release_scope_accepts_the_stored_version_name(library):
    """The admin passes ``boost-1.92.0``; an operator types ``1.92.0``."""
    newer = make_library_version(
        library, "boost-1.92.0", ["Jane Smith <jane -at- x.com>"]
    )

    call_command("update_library_version_authors", "--release", "boost-1.92.0")

    assert newer.authors.filter(email="jane@x.com").exists()


def test_release_scope_does_not_widen_into_neighbouring_versions(library):
    """``1.9`` is not a release, and must not be read as every 1.9x release."""
    newer = make_library_version(
        library, "boost-1.92.0", ["Jane Smith <jane -at- x.com>"]
    )

    call_command("update_library_version_authors", "--release", "1.9")

    assert newer.authors.count() == 0


def test_the_unscoped_sweep_still_backfills_earlier_releases(library):
    """No release named, so the pre-existing sweep behaviour is unchanged."""
    older = make_library_version(library, "boost-1.90.0")
    make_library_version(library, "boost-1.92.0", ["Jane Smith <jane -at- x.com>"])

    call_command("update_library_version_authors")

    assert older.authors.filter(email="jane@x.com").exists()


def test_library_name_filters_instead_of_raising(library):
    """``--library-name`` filtered on a field Library does not have."""
    other = baker.make("libraries.Library", name="asio", slug="asio")
    wanted = make_library_version(
        library, "boost-1.92.0", ["Jane Smith <jane -at- x.com>"]
    )
    unwanted = make_library_version(
        other, "boost-1.91.0", ["Juan Rodrigo <juan -at- x.com>"]
    )

    call_command("update_library_version_authors", "--library-name", library.name)

    assert wanted.authors.filter(email="jane@x.com").exists()
    assert unwanted.authors.count() == 0


def test_the_task_imports_the_data_before_binding_its_authors():
    """The author pass can only read what the import has already written."""
    baker.make("versions.Version", name="boost-1.92.0", slug="1-92-0")
    calls = Mock()
    with patch("versions.tasks.import_library_versions", calls.import_versions), patch(
        "libraries.tasks.call_command", calls.call_command
    ):
        synchronize_release_library_data("boost-1.92.0")

    assert calls.mock_calls == [
        ("import_versions", ("boost-1.92.0",), {"version_type": "tag"}),
        (
            "call_command",
            ("update_library_version_authors", "--release", "boost-1.92.0"),
            {},
        ),
    ]


def test_the_task_refuses_a_moving_branch():
    """Importing master or develop deletes library versions; this job does not."""
    baker.make("versions.Version", name="develop", slug="develop")
    calls = Mock()
    with patch("versions.tasks.import_library_versions", calls.import_versions), patch(
        "libraries.tasks.call_command", calls.call_command
    ):
        synchronize_release_library_data("develop")

    assert calls.mock_calls == []


def test_the_task_does_nothing_for_a_release_that_is_not_stored():
    calls = Mock()
    with patch("versions.tasks.import_library_versions", calls.import_versions), patch(
        "libraries.tasks.call_command", calls.call_command
    ):
        synchronize_release_library_data("boost-9.99.0")

    assert calls.mock_calls == []


def test_the_button_refuses_a_submission_with_no_release(client, super_user):
    """There is no unscoped run: an empty select must not start a sweep."""
    baker.make("versions.Version", name="boost-1.92.0", slug="1-92-0")
    client.force_login(super_user)

    with patch(TASK_PATH) as delay:
        response = client.post(reverse(BUTTON_URL), {"release": ""}, follow=True)

    delay.assert_not_called()
    assert "this job has no unscoped run" in response.content.decode()


def test_the_button_refuses_a_release_it_did_not_offer(client, super_user):
    baker.make("versions.Version", name="boost-1.92.0", slug="1-92-0")
    client.force_login(super_user)

    with patch(TASK_PATH) as delay:
        client.post(reverse(BUTTON_URL), {"release": "boost-9.99.0"}, follow=True)

    delay.assert_not_called()


def test_the_button_enqueues_the_release_it_was_pointed_at(client, super_user):
    baker.make("versions.Version", name="boost-1.92.0", slug="1-92-0")
    client.force_login(super_user)

    with patch(TASK_PATH, return_value=Mock(id="a-task-id")) as delay:
        client.post(reverse(BUTTON_URL), {"release": "boost-1.92.0"}, follow=True)

    delay.assert_called_once_with(release="boost-1.92.0")


def test_the_allowlist_holds_the_stored_releases_and_not_the_branches(
    client, super_user
):
    """The row buttons post a release, and this is the list it is checked against.

    Read from the database, so a release imported today can be pressed today, and
    a moving branch cannot be posted at all: importing one deletes library
    versions, which this job promises not to do.
    """
    baker.make("versions.Version", name="boost-1.92.0", slug="1-92-0")
    baker.make("versions.Version", name="develop", slug="develop")
    client.force_login(super_user)

    response = client.get(reverse(CHANGELIST_URL))

    button = next(
        b
        for b in response.context["task_buttons"]
        if b["argument"] == "release" and b["require_choice"]
    )
    assert ("boost-1.92.0", "1.92.0") in button["choices"]
    assert all(value != "develop" for value, _ in button["choices"])


def test_the_task_binds_authors_even_when_a_post_import_step_fails():
    """A point release ships no docs archive, and the import ends by scraping it.

    That raise has nothing to do with authorship, so losing the author pass to it
    would leave the release rendering "Unknown", which is what this job repairs.
    The import raises it as `PostImportStepFailed`, which says the library
    metadata the author pass reads was written before the step that failed.
    """
    baker.make("versions.Version", name="boost-1.91.0-1", slug="1-91-0-1")
    calls = Mock()
    calls.import_versions.side_effect = PostImportStepFailed(["array", "asio"])
    with patch("versions.tasks.import_library_versions", calls.import_versions), patch(
        "libraries.tasks.call_command", calls.call_command
    ):
        synchronize_release_library_data("boost-1.91.0-1")

    assert calls.call_command.call_args_list == [
        (("update_library_version_authors", "--release", "boost-1.91.0-1"), {}),
    ]


def test_the_task_aborts_when_the_import_fails_before_writing_anything():
    """A failure that is not the documentation scrape leaves the data untouched.

    Resolving the tag, building the GitHub client and writing the rows can all
    raise, and none of them has written a thing when they do. Binding authors
    over metadata that is as stale as it was found and reporting success would
    tell the operator the release was repaired when nothing was read at all.
    """
    baker.make("versions.Version", name="boost-1.92.0", slug="1-92-0")
    calls = Mock()
    calls.import_versions.side_effect = RuntimeError("no GitHub token configured")
    with patch("versions.tasks.import_library_versions", calls.import_versions), patch(
        "libraries.tasks.call_command", calls.call_command
    ):
        with pytest.raises(RuntimeError, match="no GitHub token"):
            synchronize_release_library_data("boost-1.92.0")

    calls.call_command.assert_not_called()


def test_a_post_import_failure_that_read_nothing_still_fails():
    """The two shapes of failure can arrive together, and the stricter one wins."""
    baker.make("versions.Version", name="boost-1.61.0", slug="1-61-0")
    calls = Mock()
    calls.import_versions.side_effect = PostImportStepFailed([])
    with patch("versions.tasks.import_library_versions", calls.import_versions), patch(
        "libraries.tasks.call_command", calls.call_command
    ):
        with pytest.raises(ValueError, match="Could not read the libraries"):
            synchronize_release_library_data("boost-1.61.0")

    calls.call_command.assert_not_called()


def _release_rows(rf, user):
    """The page's own annotated rows, keyed by release name."""
    from django.contrib.admin.sites import site

    from release_tools.models import ReleaseLibraryData

    model_admin = site._registry[ReleaseLibraryData]
    request = rf.get("/")
    request.user = user
    return model_admin, {
        version.name: version for version in model_admin.get_queryset(request)
    }


def test_the_page_reports_which_releases_need_repairing(rf, super_user, library):
    """The list exists to answer "which release needs this" before running it."""
    healthy = baker.make(
        "versions.Version", name="boost-1.92.0", slug="1-92-0", active=True
    )
    broken = baker.make(
        "versions.Version", name="boost-1.91.0-1", slug="1-91-0-1", active=True
    )
    bound = baker.make(
        "libraries.LibraryVersion",
        library=library,
        version=healthy,
        data={"authors": ["Jane"]},
    )
    bound.authors.add(super_user)
    baker.make(
        "libraries.LibraryVersion",
        library=library,
        version=broken,
        data={"authors": ["Jane"]},
    )

    model_admin, rows = _release_rows(rf, super_user)

    assert model_admin.needs_synchronizing(rows["boost-1.91.0-1"]) == "1 of 1"
    assert model_admin.needs_synchronizing(rows["boost-1.92.0"]) == "none"


def test_a_library_with_no_upstream_author_is_counted_apart(rf, super_user, library):
    """Three libraries name no author in their own metadata, on every release.

    Counting them as work to do reads as a fault on an otherwise healthy release,
    and no amount of synchronizing would ever clear it.
    """
    release = baker.make(
        "versions.Version", name="boost-1.92.0", slug="1-92-0", active=True
    )
    baker.make(
        "libraries.LibraryVersion",
        library=library,
        version=release,
        data={"authors": ""},
    )

    model_admin, rows = _release_rows(rf, super_user)
    row = rows["boost-1.92.0"]

    assert model_admin.needs_synchronizing(row) == "none"
    assert model_admin.no_author_upstream(row) == 1


def test_an_unimported_release_is_not_reported_as_healthy(rf, super_user):
    """No libraries at all is a different problem from no missing authors."""
    baker.make("versions.Version", name="boost-1.92.0", slug="1-92-0", active=True)

    model_admin, rows = _release_rows(rf, super_user)

    assert model_admin.needs_synchronizing(rows["boost-1.92.0"]) == (
        "no libraries imported"
    )


def test_each_release_gets_its_own_synchronize_button(client, super_user):
    """The job is pressed on the release it acts on; there is no select to mis-set."""
    baker.make("versions.Version", name="boost-1.92.0", slug="1-92-0", active=True)
    baker.make("versions.Version", name="boost-1.91.0-1", slug="1-91-0-1", active=True)
    client.force_login(super_user)

    body = client.get(reverse(CHANGELIST_URL)).content.decode()

    assert '<select name="release"' not in body
    for name in ("boost-1.92.0", "boost-1.91.0-1"):
        assert f'<input type="hidden" name="release" value="{name}">' in body


def test_a_release_synchronizing_does_not_hide_another_rows_button(client, super_user):
    """Two releases can be in flight at once; each row reports its own job.

    The key holding the button's last run remembers only the most recent of
    them, so a row read from it showed the release started second as running and
    offered the first one a button its own lock would have refused.
    """
    started = ("boost-1.92.0", "task-92"), ("boost-1.91.0", "task-91")
    finished = ("boost-1.90.0", "task-90")
    for name, _ in (*started, finished):
        baker.make(
            "versions.Version",
            name=name,
            slug=name.removeprefix("boost-").replace(".", "-"),
            active=True,
        )
    client.force_login(super_user)

    states = {task_id: ("STARTED", "") for _, task_id in started}
    states[finished[1]] = ("SUCCESS", "")
    for name, task_id in (*started, finished):
        with patch(TASK_PATH, return_value=Mock(id=task_id)):
            client.post(reverse(BUTTON_URL), {"release": name}, follow=True)

    with patch("core.admin_buttons.task_status", states.get):
        body = client.get(reverse(CHANGELIST_URL)).content.decode()

    for name, _ in started:
        assert f'<input type="hidden" name="release" value="{name}">' not in body
    assert body.count('<span class="release-tools-running">Running</span>') == 2
    # The finished one is offered again, rather than left reading as running.
    assert f'<input type="hidden" name="release" value="{finished[0]}">' in body


def test_a_library_whose_metadata_was_never_read_counts_as_work(
    rf, super_user, library
):
    """An absent `authors` key is what a failed import leaves behind.

    It is also the shape a JSON exclusion silently drops: SQL reads `NOT
    (data->>'authors' = '')` as unknown when the key is missing, so these rows
    fall out of a `~Q` filter and the release reports itself healthy.
    """
    release = baker.make(
        "versions.Version", name="boost-1.92.0", slug="1-92-0", active=True
    )
    baker.make("libraries.LibraryVersion", library=library, version=release, data={})

    model_admin, rows = _release_rows(rf, super_user)
    row = rows["boost-1.92.0"]

    assert model_admin.needs_synchronizing(row) == "1 of 1"
    assert model_admin.no_author_upstream(row) == ""


def test_the_task_fails_when_the_import_reads_nothing():
    """A release whose libraries could not be read must not report success.

    `import_library_versions` logs and returns on a bad ref or unreadable
    .gitmodules rather than raising, so without this the button says Finished
    over a run that changed nothing.
    """
    baker.make("versions.Version", name="boost-1.61.0", slug="1-61-0")
    calls = Mock()
    calls.import_versions.return_value = None
    with patch("versions.tasks.import_library_versions", calls.import_versions), patch(
        "libraries.tasks.call_command", calls.call_command
    ):
        with pytest.raises(ValueError, match="Could not read the libraries"):
            synchronize_release_library_data("boost-1.61.0")

    calls.call_command.assert_not_called()
