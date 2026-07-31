"""Shared argument types for badge management commands."""

from argparse import ArgumentTypeError


def positive_integer(value):
    """Parse a strictly positive integer for ``argparse``."""
    parsed = int(value)
    if parsed <= 0:
        raise ArgumentTypeError("must be a positive integer")
    return parsed
