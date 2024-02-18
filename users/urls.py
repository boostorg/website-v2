#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from rest_framework.routers import DefaultRouter

from django.urls import path

from . import api


router = DefaultRouter()
router.register(r"users", api.UserViewSet, basename="user")

urlpatterns = [
    path("users/me/", api.CurrentUserView.as_view(), name="current-user"),
]

urlpatterns += router.urls
