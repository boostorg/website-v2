from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def can_edit(context, news_item, *args, **kwargs):
    request = context.get("request")
    return news_item.can_edit(request.user)
