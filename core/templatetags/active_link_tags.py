from django import template
from django.urls import NoReverseMatch, reverse
from django.utils.encoding import escape_uri_path

register = template.Library()


@register.simple_tag(takes_context=True)
def active_link(
    context, viewnames, css_class=None, inactive_class="", strict=None, *args, **kwargs
):
    """
    Renders the given CSS class if the request path matches the path of the view.
    :param context: The context where the tag was called. Used to access the request object.
    :param viewnames: The name of the view or views separated by || (include namespaces if any).
    :param css_class: The CSS classes to render.
    :param inactive_class: The CSS classes to render if the views is not active.
    :param strict: If True, the tag will perform an exact match with the request path.
    :return:
    """
    request = context.get("request")
    if request is None:
        # Can't work without the request object.
        return ""
    active = False
    views = viewnames.split("||")

    for viewname in views:
        try:
            path = reverse(viewname.strip(), args=args, kwargs=kwargs)
        except NoReverseMatch:
            continue
        request_path = escape_uri_path(request.path)
        if strict:
            active = request_path == path
        else:
            active = request_path.find(path) == 0
        if active:
            break

    if active:
        return css_class

    return inactive_class
