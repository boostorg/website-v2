#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from core.context_processors import current_release


def test_current_release_context(
    version, beta_version, inactive_version, old_version, rf
):
    """Test the current_release context processor. Making the other versions
    ensures that the most_recent() method returns the correct version."""
    request = rf.get("/")
    context = current_release(request)
    assert "current_release" in context
    assert context["current_release"] == version
