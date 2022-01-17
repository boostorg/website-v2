from django.core import files
from rest_framework import serializers
from versions.models import Version, VersionFile


class VersionFileSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()
    class Meta:
        model = VersionFile
        fields = ["id", "checksum", "operating_system", "filename", "url", "file"]
    
    def get_url(self, obj):
        request = self.context.get('request')
        file_url = obj.file.url
        return request.build_absolute_uri(file_url)
    
    def get_filename(self, obj):
        return obj.file.name



class VersionSerializer(serializers.ModelSerializer):
    files = VersionFileSerializer(many=True, read_only=True)
    class Meta:
        model = Version
        fields = ["id", "name", "files", "release_date"]
    
    # def create(self, validated_data):
    #     files = validated_data.pop('files')
    #     version = Version.objects.create(**validated_data)
    #     for file in files:
    #         version_file = VersionFile.objects.create(file=file.get("file"), operating_system=file.get("operating_system"))
    #         version.files.add(version_file)
    #     return version

