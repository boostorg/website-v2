"""Changelist buttons that enqueue a Celery task.

Kept in one place because every one of them needs the same four things and gets
them wrong independently otherwise: a POST (so a link prefetch or a restored
browser tab cannot start a full-table job), a CSRF token, a short cache lock so a
double-click does not queue the work twice, and a permission check -
``admin_site.admin_view`` only asks whether the caller is staff, which is not
enough to authorise rewriting every row of a table.

The lock is the enqueued task's id rather than a boolean, so it can answer "is
that job still running" instead of "was this button pressed recently". Three
cache keys, each with one job:

* ``<key>:job:<argument>`` (the cooldown) - the id of the last run of *this*
  job, which blocks another while that run is demonstrably executing. Settings
  enable ``task_track_started``, so a task a worker has collected reports
  ``STARTED`` rather than ``PENDING``. Keyed by the argument, so a run scoped to
  one source does not refuse a run for another.
* ``<key>:job:<argument>:recent`` (a few seconds) - one click is one job. A
  second POST inside the floor is a double-click or a resubmitted form, whatever
  the worker is doing. It is also the grace period a queued task gets to be
  picked up: past it a ``PENDING`` task no longer blocks, because a task that no
  worker will ever collect must not wedge the button.
* ``<key>`` (the cooldown) - the last run of the button whatever it targeted,
  read only to render its state.

The trade is deliberate: a duplicate run of an idempotent job is recoverable, a
button locked for ten minutes because the worker died is not.

The state is rendered with the page, so it is correct without JavaScript; the
status view exists so HTMX can re-fetch just that fragment while the job runs.

A button whose job deletes rows sets ``permission`` (change is not enough to
authorise a delete) and ``confirm`` (a preview page, so the click that starts it
is an informed one). Both are opt-in: a button that only rewrites derived state
needs neither.
"""

import logging
from dataclasses import dataclass
from typing import Any

from celery.result import AsyncResult
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from config.celery import app as celery_app

logger = logging.getLogger(__name__)

TASK_BUTTON_COOLDOWN_SECONDS = 600
TASK_BUTTON_CLICK_FLOOR_SECONDS = 30
TASK_BUTTON_POLL_INTERVAL = "every 5s"

# A task in one of these has been collected by a worker and is not finished.
# Anything else is either terminal or not yet collected.
RUNNING_STATES = frozenset({"STARTED", "RETRY"})
FINISHED_STATES = frozenset({"SUCCESS", "FAILURE", "REVOKED"})

# Celery's own state names, which mean something to Celery and nothing to the
# person who pressed the button.
TASK_STATE_LABELS = {
    "PENDING": "Queued",
    "STARTED": "Running",
    "RETRY": "Retrying",
    "SUCCESS": "Finished",
    "FAILURE": "Failed",
    "REVOKED": "Cancelled",
}
UNKNOWN_STATE_LABEL = "Status unavailable"


@dataclass(frozen=True)
class TaskButton:
    """One changelist button and the task it enqueues.

    ``choices`` turns the button into a scoped run: ``(value, label)`` pairs
    become a select beside it, and the chosen value is passed to the task as
    ``argument``. Choosing nothing runs the task with no arguments at all, which
    is what every unscoped caller of these tasks already does.

    ``permission`` names the permission that authorises the job, for a button
    whose task does something the model's *change* permission does not cover -
    a sweep that deletes rows wants ``delete_``, not ``change_``. Left unset, the
    change permission is the gate, which is what a button that only rewrites
    derived state needs.

    ``confirm`` interposes a preview between the click and the enqueue, for a job
    worth reading about before it runs. It is called as ``confirm(request, value)``
    and returns the preview's context: ``title``, ``summary``, ``rows`` (each with
    ``label``, ``detail`` and ``warning``), ``warning``, and ``can_apply``. The
    task is enqueued only when the preview's own submit comes back, which is what
    carries ``apply``.

    ``description`` renders under the button as help text. These jobs are not
    self-explanatory from a label - two of them differ only in whether they can
    remove anything - and the person deciding which to press is not the person who
    wrote them. One or two sentences: what it changes, and what it leaves alone.
    """

    name: str
    label: str
    task: Any
    success_message: str
    busy_message: str
    argument: str = ""
    choice_label: str = ""
    choices: tuple = ()
    all_label: str = "All"
    permission: str = ""
    confirm: Any = None
    description: str = ""

    def __post_init__(self):
        """Refuse a select whose value would go nowhere."""
        if self.choices and not self.argument:
            raise ValueError(
                f"TaskButton {self.name!r} has choices but no argument to pass "
                "the chosen value as."
            )


