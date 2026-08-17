"""Feedback submission endpoint plus the standalone form used as the no-JS fallback."""

from urllib.parse import urlsplit

import structlog
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from waffle import flag_is_active

from feedback.diagnostics import (
    clean_client_diagnostics,
    page_context,
    recent_server_errors,
)
from feedback.models import (
    MESSAGE_MAX_LENGTH,
    PAGE_URL_MAX_LENGTH,
    USER_AGENT_MAX_LENGTH,
    Feedback,
    FeedbackForm,
)

logger = structlog.get_logger()

SUCCESS_MESSAGE = "Thanks for the feedback — the team will take a look."
SIGNED_OUT_MESSAGE = "Your session has expired. Please sign in again to send feedback."
THROTTLE_MESSAGE = (
    "Thanks for all the feedback! You've reached the limit for now — "
    "please try again in a little while."
)

RATE_LIMIT = 40
RATE_WINDOW = 3600  # seconds


def wants_json(request):
    """The widget marks its fetch() calls so it can show errors without navigating."""
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def is_rate_limited(request):
    """Cache-backed so it holds for clients that discard cookies, unlike a session gate.

    Fails open. The cache is Redis, which raises when it is unreachable, and losing
    a report is a worse outcome than letting a runaway client through: sessions live
    in the database, so members stay signed in through a Redis outage and would hit
    this on the very page they were trying to report from.
    """
    key = f"feedback_rate:user:{request.user.pk}"
    try:
        cache.add(key, 0, timeout=RATE_WINDOW)
        return cache.incr(key) > RATE_LIMIT
    except Exception:
        logger.warning("Feedback rate limit unavailable; allowing", exc_info=True)
        return False


class FeedbackView(LoginRequiredMixin, View):
    """GET renders the standalone form; POST accepts submissions from it and the widget.

    Login required: beta access is granted through the `v3` flag, which is scoped to
    signed-in users, so every submitter has an account and an email we can reply to.
    """

    template_name = "v3/feedback_page.html"

    def dispatch(self, request, *args, **kwargs):
        """Honour the same flags as the widget, so switching the beta off closes the
        endpoint rather than only hiding the launcher.

        Runs before the login check, so a signed-out visitor gets a 404 instead of a
        login redirect advertising a route that is not open.
        """
        if not (
            flag_is_active(request, "v3") and flag_is_active(request, "beta_feedback")
        ):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def handle_no_permission(self):
        """A session that expired mid-form should say so, not fail opaquely."""
        if wants_json(self.request):
            return JsonResponse({"errors": {"__all__": SIGNED_OUT_MESSAGE}}, status=401)
        return super().handle_no_permission()

    def get(self, request):
        return self._render(request, FeedbackForm())

    def post(self, request):
        page_url = self._page_url(request)

        form = FeedbackForm(request.POST, request.FILES)
        if not form.is_valid():
            if wants_json(request):
                first_errors = {
                    field: errors[0] for field, errors in form.errors.items()
                }
                return JsonResponse({"errors": first_errors}, status=400)
            return self._render(request, form)

        # Checked after validation so the quota counts reports, not attempts: a member
        # fighting a rejected screenshot should not spend it.
        if is_rate_limited(request):
            if wants_json(request):
                return JsonResponse(
                    {"errors": {"__all__": THROTTLE_MESSAGE}}, status=429
                )
            messages.error(request, THROTTLE_MESSAGE)
            return redirect(self._safe_redirect_target(request, page_url))

        feedback = form.save(commit=False)
        feedback.user = request.user
        feedback.page_url = page_url
        feedback.source = self._source(request)
        feedback.user_agent = request.headers.get("user-agent", "")[
            :USER_AGENT_MAX_LENGTH
        ]

        context = page_context(request, page_url)
        feedback.url_name = context["url_name"]
        feedback.boost_version = context["boost_version"]
        # Server-derived keys come last: the client blob is allowlisted, but this way
        # a browser could never shadow them even if that allowlist grew.
        feedback.diagnostics = {
            "view_name": context["view_name"],
            **clean_client_diagnostics(request.POST.get("diagnostics", "")),
            **recent_server_errors(request.user),
        }
        feedback.save()

        if wants_json(request):
            return JsonResponse({"ok": True})
        messages.success(request, SUCCESS_MESSAGE)
        return redirect(self._safe_redirect_target(request, page_url))

    def _source(self, request):
        """Which form produced this submission, and whether JavaScript was running.

        The widget is the only client that sets the XHR header. Everything else is a
        plain page POST from the standalone form, where a populated diagnostics field
        is the only evidence that scripts ran — no JS means the field posts empty.
        """
        if wants_json(request):
            return Feedback.Source.WIDGET
        if request.POST.get("diagnostics", "").strip():
            return Feedback.Source.PAGE
        return Feedback.Source.PAGE_NO_JS

    def _render(self, request, form):
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "feedback_type_options": Feedback.Type.choices,
                "message_max_length": MESSAGE_MAX_LENGTH,
                "page_url": self._page_url(request),
            },
        )

    def _page_url(self, request):
        """Where the feedback came from, most authoritative source first.

        The hidden field wins on submit; `?from=` covers the no-JS launcher, whose
        Referer privacy tooling often strips; Referer is the last resort.

        Only the scheme is enforced, which is what makes the value safe to link from
        the admin. Hostnames are left alone so single-label internal hosts still work.
        Bad values are dropped rather than raised, so unusable metadata can never
        block a submission the user cannot see or correct.
        """
        candidates = (
            request.POST.get("page_url", ""),
            request.GET.get("from", ""),
            request.headers.get("referer", ""),
        )
        for candidate in candidates:
            candidate = candidate.strip()[:PAGE_URL_MAX_LENGTH]
            parts = urlsplit(candidate)
            if parts.scheme in ("http", "https") and parts.netloc:
                return candidate
        return ""

    def _safe_redirect_target(self, request, page_url):
        """page_url reaches us from the client, so only same-host values are followed."""
        if page_url and url_has_allowed_host_and_scheme(
            page_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return page_url
        return "/"
