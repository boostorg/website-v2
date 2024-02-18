#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("libraries", "0016_libraryversion_data_alter_library_data"),
        ("libraries", "0016_remove_library_first_github_tag_date"),
    ]

    operations = []
