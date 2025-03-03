from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """
    Default serializer that doesn't expose too much possibly sensitive
    information
    """

    class Meta:
        model = User
        fields = (
            "id",
            "display_name",
        )
        read_only_fields = (
            "id",
            "display_name",
        )


class CurrentUserSerializer(serializers.ModelSerializer):
    """
    User serializer for the currently logged in user
    """

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "display_name",
            "image",
            "date_joined",
            "data",
        )
        read_only_fields = (
            "id",
            "email",  # Users shouldn't change their email this way
            "image",
            "date_joined",
        )


class FullUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "display_name",
            "is_staff",
            "is_active",
            "is_superuser",
            "date_joined",
            "data",
        )
        read_only_fields = ("id",)
