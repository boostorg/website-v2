#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from django.contrib import admin
from .models import RenderedContent


@admin.register(RenderedContent)
class RenderedContentAdmin(admin.ModelAdmin):
    list_display = ("cache_key", "content_type")
    search_fields = ("cache_key",)
