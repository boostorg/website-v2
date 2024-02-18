#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
import pytest
from model_bakery import baker
from ..models import MailingListMessage


@pytest.fixture
def mailing_list_messages():
    return baker.make(MailingListMessage, _quantity=10)


@pytest.mark.django_db
def test_mailing_list_view(tp, mailing_list_messages):
    """Test the mailing list view."""
    url = tp.reverse("mailing-list")
    response = tp.get_check_200(url)
    assert len(response.context["object_list"]) == len(mailing_list_messages)
    assert set(response.context["object_list"]) == set(mailing_list_messages)


@pytest.mark.django_db
def test_mailing_list_detail_view(tp, mailing_list_messages):
    """Test the mailing list view."""
    url = tp.reverse("mailing-list-detail", pk=mailing_list_messages[0].pk)
    tp.get_check_200(url)
