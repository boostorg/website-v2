import pytest
from django.urls import reverse
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
