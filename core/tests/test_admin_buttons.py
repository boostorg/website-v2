"""Tests for the shared changelist task buttons.

This module owns the *mixin's* contract - POST only, permission-gated, locked
against a double click, honest about the state of the last run. Which button
enqueues which task is the wiring each app asserts for itself.

Exercised through the badges admin, which is where the real buttons live: a
test-only ``ModelAdmin`` would need its own model, its own registration and its
own url namespace to assert anything about urls and permissions.
"""

from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.urls import reverse
from django.utils.html import escape
from model_bakery import baker

from badges.admin import BACKFILL_BUTTON, RECONCILE_BUTTON
from badges.sources import AUTOMATIC_SLUGS
from core.admin_buttons import TASK_BUTTON_COOLDOWN_SECONDS

pytestmark = pytest.mark.django_db

BACKFILL_URL = "admin:badges_userachievement_backfill"
STATUS_URL = "admin:badges_userachievement_backfill_status"
CHANGELIST_URL = "admin:badges_userachievement_changelist"
TASK_PATH = "badges.admin.backfill_achievements_task.delay"

# Both live buttons, so the contract is asserted on more than the single one the
# rest of this module drives. The scoped and status-rendering behaviour is only
# exercised through the backfill button, which is the one that has choices. The
# third element is whether the button names the caller to its task.
BUTTONS = [
    ("admin:badges_userachievement_backfill", "backfill_achievements_task", True),
    ("admin:badges_userbadge_recalculate", "recalculate_all_badges_task", False),
]

# The last run of the button, for display; and the last run of one of its jobs,
# which is what decides whether another may start.
LAST_RUN_KEY = "admin-task-button:badges_userachievement_backfill"
JOB_KEY = f"{LAST_RUN_KEY}:job:all"


@pytest.fixture(autouse=True)
def _clear_task_button_locks():
    """The buttons lock through the cache; isolate tests from each other."""
    cache.clear()


def _result(task_id="a-task-id"):
    """A stand-in for what ``.delay()`` returns."""
    return Mock(id=task_id)


def _state(state):
    """Patch the Celery state of every task id for the duration of a block."""
    return patch("core.admin_buttons.AsyncResult", return_value=Mock(state=state))


def _running_job(task_id="running-task"):
    """Record ``task_id`` as this button's last run of the unscoped job."""
    cache.set(JOB_KEY, task_id, TASK_BUTTON_COOLDOWN_SECONDS)
    cache.set(
        LAST_RUN_KEY,
        {"task_id": task_id, "scope": ""},
        TASK_BUTTON_COOLDOWN_SECONDS,
    )


def _bare_staff(email):
    """A staff account holding no badges permissions at all."""
    return baker.make("users.User", email=email, is_staff=True)


@pytest.mark.parametrize("url_name,task,names_actor", BUTTONS)
def test_button_still_swallows_a_double_click(
    client, super_user, url_name, task, names_actor
):
    """Two immediate posts enqueue once, whatever the worker is doing."""
    client.force_login(super_user)

    with patch(f"badges.admin.{task}.delay", return_value=_result()) as delay:
        client.post(reverse(url_name))
        client.post(reverse(url_name))

    delay.assert_called_once_with(
        **({"actor_id": super_user.pk} if names_actor else {})
    )


def test_button_does_not_enqueue_after_losing_the_click_floor_claim(client, super_user):
    """A concurrent request that wins the atomic claim is the only enqueue."""
    client.force_login(super_user)

    with (
        patch("core.admin_buttons.cache.add", return_value=False),
        patch(TASK_PATH) as delay,
    ):
        response = client.post(reverse(BACKFILL_URL), follow=True)

    delay.assert_not_called()
    assert "not starting another one" in response.content.decode()


@pytest.mark.parametrize("url_name,task,_names_actor", BUTTONS)
def test_button_ignores_a_get(client, super_user, url_name, task, _names_actor):
    """A GET must never start the job: link prefetchers and history restores do.

    The button is a POST form, so a GET means something other than a click.
    """
    client.force_login(super_user)

    with patch(f"badges.admin.{task}.delay") as delay:
        response = client.get(reverse(url_name))

    delay.assert_not_called()
    assert response.status_code == 302


@pytest.mark.parametrize("url_name,task,_names_actor", BUTTONS)
def test_button_requires_change_permission(client, db, url_name, task, _names_actor):
    """Staff alone is not authorisation to rewrite every row of a table.

    ``admin_site.admin_view`` only checks ``is_staff``, so without this a support
    account with no badges permissions could start a full-database job.
    """
    client.force_login(_bare_staff("plain-staff@example.com"))

    with patch(f"badges.admin.{task}.delay") as delay:
        response = client.post(reverse(url_name))

    assert response.status_code == 403
    delay.assert_not_called()


