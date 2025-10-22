import requests
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import CreateView

from core.views import logger
from marketing.forms import CapturedEmailForm
from marketing.models import CapturedEmail


@method_decorator(never_cache, name="dispatch")
class PlausibleRedirectView(View):
    """Handles QR code and social media urls, sending them to Plausible, then redirecting to the desired url.

    QR code urls are formatted /qrc/<campaign_identifier>/desired/path/to/content/, and will
    result in a redirect to /desired/path/to/content/.

    Social media urls are formatted /bsm/<campaign_identifier>/desired/path/to/content/, and will
    result in a redirect to /desired/path/to/content/.

    E.g. https://www.boost.org/qrc/pv-01/library/latest/beast/ will send this full url to Plausible,
    then redirect to https://www.boost.org/library/latest/beast/
    """

    def get(self, request: HttpRequest, campaign_identifier: str, main_path: str = ""):
        absolute_url = request.build_absolute_uri(request.path)
        referrer = request.headers.get("referer", "")
        user_agent = request.headers.get("user-agent", "")

        plausible_payload = {
            "name": "pageview",
            "domain": "qrc.boost.org",
            "url": absolute_url,
            "referrer": referrer,
        }

        headers = {"Content-Type": "application/json", "User-Agent": user_agent}

        client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        client_ip = client_ip or request.META.get("REMOTE_ADDR")

        if client_ip:
            headers["X-Forwarded-For"] = client_ip

        try:
            requests.post(
                "https://plausible.io/api/event",
                json=plausible_payload,
                headers=headers,
                timeout=2.0,
            )
        except Exception as e:
            # Don’t interrupt the redirect - just log it
            logger.error(f"Plausible event post failed: {e}")

        # Now that we've sent the request url to plausible, we can redirect to the main_path
        # Preserve the original querystring, if any.
        # Example: /qrc/3/library/latest/algorithm/?x=1  ->  /library/latest/algorithm/?x=1
        # `main_path` is everything after qrc/<campaign>/ thanks to <path:main_path>.
        redirect_path = "/" + main_path if main_path else "/"
        qs = request.META.get("QUERY_STRING")
        if qs:
            redirect_path = f"{redirect_path}?{qs}"

        request.session["original_referrer"] = referrer or campaign_identifier

        return HttpResponseRedirect(redirect_path)


class WhitePaperView(SuccessMessageMixin, CreateView):
    """Email capture and whitepaper view."""

    model = CapturedEmail
    form_class = CapturedEmailForm
    success_message = "Thanks! We'll be in touch."
    referrer: str

    def dispatch(self, request, *args, **kwargs):
        """Store self.referrer for use in form submission."""
        # If this view originated from PlausibleRedirectView, we should have original_referrer in the session
        if original_referrer := self.request.session.get("original_referrer", ""):
            self.referrer = original_referrer
        else:
            self.referrer = self.request.headers.get("referer", "")
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        category = self.kwargs["category"]
        slug = self.kwargs["slug"]
        return [f"marketing/whitepapers/{category}/{slug}.html"]

    def form_valid(self, form):
        form.instance.referrer = self.referrer
        form.instance.page_slug = f"{self.kwargs['category']}/{self.kwargs['slug']}"
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("whitepaper", kwargs=self.kwargs)
