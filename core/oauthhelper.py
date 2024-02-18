#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from django.conf import settings

from oauth2_provider.models import Application


def get_oauth_client():
    try:
        return Application.objects.get(name=settings.OAUTH_APP_NAME)
    except Application.DoesNotExist:
        return
