from django import template
from django.core.paginator import Paginator

register = template.Library()


@register.simple_tag(takes_context=True)
def resolve_pagination(context, current=None, total=None):
    """Return a Django Page object resolved from context or explicit overrides.

    In a ListView context, returns page_obj directly.
    In isolated/demo usage, creates a real Paginator from the given values.
    """
    page_obj = context.get("page_obj")

    if isinstance(current, int) and isinstance(total, int):
        paginator = Paginator(range(1, total + 1), 1)
        return paginator.page(max(1, min(current, paginator.num_pages)))

    if page_obj is not None:
        return page_obj

    return Paginator([], 1).page(1)


@register.simple_tag
def pagination_range(page, window=2):
    """Return an elided page range for the given Page object.

    Always uses an ellipsis for any gap (even a single page), unlike Django's
    built-in get_elided_page_range which fills single-page gaps with the page
    number. Each element is either an integer or '…'.
    """
    num_pages = page.paginator.num_pages
    current = page.number

    if num_pages <= 1:
        return list(range(1, num_pages + 1))

    window_start = max(2, current - window)
    window_end = min(num_pages - 1, current + window)

    items = [1]
    if window_start > 2:
        items.append("…")
    items.extend(range(window_start, window_end + 1))
    if window_end < num_pages - 1:
        items.append("…")
    items.append(num_pages)
    return items


@register.simple_tag(takes_context=True)
def page_url(context, page_number, page_param="page", anchor=""):
    """Build a URL with the page param set, preserving all other query params.

    If anchor is provided, appends #anchor so the browser scrolls to that element.
    """
    page_param = page_param or "page"
    request = context.get("request")
    if not request:
        url = f"?{page_param}={page_number}"
    else:
        params = request.GET.copy()
        params[page_param] = page_number
        url = f"?{params.urlencode()}"
    return f"{url}#{anchor}" if anchor else url
