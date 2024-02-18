#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from django import template
from datetime import datetime

register = template.Library()


@register.filter
def years_since(value):
    today = datetime.today().date()
    delta = today - value
    return delta.days // 365
