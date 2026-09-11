"""Who a feedback submission is counted against."""

import ipaddress

import structlog

logger = structlog.get_logger()


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
    """The caller's address, or empty when none can be trusted.

    Only two sources are consulted. The CDN overwrites `Fastly-Client-IP`, and
    `REMOTE_ADDR` comes from the server rather than the request, so neither can
    be chosen by the caller.

    `X-Forwarded-For` is deliberately not consulted. nginx appends to it instead
    of replacing it, so its first entry is whatever the caller sent: a different
    value on each request would buy a fresh allowance every time and the limit
    would count nothing.

    Parsed rather than trusted, since the result becomes part of a cache key.
    """
    candidates = (
        ("fastly-client-ip", request.headers.get("fastly-client-ip", "")),
        ("remote-addr", request.META.get("REMOTE_ADDR", "")),
    )
    for source, candidate in candidates:
        try:
            address = str(ipaddress.ip_address(candidate.strip()))
        except ValueError:
            continue

        logger.info("Resolved feedback submitter address from %s", source)
        return address
    logger.warning("No usable feedback submitter address")
    return ""
