#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from django.forms import Form, ModelChoiceField, ModelForm

from versions.models import Version
from .models import Library


class LibraryForm(ModelForm):
    class Meta:
        model = Library
        fields = ["categories"]


class VersionSelectionForm(Form):
    version = ModelChoiceField(
        queryset=Version.objects.all(),
        label="Select a version",
        empty_label="Choose a version...",
    )
