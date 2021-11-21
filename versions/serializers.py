from rest_framework import serializers
from versions.models import Version


class VersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Version
        fields = ["id", "name", "checksum", "file", "release_date"]
