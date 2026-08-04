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
        default=SyncTrigger.COMMAND,
        help="How this run was started, recorded in the sync log.",
    )
    parser.add_argument(
        "--triggered-by",
        dest="actor_id",
        type=positive_integer,
        metavar="USER_ID",
        help="Primary key of the person who started this run, for the sync log.",
    )


def resolve_actor(actor_id, stderr):
    """The member ``--triggered-by`` names, or ``None``.

    An id that resolves to nobody is reported and otherwise ignored: attribution is
    worth less than the run itself, so a member deleted between a button press and
    the worker collecting the job costs the log a name, not the sweep.
    """
    if actor_id is None:
        return None
    actor = get_user_model().objects.filter(pk=actor_id).first()
    if actor is None:
        stderr.write(
            f"No member with id {actor_id}: the sync log will not record who "
            "started this run."
        )
    return actor
