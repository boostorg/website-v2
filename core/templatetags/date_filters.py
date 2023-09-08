from django import template
from datetime import datetime

register = template.Library()


@register.filter
def years_since(value):
    today = datetime.today().date()
    delta = today - value
    return delta.days // 365