def test_button_is_not_rendered_without_permission(client, db):
    """A button the caller cannot use must not be offered."""
    staff = _bare_staff("viewer-staff@example.com")
    staff.user_permissions.add(
        Permission.objects.get(
            codename="view_userachievement", content_type__app_label="badges"
        )
    )
    client.force_login(staff)

    response = client.get(reverse(CHANGELIST_URL))

    assert response.status_code == 200
    assert response.context["task_buttons"] == []


def test_button_refuses_while_the_task_is_running(client, super_user):
    """A job a worker has picked up and not finished blocks a second run."""
    client.force_login(super_user)
    _running_job()

    with _state("STARTED"), patch(TASK_PATH) as delay:
        response = client.post(reverse(BACKFILL_URL), follow=True)

    delay.assert_not_called()
    assert "not starting another one" in response.content.decode()


def test_button_allows_a_second_run_once_the_task_is_ready(client, super_user):
    """A finished job does not hold the button for the rest of the cooldown.

    The regression test for the dead lock: before the id was tracked, any press
    took the button out for ten minutes even if the work took two seconds.
    """
    client.force_login(super_user)
    _running_job("finished-task")

    with _state("SUCCESS"), patch(TASK_PATH, return_value=_result()) as delay:
        client.post(reverse(BACKFILL_URL))

    delay.assert_called_once_with(actor_id=super_user.pk)


def test_button_allows_a_second_run_once_a_queued_task_is_stale(client, super_user):
    """A task no worker ever collected must not wedge the button.

    ``PENDING`` is both "queued a moment ago" and "queued at a broker nothing is
    listening to". Past the click floor the two are indistinguishable, so the
    button reopens rather than staying locked for the full cooldown.
    """
    client.force_login(super_user)
    _running_job("orphaned-task")

    with _state("PENDING"), patch(TASK_PATH, return_value=_result()) as delay:
        client.post(reverse(BACKFILL_URL))

    delay.assert_called_once_with(actor_id=super_user.pk)


def test_button_records_the_task_id(client, super_user):
    """The lock holds the id of the job it started, not a boolean."""
    client.force_login(super_user)

    with patch(TASK_PATH, return_value=_result("the-new-task")):
        client.post(reverse(BACKFILL_URL))

    assert cache.get(JOB_KEY) == "the-new-task"
    assert cache.get(LAST_RUN_KEY) == {"task_id": "the-new-task", "scope": ""}


def test_button_falls_back_to_the_cooldown_without_a_result_backend(client, super_user):
    """A state the backend cannot report is treated as "still running".

    Degrading to the behaviour these buttons had before is the safe direction: a
    button that refuses is recoverable, a second full-table job started on a
    guess is not.
    """
    client.force_login(super_user)
    _running_job("unknowable-task")

    with patch("core.admin_buttons.AsyncResult", side_effect=OSError("no backend")):
        with patch(TASK_PATH) as delay:
            response = client.post(reverse(BACKFILL_URL), follow=True)

    delay.assert_not_called()
    assert "not starting another one" in response.content.decode()


def test_changelist_reports_a_running_task(client, super_user):
    """The state of the last run is on the page, in words, next to the button."""
    client.force_login(super_user)
    _running_job()

    with _state("STARTED"):
        body = client.get(reverse(CHANGELIST_URL)).content.decode()

    assert "Backfill achievements: <strong>Running</strong>" in body


def test_changelist_reports_a_failed_task(client, super_user):
    """A failure says so, and says what the failure was."""
    client.force_login(super_user)
    _running_job("failed-task")
    failed = Mock(state="FAILURE", result=RuntimeError("no source is wired"))

    with patch("core.admin_buttons.AsyncResult", return_value=failed):
        body = client.get(reverse(CHANGELIST_URL)).content.decode()

    assert "<strong>Failed</strong>" in body
    assert "no source is wired" in body


def test_changelist_says_nothing_before_the_first_run(client, super_user):
    """No run is no status, rather than a status of nothing."""
    client.force_login(super_user)

    body = client.get(reverse(CHANGELIST_URL)).content.decode()

    assert "task-button-status" not in body


def test_changelist_ignores_a_lock_from_an_older_deploy(client, super_user):
    """The key used to hold a boolean; finding one must not break the page."""
    client.force_login(super_user)
    cache.set(LAST_RUN_KEY, True, TASK_BUTTON_COOLDOWN_SECONDS)

    response = client.get(reverse(CHANGELIST_URL))

    assert response.status_code == 200
    assert "task-button-status" not in response.content.decode()


def test_changelist_polls_only_while_the_task_runs(client, super_user):
    """A finished job stops the polling, by rendering nothing to poll with."""
    client.force_login(super_user)
    _running_job("a-task")
    status_url = reverse(STATUS_URL)

    with _state("STARTED"):
        running = client.get(reverse(CHANGELIST_URL)).content.decode()
    with _state("SUCCESS"):
        finished = client.get(reverse(CHANGELIST_URL)).content.decode()

    assert f'hx-get="{status_url}"' in running
    assert "hx-get" not in finished
    assert "<strong>Finished</strong>" in finished


