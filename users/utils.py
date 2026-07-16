def humanize_link_lifetime(delta):
    """Return a short phrase for a link lifetime, e.g. "3 days" or "1 hour".

    Picks the largest whole unit so the copy reads naturally for whole-day or
    whole-hour settings, and pluralizes correctly (so a one-day or one-hour
    timeout never renders as "1 days" / "0 days").
    """
    seconds = int(delta.total_seconds())
    for unit_seconds, name in ((86400, "day"), (3600, "hour"), (60, "minute")):
        count = seconds // unit_seconds
        if count:
            return f"{count} {name}{'' if count == 1 else 's'}"
    return f"{seconds} second{'' if seconds == 1 else 's'}"
