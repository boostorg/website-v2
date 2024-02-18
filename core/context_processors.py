#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from versions.models import Version


def current_release(request):
    """Custom context processor that adds the current release to the context"""
    current_release = Version.objects.most_recent()
    return {"current_release": current_release}
