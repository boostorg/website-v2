import requests
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import CreateView

from core.views import logger
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
        referrer = request.META.get("HTTP_REFERER", "")
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        plausible_payload = {
            "name": "pageview",
            "domain": "qrc.boost.org",
            "url": absolute_url,
            "referrer": referrer,
        }

        headers = {"Content-Type": "application/json", "User-Agent": user_agent}

        client_ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
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
    fields = ["email"]
    success_message = "Thanks! We'll be in touch."

    def get_template_names(self):
        return [f"marketing/whitepapers/{self.kwargs.get('slug')}.html"]

    def form_valid(self, form):
        form.instance.page_slug = self.kwargs["slug"]
        # If this view originated from PlausibleRedirectView, we should have original_referrer in the session
        if original_referrer := self.request.session.pop("original_referrer", ""):
            form.instance.referrer = original_referrer
        else:
            form.instance.referrer = self.request.META.get("HTTP_REFERER", "")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("whitepaper", kwargs=self.kwargs)
