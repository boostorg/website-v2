import pytest
from django.urls import reverse
from model_bakery import baker
from ..models import MailingListMessage


@pytest.fixture
def mailing_list_messages():
    return baker.make(MailingListMessage, _quantity=10)


@pytest.mark.django_db
def test_mailing_list_view(logged_in_tp, mailing_list_messages):
    """Test the mailing list view."""
    url = logged_in_tp.reverse("mailing-list")
    response = logged_in_tp.get_check_200(url)
    assert len(response.context["object_list"]) == len(mailing_list_messages)
    assert set(response.context["object_list"]) == set(mailing_list_messages)


@pytest.mark.django_db
def test_mailing_list_detail_view(logged_in_tp, mailing_list_messages):
    """Test the mailing list view."""
    url = logged_in_tp.reverse("mailing-list-detail", pk=mailing_list_messages[0].pk)
    response = logged_in_tp.get_check_200(url)