def test_status_endpoint_renders_without_js(client, super_user):
    """A plain GET of the fragment returns what the poll would return.

    Which is the same thing the changelist renders inline, so the page is right
    with JavaScript off and the polling only saves a reload.
    """
    client.force_login(super_user)
    _running_job()

    with _state("STARTED"):
        fragment = client.get(reverse(STATUS_URL)).content.decode()
        changelist = client.get(reverse(CHANGELIST_URL)).content.decode()

    assert "Backfill achievements: <strong>Running</strong>" in fragment
    assert fragment.strip() in changelist


def test_status_endpoint_reports_an_unreadable_backend(client, super_user):
    """A state the backend cannot report is not rendered as a state."""
    client.force_login(super_user)
    _running_job("unknowable-task")

    with patch("core.admin_buttons.AsyncResult", side_effect=OSError("no backend")):
        body = client.get(reverse(STATUS_URL)).content.decode()

    assert "Status unavailable" in body
    assert "hx-get" not in body


def test_status_endpoint_requires_permission(client, db):
    """Staff who are not offered the button are not offered its status either."""
    client.force_login(_bare_staff("status-staff@example.com"))
    _running_job()

    assert client.get(reverse(STATUS_URL)).status_code == 403


def test_button_does_not_lock_when_the_enqueue_fails(client, super_user):
    """A broker that is down must not take the button out for ten minutes."""
    client.force_login(super_user)

    with patch(TASK_PATH, side_effect=OSError("broker down")):
        response = client.post(reverse(BACKFILL_URL), follow=True)

    assert "task queue is not reachable" in response.content.decode()
    assert cache.get(JOB_KEY) is None
    assert cache.get(f"{JOB_KEY}:recent") is None

    with patch(TASK_PATH, return_value=_result()) as delay:
        client.post(reverse(BACKFILL_URL))

    delay.assert_called_once_with(actor_id=super_user.pk)


def test_changelist_offers_every_wired_source(client, super_user):
    """The select is built from the wired iterators, plus running them all."""
    client.force_login(super_user)

    body = client.get(reverse(CHANGELIST_URL)).content.decode()

    assert '<option value="">All sources</option>' in body
    for slug in AUTOMATIC_SLUGS:
        assert f'<option value="{slug}">' in body


def test_changelist_renders_each_button_description(client, super_user):
    """A button's help text reaches the page, so its label is not the only clue.

    Asserted against the ``TaskButton`` rather than against a copy of the prose, so
    rewording a description does not break the test but dropping it does.
    """
    client.force_login(super_user)

    body = client.get(reverse(CHANGELIST_URL)).content.decode()

    for button in (BACKFILL_BUTTON, RECONCILE_BUTTON):
        assert button.description, f"{button.name} has no description"
        assert escape(button.description) in body


def test_changelist_keeps_task_buttons_out_of_the_object_tools(client, super_user):
    """The buttons render in their own list, not in Django's right-aligned tools.

    ``ul.object-tools`` is ``text-align: right`` and lays its items out inline, so
    a button that ends up back inside it is crammed against the far edge of the
    page next to "Add user achievement" rather than stacked below it.
    """
    client.force_login(super_user)

    body = client.get(reverse(CHANGELIST_URL)).content.decode()
    tools_start = body.index('<ul class="object-tools">')
    tools = body[tools_start : body.index("</ul>", tools_start)]

    assert '<ul class="task-buttons">' in body
    assert "Add user achievement" in tools
    assert "Backfill achievements" not in tools
    assert body.index("Backfill achievements") < body.index("Reconcile achievements")


def test_scoped_button_passes_its_argument(client, super_user):
    """Choosing a source runs the task for that source alone."""
    client.force_login(super_user)

    with patch(TASK_PATH, return_value=_result()) as delay:
        response = client.post(
            reverse(BACKFILL_URL), {"slug": "code-commits"}, follow=True
        )

    delay.assert_called_once_with(slug="code-commits", actor_id=super_user.pk)
    assert "Limited to Code Commits." in response.content.decode()


def test_scoped_button_refuses_an_unknown_value(client, super_user):
    """``call_command`` does not check choices, so the view has to.

    A slug with no iterator would otherwise raise a ``KeyError`` inside the
    worker, where nothing surfaces it.
    """
    client.force_login(super_user)

    with patch(TASK_PATH) as delay:
        response = client.post(
            reverse(BACKFILL_URL), {"slug": "not-a-source"}, follow=True
        )

    delay.assert_not_called()
    assert "not one of the available options" in response.content.decode()


def test_status_names_the_source_of_a_scoped_run(client, super_user):
    """A status of "Running" is ambiguous when the button can be scoped."""
    client.force_login(super_user)

    with patch(TASK_PATH, return_value=_result()):
        client.post(reverse(BACKFILL_URL), {"slug": "code-commits"})
    with _state("STARTED"):
        body = client.get(reverse(CHANGELIST_URL)).content.decode()

    assert "Backfill achievements (Code Commits): <strong>Running</strong>" in body
