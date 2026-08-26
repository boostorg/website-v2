"""Shared arguments for the badge management commands."""

from argparse import ArgumentTypeError

from django.contrib.auth import get_user_model

from badges.models import SyncTrigger


def positive_integer(value):
    """Parse a strictly positive integer for ``argparse``."""
    parsed = int(value)
    if parsed <= 0:
        raise ArgumentTypeError("must be a positive integer")
    return parsed


def add_sync_log_arguments(parser):
    """Register the options describing how a run was started.

    Both are for the sync log, and both are how a caller that is not a person at a
    shell says so: the release pipeline sets the trigger, and a changelist button
    names the admin behind it.
    """
    parser.add_argument(
        "--trigger",
        choices=SyncTrigger.values,
        default=None,
        help=(
            "How this run was started, recorded in the sync log (default: admin "
            "when --triggered-by names somebody, otherwise command)."
        ),
    )
    parser.add_argument(
        "--triggered-by",
        dest="actor_id",
        type=positive_integer,
        metavar="USER_ID",
        help="Primary key of the person who started this run, for the sync log.",
    )


def resolve_sync_log(options, stderr):
    """``(trigger, actor)`` describing where this run came from.

    A named person means somebody pressed a button, which is why a caller passing
    ``--triggered-by`` need not also state the trigger. An explicit one still wins,
    so the release pipeline can label its own sweep.

    An id that resolves to nobody is reported and otherwise ignored: attribution is
    worth less than the run itself, so a member deleted between a button press and
    the worker collecting the job costs the log a name, not the sweep. The trigger
    still says a person started it, because one did.
    """
    actor_id = options["actor_id"]
    trigger = options["trigger"] or (
        SyncTrigger.ADMIN if actor_id else SyncTrigger.COMMAND
    )
    if actor_id is None:
        return trigger, None

    actor = get_user_model().objects.filter(pk=actor_id).first()
    if actor is None:
        stderr.write(
            f"No member with id {actor_id}: the sync log will not record who "
            "started this run."
        )
    return trigger, actor
