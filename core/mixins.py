from waffle import flag_is_active


class V3Mixin:
    """Renders a v3 template when the 'v3' waffle flag is active.

    Hooks into dispatch() to short-circuit the normal view flow (e.g.
    MarkdownTemplateView's markdown rendering) when v3 is active.

    Subclasses declare:
        v3_template_name: str — template to render when v3 is active

    And override get_v3_context_data() to supply view-specific context.
    """

    v3_template_name = None

    def dispatch(self, request, *args, **kwargs):
        if self.v3_template_name and flag_is_active(request, "v3"):
            self._v3_active = True
            return self.render_v3_response()
        self._v3_active = False
        return super().dispatch(request, *args, **kwargs)

    def get_v3_context_data(self, **kwargs):
        """Override in subclasses to provide v3-specific context."""
        return {}

    def render_v3_response(self):
        """Render the v3 template through Django's standard TemplateView pipeline."""
        context = self.get_context_data(**self.get_v3_context_data())
        print(context["library_filter_fields"])
        return self.render_to_response(context)

    def get_template_names(self):
        if getattr(self, "_v3_active", False):
            return [self.v3_template_name]
        return super().get_template_names()
