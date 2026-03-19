from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden

_PATTERN_LIBRARY_PREFIX = "/pattern-library/"


class PatternLibraryStaffMiddleware:
    """Restrict the /pattern-library/ endpoint to staff users only.

    django-pattern-library is a development tool that exposes raw template
    rendering. This middleware ensures it requires staff auth even when the
    endpoint is enabled (ENABLE_PATTERN_LIBRARY=True), so it can never be
    accessed by unauthenticated or non-staff users.

    Must appear in MIDDLEWARE after AuthenticationMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(_PATTERN_LIBRARY_PREFIX):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not request.user.is_staff:
                return HttpResponseForbidden("Staff access required.")
        return self.get_response(request)
