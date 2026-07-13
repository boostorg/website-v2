from django.http import Http404
from django.urls import URLPattern, URLResolver, get_resolver, reverse_lazy
from waffle import flag_is_active

from core.templatetags.custom_static import large_static


class V3Mixin:
    """Renders a v3 template when the 'v3' waffle flag is active.

    Hooks into dispatch() to short-circuit the normal view flow (e.g.
    MarkdownTemplateView's markdown rendering) when v3 is active.

    Subclasses declare:
        v3_template_name: str — template to render when v3 is active

    And override get_v3_context_data() to supply view-specific context.

    When the flag is off and no legacy template_name exists (i.e. a
    V3-only view), dispatch returns 404.
    """

    v3_template_name = None

    def dispatch(self, request, *args, **kwargs):
        if self.v3_template_name and flag_is_active(request, "v3"):
            self._v3_active = True
            return super().dispatch(request, *args, **kwargs)
        self._v3_active = False
        if not getattr(self, "template_name", None):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        if getattr(self, "_v3_active", False) and getattr(
            self, "_get_v3_initial", True
        ):
            self._get_v3_initial = False
            base_context = self.get_context_data(**kwargs)
            context = self.get_v3_context_data(**base_context)
        else:
            context = super().get_context_data(**kwargs)
        return context

    def serve(self, request, *args, **kwargs):
        if not flag_is_active(request, "v3"):
            raise Http404
        return super().serve(request, *args, **kwargs)

    def get_v3_context_data(self, **kwargs):
        """Override in subclasses to provide v3-specific context."""
        return {**kwargs}

    def get_template_names(self):
        if getattr(self, "_v3_active", False):
            return [self.v3_template_name]
        return super().get_template_names()


def iter_v3_views():
    """Yield (URLPattern, view_class) for every V3Mixin view in the URL conf."""

    def walk(patterns):
        for entry in patterns:
            if isinstance(entry, URLResolver):
                yield from walk(entry.url_patterns)
            elif isinstance(entry, URLPattern):
                callback = entry.callback
                view_class = None
                while callback is not None:
                    view_class = getattr(callback, "view_class", None)
                    if view_class is not None:
                        break
                    callback = getattr(callback, "__wrapped__", None)
                if view_class and issubclass(view_class, V3Mixin):
                    yield entry, view_class

    yield from walk(get_resolver().url_patterns)


class V3AuthContextMixin(V3Mixin):
    """Shared context for all V3 auth pages (signup, login, password reset, etc.)."""

    def dispatch(self, request, *args, **kwargs):
        if not flag_is_active(request, "v3"):
            if not getattr(self, "template_name", None):
                raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_v3_context_data(self, **kwargs):
        context = super().get_v3_context_data(**kwargs)
        context["page_title"] = getattr(self, "page_title", "Account")
        context["foreground_image_url"] = large_static(
            "img/v3/auth-page/auth-page-foreground.png"
        )
        context["background_image_url"] = large_static(
            "img/v3/auth-page/auth-page-background.png"
        )
        context["login_url"] = reverse_lazy("v3-login")
        context["signup_url"] = reverse_lazy("account_signup")
        context["password_reset_url"] = reverse_lazy("v3-password-reset")
        return context
