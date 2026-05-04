from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def resolve_pagination(context, current=None, total=None, param=None):
    """Return a dict with current, total, and param resolved from context or explicit overrides.

    When used in an isolated/demo context, pass current/total/param explicitly.
    When used inside a Django ListView, they are read from page_obj and paginator.
    """
    page_obj = context.get("page_obj")
    paginator = context.get("paginator")
    return {
        "current": (
            current if current is not None else (page_obj.number if page_obj else 1)
        ),
        "total": (
            total if total is not None else (paginator.num_pages if paginator else 0)
        ),
        "param": param or "page",
    }


@register.simple_tag
def pagination_range(current_page, num_pages):
    """Compute the list of page items to display in a paginator.

    Returns a list where each element is either:
    - An integer (page number, clickable)
    - The string '...' (ellipsis, decorative)
    """
    if num_pages <= 1:
        return []

    window_start = max(2, current_page - 2)
    window_end = min(num_pages - 1, current_page + 2)

    items = [1]

    if window_start > 2:
        items.append("...")

    items.extend(range(window_start, window_end + 1))

    if window_end < num_pages - 1:
        items.append("...")

    items.append(num_pages)
    return items


@register.simple_tag(takes_context=True)
def page_url(context, page_number, page_param="page"):
    """Build a URL with the page param set, preserving all other query params."""
    request = context.get("request")
    if not request:
        return f"?{page_param}={page_number}"
    params = request.GET.copy()
    params[page_param] = page_number
    return f"?{params.urlencode()}"
