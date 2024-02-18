#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def can_edit(context, news_item, *args, **kwargs):
    request = context.get("request")
    return news_item.can_edit(request.user)
