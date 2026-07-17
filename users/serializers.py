import re
import os
import uuid
from urllib.parse import urlparse

from django.conf import settings
from rest_framework import serializers

from core.validators import downscale_image_file_size_validator
from news.utils import downsize_uploaded_image

from .forms import SLACK_PROFILE_URL_PREFIX, V3ProfileLinkChoices
from .models import User

SECURE_LINK_TYPES = {V3ProfileLinkChoices.GITHUB, V3ProfileLinkChoices.WEBSITE}
SLACK_MEMBER_ID_PATTERN = re.compile(r"^[A-Z0-9]{9,11}$", re.IGNORECASE)


def is_secure_url(value):
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme == "https" and bool(parsed.hostname)


def is_url(value):
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return bool(parsed.scheme) and bool(parsed.netloc)


def is_valid_slack_link(value):
    # A pasted link must be our canonical CPPLang Slack profile URL; anything
    # else that isn't a URL is checked against the Member ID shape.
    if is_url(value):
        return value.lower().startswith(SLACK_PROFILE_URL_PREFIX.lower())
    return bool(SLACK_MEMBER_ID_PATTERN.match(value))


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
    profile_image = serializers.ImageField(
        validators=[downscale_image_file_size_validator]
    )

    def validate_profile_links(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "profile_links must be an object keyed by link type."
            )
        allowed_types = set(V3ProfileLinkChoices.values)
        if not set(value).issubset(allowed_types):
            raise serializers.ValidationError("Unknown profile link type.")
        if any(not isinstance(v, str) or len(v) > 200 for v in value.values()):
            raise serializers.ValidationError(
                "Each link must be a string of 200 characters or fewer."
            )
        # Keyed by link type so the frontend can route each message to its
        # own field instead of a single banner next to the Save button.
        field_errors = {}
        for link_type in SECURE_LINK_TYPES:
            link_value = value.get(link_type)
            if link_value and not is_secure_url(link_value):
                field_errors[link_type] = "Please add a secure link."
        slack_value = value.get(V3ProfileLinkChoices.SLACK)
        if slack_value and not is_valid_slack_link(slack_value):
            field_errors[V3ProfileLinkChoices.SLACK] = (
                "Please enter a valid CPPLang profile URL or Member ID."
            )
        if field_errors:
            raise serializers.ValidationError(field_errors)
        return value

    def validate_profile_image(self, value):
        file_name = value.name
        root, ext = os.path.splitext(file_name)
        value.name = str(uuid.uuid4()) + ext
        if value.size > settings.DOWNSCALE_IMAGE_THRESHOLD:
            return downsize_uploaded_image(value)
        return value

    def validate(self, data):
        user = self.instance
        if not user.can_update_image and "profile_image" in data:
            raise serializers.ValidationError(
                "You do not have permission to update your profile photo."
            )

        return super().validate(data)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "display_name",
            "profile_image",
            "date_joined",
            "data",
            "profile_links",
        )
        read_only_fields = (
            "id",
            "email",  # Users shouldn't change their email this way
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
