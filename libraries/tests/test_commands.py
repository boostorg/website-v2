#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
import pytest

from django.contrib.auth import get_user_model
from django.core.management import call_command


User = get_user_model()


@pytest.mark.django_db
def test_update_authors_command(library):
    """Test update_authors Django management command."""
    library.data = {
        "authors": [
            "Jane Smith <jane -at- boost.com>",
            "Juan Rodrigo <juan -at- boost.com>",
        ]
    }
    library.save()
    call_command("update_authors")
    assert User.objects.filter(email="jane@boost.com").exists()
    assert User.objects.filter(email="juan@boost.com").exists()
    library.refresh_from_db()
    assert library.authors.count() == 2
    assert library.authors.filter(email="jane@boost.com").exists()
    assert library.authors.filter(email="juan@boost.com").exists()


@pytest.mark.django_db
def test_update_maintainers_command(library_version):
    """Test update_maintainers Django management command."""
    library_version.data = {
        "maintainers": [
            "Jane Smith <jane -at- boost.com>",
            "Juan Rodrigo <juan -at- boost.com>",
        ]
    }
    library_version.save()
    call_command("update_maintainers")
    assert User.objects.filter(email="jane@boost.com").exists()
    assert User.objects.filter(email="juan@boost.com").exists()
    library_version.refresh_from_db()
    assert library_version.maintainers.count() == 2
    assert library_version.maintainers.filter(email="jane@boost.com").exists()
    assert library_version.maintainers.filter(email="juan@boost.com").exists()
