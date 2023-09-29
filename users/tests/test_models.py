import pytest

from django.contrib.auth import get_user_model
from pytest_django.asserts import assertQuerySetEqual

from ..models import Preferences

User = get_user_model()


def test_regular_user(user):
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False


def test_staff_user(staff_user):
    assert staff_user.is_active is True
    assert staff_user.is_staff is True
    assert staff_user.is_superuser is False


def test_super_user(super_user):
    assert super_user.is_active is True
    assert super_user.is_staff is True
    assert super_user.is_superuser is True


def test_get_display_name(user):
    # Test case 1: Display name is set
    user.display_name = "Display Name"
    user.save()
    assert user.get_display_name == "Display Name"

    # Test case 2: First and last name are set, no display name
    user.display_name = ""
    user.save()
    assert user.get_display_name == f"{user.first_name} {user.last_name}"

    # Test case 3: Only first name is set, no display name
    user.first_name = "First"
    user.last_name = ""
    user.save()
    assert user.get_display_name == "First"

    # Test case 4: Only last name is set, no display name
    user.first_name = ""
    user.last_name = "Last"
    user.save()
    assert user.get_display_name == "Last"


@pytest.mark.skip("Add this test when I have the patience for mocks")
def test_user_save_image_from_github(user):
    """
    Test `User.save_image_from_github(avatar_url)`
    See test_signals -- you will need to do something similar here, but
    dealing with a File object might make it trickier.
    """
    pass


def test_claim(user):
    user.claimed = False
    user.save()
    user.refresh_from_db()

    assert not user.claimed
    user.claim()
    user.refresh_from_db()
    assert user.claimed


def test_find_contributor_by_email(user):
    found_user = User.objects.find_contributor(email=user.email)
    assert found_user == user


def test_find_contributor_by_email_not_found():
    non_existent_email = "nonexistent@email.com"
    found_user = User.objects.find_contributor(email=non_existent_email)
    assert found_user is None


def test_find_contributor_not_author_or_maintainer(user: User):
    found_user = User.objects.find_contributor(
        first_name=user.first_name, last_name=user.last_name
    )
    assert found_user is None


def test_find_contributor_by_first_and_last_name_not_found():
    non_existent_first_name = "Nonexistent"
    non_existent_last_name = "User"
    found_user = User.objects.find_contributor(
        first_name=non_existent_first_name, last_name=non_existent_last_name
    )
    assert found_user is None


def test_find_contributor_by_first_and_last_name_multiple_results(user, staff_user):
    staff_user.first_name = user.first_name
    staff_user.last_name = user.last_name
    staff_user.save()

    found_user = User.objects.find_contributor(
        first_name=user.first_name, last_name=user.last_name
    )
    assert found_user is None


def test_find_contributor_no_args():
    found_user = User.objects.find_contributor()
    assert found_user is None


def test_find_contributor_is_author(user, library):
    library.authors.add(user)
    library.save()

    found_user = User.objects.find_contributor(
        first_name=user.first_name, last_name=user.last_name
    )
    assert found_user == user


def test_find_contributor_is_maintainer(user, library_version):
    library_version.maintainers.add(user)
    library_version.save()

    found_user = User.objects.find_contributor(
        first_name=user.first_name, last_name=user.last_name
    )
    assert found_user == user


def test_preferences(user):
    assert Preferences.objects.get(user=user) == user.preferences
    assert user.preferences.notifications == {
        "own-news-approved": [Preferences.NEWS_TYPES_WILDCARD],
        "others-news-posted": [],
        "others-news-needs-moderation": [Preferences.NEWS_TYPES_WILDCARD],
    }


@pytest.mark.parametrize(
    "notification_type, default",
    [
        ("own-news-approved", [Preferences.NEWS_TYPES_WILDCARD]),
        ("others-news-posted", []),
        ("others-news-needs-moderation", [Preferences.NEWS_TYPES_WILDCARD]),
    ],
)
def test_preferences_set_value(user, notification_type, default):
    attr_name = f"allow_notification_{notification_type.replace('-', '_')}"

    # default value
    assert user.preferences.notifications[notification_type] == default
    assert getattr(user.preferences, attr_name) == (
        Preferences.ALL_NEWS_TYPES
        if Preferences.NEWS_TYPES_WILDCARD in default
        else default
    )

    # set empty list
    setattr(user.preferences, attr_name, [])
    assert getattr(user.preferences, attr_name) == []
    assert user.preferences.notifications[notification_type] == []

    # set a few values
    setattr(user.preferences, attr_name, ["link", "blogpost"])
    assert getattr(user.preferences, attr_name) == ["blogpost", "link"]
    assert user.preferences.notifications[notification_type] == ["blogpost", "link"]

    # set all values
    setattr(user.preferences, attr_name, list(reversed(Preferences.ALL_NEWS_TYPES)))
    assert getattr(user.preferences, attr_name) == Preferences.ALL_NEWS_TYPES
    assert user.preferences.notifications[notification_type] == [
        Preferences.NEWS_TYPES_WILDCARD
    ]


@pytest.mark.parametrize("news_type", Preferences.ALL_NEWS_TYPES)
def test_manager_preferences_shortcuts(tp, make_user, news_type):
    # user does not allow notifications
    make_user(email="u1@example.com", allow_notification_others_news_posted=[])
    # allows nofitications for all news type
    u2 = make_user(
        email="u2@example.com",
        allow_notification_others_news_posted=[Preferences.NEWS_TYPES_WILDCARD],
    )
    # allows only for the same type as entry
    u3 = make_user(
        email="u3@example.com", allow_notification_others_news_posted=[news_type]
    )
    # allows for any other type except entry's
    make_user(
        email="u4@example.com",
        allow_notification_others_news_posted=[
            t for t in Preferences.ALL_NEWS_TYPES if t != news_type
        ],
    )

    with tp.assertNumQueriesLessThan(2, verbose=True):
        result = User.objects.allow_notification_others_news_posted(news_type)

    assertQuerySetEqual(result, [u2, u3], ordered=False)
