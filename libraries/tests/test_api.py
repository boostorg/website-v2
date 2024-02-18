#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
def test_library_search(library, tp):
    """
    GET /api/v1/libraries/?q=
    A library containing the querystring is returned
    """
    library = library
    res = tp.get(f"/api/v1/libraries/?q={library.name[:3]}")
    tp.response_200(res)
    assert len(res.context["libraries"]) == 1
