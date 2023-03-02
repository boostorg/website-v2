import pytest

from ..tasks import UserMissingGithubUsername, update_user_github_photo


def test_update_user_github_photo_user_not_found(db):
    with pytest.raises(Exception):
        update_user_github_photo(9999)


def test_update_user_github_photo_no_gh_username(user):
    user.github_username = ""
    user.save()
    with pytest.raises(UserMissingGithubUsername):
        update_user_github_photo(user.pk)