def task_status(task_id):
    """``(state, error)`` for ``task_id``, or ``None`` if the backend cannot say.

    A result backend is configured in every environment this admin runs in, but
    an unreachable one must not turn into a 500 on a changelist, and a state it
    cannot report must not be rendered as fact. Callers treat ``None`` as "assume
    the job is still running", which is the behaviour these buttons had before
    they tracked task ids at all.
    """
    try:
        result = AsyncResult(task_id, app=celery_app)
        state = result.state
        return state, str(result.result) if state == "FAILURE" else ""
    except Exception:
        logger.warning("Could not read Celery state for task %s", task_id)
        return None


class TaskButtonAdminMixin:
    """Adds ``task_buttons`` to a ``ModelAdmin`` changelist.

    Set ``task_buttons`` to a tuple of ``TaskButton``. Each one gets its own
    admin view, reachable only by POST, and is rendered as a submit button by
    ``admin/task_buttons_change_list.html``. Subclasses that need their own
    changelist template should extend that one.
    """

    change_list_template = "admin/task_buttons_change_list.html"
    task_buttons = ()
    task_button_cooldown_seconds = TASK_BUTTON_COOLDOWN_SECONDS
    task_button_click_floor_seconds = TASK_BUTTON_CLICK_FLOOR_SECONDS

    def get_urls(self):
        """Register a POST-only view and a status view per button, first."""
        custom = []
        for button in self.task_buttons:
            custom += [
                path(
                    f"{button.name}/",
                    self.admin_site.admin_view(self._task_button_view(button)),
                    name=self._task_button_url_name(button),
                ),
                path(
                    f"{button.name}/status/",
                    self.admin_site.admin_view(self._task_status_view(button)),
                    name=f"{self._task_button_url_name(button)}_status",
                ),
            ]
        return custom + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        """Pass the resolved button urls and their last run to the template.

        Nothing is passed to a caller who could not use it, so the buttons are not
        rendered as dead controls. The status is rendered here rather than fetched,
        so it is right on a plain page load and polling is only an enhancement.
        """
        buttons = [
            {
                "url": reverse(f"admin:{self._task_button_url_name(button)}"),
                "label": button.label,
                "argument": button.argument,
                "choice_label": button.choice_label,
                "choices": button.choices,
                "all_label": button.all_label,
                "description": button.description,
                "field_id": f"task-button-{button.name}-{button.argument}",
                "status": self._task_button_status(button),
            }
            for button in self.task_buttons
            if self._task_button_allows(request, button)
        ]
        extra_context = {**(extra_context or {}), "task_buttons": buttons}
        return super().changelist_view(request, extra_context)

    def _task_button_allows(self, request, button):
        """Whether this caller may start ``button``'s job.

        Per button, because they do not all cost the same: the change permission
        is enough to rewrite derived state, and not enough to delete rows.
        """
        if button.permission:
            return request.user.has_perm(button.permission)
        return self.has_change_permission(request)

    def _task_button_url_name(self, button):
        """The admin url name for ``button``, which every other key derives from."""
        opts = self.model._meta
        return f"{opts.app_label}_{opts.model_name}_{button.name}"

    def _task_button_cache_key(self, button):
        """The key holding this button's last run, whatever it was scoped to.

        Read for display only. The button asks ``_task_button_job_key`` whether
        it may start something.
        """
        return f"admin-task-button:{self._task_button_url_name(button)}"

    def _task_button_job_key(self, button, value=""):
        """The key holding the id of the last run of one particular job.

        Keyed by the chosen argument, so a backfill of one source does not refuse
        a backfill of another - they are different jobs that happen to share a
        button.
        """
        return f"{self._task_button_cache_key(button)}:job:{value or 'all'}"

    def _task_button_is_busy(self, button, value=""):
        """Whether this job is still running, or was started a moment ago."""
        key = self._task_button_job_key(button, value)
        if cache.get(f"{key}:recent") is not None:
            return True
        task_id = cache.get(key)
        if task_id is None:
            return False
        status = task_status(task_id)
        return status is None or status[0] in RUNNING_STATES

    def _task_button_status(self, button):
        """What to say about ``button``'s last run, if there was one.

        ``label`` is empty when nothing has been started recently, which the
        template renders as nothing at all rather than as "no status".
        """
        status = {
            "url": reverse(f"admin:{self._task_button_url_name(button)}_status"),
            "name": button.label,
            "scope": "",
            "label": "",
            "error": "",
            "poll": False,
            "poll_interval": TASK_BUTTON_POLL_INTERVAL,
        }
        last = cache.get(self._task_button_cache_key(button))
        if not isinstance(last, dict):
            # Either nothing has run, or the key was written by a deploy that
            # stored something else under it.
            return status
        result = task_status(last["task_id"])
        status["scope"] = last["scope"]
        if result is None:
            # Nothing to poll for: a backend that cannot answer now will not
            # answer in five seconds either.
            status["label"] = UNKNOWN_STATE_LABEL
            return status
        state, error = result
        status["label"] = TASK_STATE_LABELS.get(state, state)
        status["error"] = error
        status["poll"] = state not in FINISHED_STATES
        return status

    def _task_status_view(self, button):
        """Build the view that renders ``button``'s status on its own."""

        def view(request):
            """Render the status fragment, for an HTMX poll or a plain GET."""
            # Same gate as the button: a caller who is not offered the control is
            # not offered the state of the job behind it either.
            if not self._task_button_allows(request, button):
                raise PermissionDenied
            return render(
                request,
                "admin/task_button_status.html",
                {"status": self._task_button_status(button)},
            )

        return view

    def _task_button_view(self, button):
        """Build the view that enqueues ``button``'s task."""

        def view(request):
            """Enqueue the task on POST, then send the caller back to the list."""
            opts = self.model._meta
            redirect_url = reverse(
                f"admin:{opts.app_label}_{opts.model_name}_changelist"
            )
            if request.method != "POST":
                return HttpResponseRedirect(redirect_url)
            if not self._task_button_allows(request, button):
                raise PermissionDenied

            choices = dict(button.choices)
            value = request.POST.get(button.argument, "") if choices else ""
            # ``call_command`` does not enforce an argument's ``choices``, so an
            # unvetted value would only fail inside the worker, where nobody is
            # looking.
            if value and value not in choices:
                self.message_user(
                    request,
                    "That is not one of the available options; nothing has been "
                    "started.",
                    level=messages.WARNING,
                )
                return HttpResponseRedirect(redirect_url)

            if self._task_button_is_busy(button, value):
                self.message_user(request, button.busy_message, level=messages.WARNING)
                return HttpResponseRedirect(redirect_url)

            # Checked after the busy test, so nobody reads a preview of a job that
            # was never going to start, and before the enqueue, which the preview's
            # own submit is what authorises.
            if button.confirm and "apply" not in request.POST:
                preview = button.confirm(request, value)
                return render(
                    request,
                    "admin/dry_run_confirm.html",
                    {
                        **self.admin_site.each_context(request),
                        "opts": opts,
                        "title": preview.get("title") or button.label,
                        "preview": preview,
                        "form_action": "",
                        # The empty value is the "all" option, and passing it back
                        # as a hidden field would be the same as leaving it out.
                        "hidden_fields": (
                            [{"name": button.argument, "value": value}] if value else []
                        ),
                        "submit_label": button.label,
                        "cancel_url": redirect_url,
                    },
                )

            job_key = self._task_button_job_key(button, value)
            # Claimed before the enqueue, so two simultaneous clicks cannot both
            # get through, and released again if the enqueue fails: a broker that
            # is down would otherwise hold the button for the whole cooldown.
            if not cache.add(
                f"{job_key}:recent", True, self.task_button_click_floor_seconds
            ):
                self.message_user(request, button.busy_message, level=messages.WARNING)
                return HttpResponseRedirect(redirect_url)
            try:
                result = button.task.delay(
                    **({button.argument: value} if value else {})
                )
            except Exception:
                cache.delete(f"{job_key}:recent")
                logger.exception("Could not enqueue %s", button.name)
                self.message_user(
                    request,
                    "Could not queue the job: the task queue is not reachable. "
                    "Nothing has been started.",
                    level=messages.ERROR,
                )
                return HttpResponseRedirect(redirect_url)

            # ``str`` because this is written to a cache that has to serialise it,
            # and a task id is a string in every real case.
            task_id = str(result.id)
            scope = choices.get(value, "")
            cache.set(job_key, task_id, self.task_button_cooldown_seconds)
            cache.set(
                self._task_button_cache_key(button),
                {"task_id": task_id, "scope": scope},
                self.task_button_cooldown_seconds,
            )
            message = button.success_message
            if scope:
                message = f"{message} Limited to {scope}."
            self.message_user(request, message)
            return HttpResponseRedirect(redirect_url)

        return view
