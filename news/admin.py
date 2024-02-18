#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from django.contrib import admin

from .models import NEWS_MODELS


class EntryAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "created_at", "approved_at", "publish_at"]
    readonly_fields = ["modified_at", "is_approved", "is_published"]
    prepopulated_fields = {"slug": ["title"]}


for news_model in NEWS_MODELS:
    admin.site.register(news_model, EntryAdmin)
