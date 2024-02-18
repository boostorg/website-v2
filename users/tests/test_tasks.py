#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
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
