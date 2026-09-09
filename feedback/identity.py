"""Who a feedback submission is counted against."""


def submitter_key(request):
    """Stable identifier for the submitter, or None when there is nothing to key on.

    Members are keyed by account. Everyone else is keyed by session, which is
    per-browser rather than per-IP, so visitors sharing a NAT do not share a
    bucket. Clearing cookies earns a fresh key; the beta flags stay the hard stop.

    Anonymous visitors have no session until something writes to one, so this
    creates it. Callers already run inside a swallow-everything guard, because a
    session store that is unreachable must not cost us the report.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return f"user:{user.pk}"

    session = getattr(request, "session", None)
    if session is None:
        return None
    if not session.session_key:
        session.create()
    return f"session:{session.session_key}"
