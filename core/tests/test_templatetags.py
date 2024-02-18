#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from datetime import date, timedelta
from ..templatetags.date_filters import years_since


def test_years_since():
    # Test case for exactly 2 years
    assert years_since(date.today() - timedelta(days=2 * 365)) == 2

    # Test case for less than a year
    assert years_since(date.today() - timedelta(days=100)) == 0

    # Test case for 1.5 years (it should round down)
    assert years_since(date.today() - timedelta(days=int(1.5 * 365))) == 1

    # Test case for 2.9 years (it should still round down)
    assert years_since(date.today() - timedelta(days=int(2.9 * 365))) == 2
