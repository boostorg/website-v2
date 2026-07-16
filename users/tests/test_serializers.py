import pytest
from rest_framework import serializers

from ..serializers import CurrentUserSerializer


@pytest.mark.parametrize(
    "value",
    [
        {"github": "https://github.com/janedoe"},
        {"github": "https://github.com/janedoe", "website": "https://example.com"},
        {},
    ],
)
def test_validate_profile_links_accepts_valid_payload(value):
    assert CurrentUserSerializer().validate_profile_links(value) == value


def test_validate_profile_links_rejects_non_dict():
    with pytest.raises(serializers.ValidationError):
        CurrentUserSerializer().validate_profile_links(["not", "a", "dict"])


def test_validate_profile_links_rejects_unknown_key():
    with pytest.raises(serializers.ValidationError):
        CurrentUserSerializer().validate_profile_links(
            {"myspace": "https://example.com"}
        )


def test_validate_profile_links_rejects_non_string_value():
    with pytest.raises(serializers.ValidationError):
        CurrentUserSerializer().validate_profile_links({"github": 12345})


def test_validate_profile_links_rejects_value_over_200_chars():
    with pytest.raises(serializers.ValidationError):
        CurrentUserSerializer().validate_profile_links({"github": "a" * 201})


@pytest.mark.parametrize(
    "value",
    [
        {"github": "http://github.com/janedoe"},
        {"website": "http://example.com"},
        {"github": "not-a-url"},
        {"website": "ftp://example.com"},
    ],
)
def test_validate_profile_links_rejects_insecure_url(value):
    with pytest.raises(serializers.ValidationError):
        CurrentUserSerializer().validate_profile_links(value)


def test_validate_profile_links_allows_non_url_link_types_unchecked():
    value = {"email": "not-a-url"}
    assert CurrentUserSerializer().validate_profile_links(value) == value


@pytest.mark.parametrize(
    "value",
    [
        {"slack": "U012AB3CDE"},
        {"slack": "u012ab3cde"},
        {"slack": "https://cpplang.slack.com/team/U012AB3CDE"},
        {"slack": ""},
    ],
)
def test_validate_profile_links_accepts_valid_slack_link(value):
    assert CurrentUserSerializer().validate_profile_links(value) == value


@pytest.mark.parametrize(
    "value",
    [
        {"slack": "not-a-member-id"},
        {"slack": "https://cpplang.slack.com/messages/janedoe"},
        {"slack": "https://slack.com/app_redirect?team=T21Q22G66&channel=U012AB3CDE"},
    ],
)
def test_validate_profile_links_rejects_invalid_slack_link(value):
    with pytest.raises(serializers.ValidationError):
        CurrentUserSerializer().validate_profile_links(value)
