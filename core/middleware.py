from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden

_PATTERN_LIBRARY_PREFIX = "/pattern-library/"


class PatternLibraryStaffMiddleware:
    """Restrict the /pattern-library/ endpoint to staff users only.

    django-pattern-library is a development tool that exposes raw template
    rendering. This middleware ensures it requires staff auth even when the
    endpoint is enabled (ENABLE_PATTERN_LIBRARY=True), so it can never be
    accessed by unauthenticated or non-staff users.

    The check is skipped when DEBUG is on: Storybook's dev proxy
    (.storybook/middleware.js) renders components server-side and never
    carries a browser session, so it would otherwise always be treated as
    anonymous. ENABLE_PATTERN_LIBRARY defaults to True in every environment
    now (Storybook ships everywhere, including production), so this staff
    check is the only thing gating the endpoint - any DEBUG=False
    environment always enforces it.

    Must appear in MIDDLEWARE after AuthenticationMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info.startswith(_PATTERN_LIBRARY_PREFIX) and not settings.DEBUG:
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not request.user.is_staff:
                return HttpResponseForbidden("Staff access required.")
        return self.get_response(request)
