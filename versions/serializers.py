#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
from rest_framework import serializers

from versions.models import Version, VersionFile


class VersionFileSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()

    class Meta:
        model = VersionFile
        fields = ["id", "filename", "checksum", "operating_system", "url"]

    def get_url(self, obj):
        request = self.context.get("request")
        file_url = obj.file.url
        return request.build_absolute_uri(file_url)

    def get_filename(self, obj):
        return obj.file.name


class VersionSerializer(serializers.ModelSerializer):
    files = VersionFileSerializer(many=True, read_only=True)

    class Meta:
        model = Version
        fields = ["id", "name", "release_date", "description", "active", "files"]
