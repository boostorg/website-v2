from django.http import Http404
from django.urls import URLPattern, URLResolver, get_resolver
from waffle import flag_is_active


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
            return self.render_v3_response()
        self._v3_active = False
        if not getattr(self, "template_name", None):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_v3_context_data(self, **kwargs):
        """Override in subclasses to provide v3-specific context."""
        return {}

    def render_v3_response(self):
        """Render the v3 template through Django's standard TemplateView pipeline."""
        context = self.get_context_data(**self.get_v3_context_data())
        return self.render_to_response(context)

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
