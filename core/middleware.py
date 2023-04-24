from django.contrib.auth.decorators import login_required


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.process_request(request)
        if response:
            return response
        return self.get_response(request)

    def process_request(self, request):
        # Exclude certain views or URL patterns from requiring login
        if (
            request.path.startswith("/admin/")
            or request.path.startswith("/accounts/")
            or request.path.startswith("/invite/")
        ):
            return None

        # Apply the login_required decorator to all views
        view_func = self.get_response
        return login_required(view_func)(request)
