"""Who a feedback submission is counted against."""

import ipaddress


def submitter_key(request):
    """Stable identifier for the submitter, or None when there is nothing to key on.

    Members are keyed by account, everyone else by network address. No session is
    started, so an anonymous visitor leaves with no cookie they did not already
    have and their pages stay shareable in the CDN.

    The trade is that one allowance now covers everyone behind a single address,
    an office or a campus. At this quota that is not a limit a person would meet.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return f"user:{user.pk}"

    address = client_address(request)
    return f"ip:{address}" if address else None


def client_address(request):
    """The caller's address, most trustworthy source first.

    `Fastly-Client-IP` is overwritten by the CDN, so it is the one value in the
    chain a caller cannot choose. `X-Forwarded-For` reaches us as what the caller
    sent followed by what nginx saw, because nginx appends rather than replaces.
    Its first entry is caller-supplied, and is only a fallback for environments
    with no CDN in front.

    Parsed rather than trusted: the result becomes part of a cache key, and these
    are client-supplied headers.
    """
    candidates = (
        request.headers.get("fastly-client-ip", ""),
        request.headers.get("x-forwarded-for", "").split(",")[0],
        request.META.get("REMOTE_ADDR", ""),
    )
    for candidate in candidates:
        try:
            return str(ipaddress.ip_address(candidate.strip()))
        except ValueError:
            continue
    return ""
