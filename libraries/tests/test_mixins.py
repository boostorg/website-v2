import datetime
import pytest
from django.test import RequestFactory
from model_bakery import baker
from libraries.mixins import VersionAlertMixin
from libraries.views import LibraryList


class MockView(LibraryList, VersionAlertMixin):
    pass


@pytest.mark.skip("TODO -- Test fails because we introduced beta releases")
@pytest.mark.django_db
def test_version_alert_mixin(version):
    latest_version = version
    old_version = baker.make("versions.Version", release_date=datetime.date(2000, 1, 1))

    # instantiate the mock view
    view = MockView()

    # create a mock request with no GET parameters
    request = RequestFactory().get("/")
    view.request = request

    # call get_context_data and check the context
    view.object_list = view.get_queryset()
    context = view.get_context_data()
    assert context["version"] == latest_version
    assert context["latest_version"] == latest_version
    assert not context["version_alert"]

    # create a mock request with a GET parameter for an old version
    request = RequestFactory().get(f"/?version={old_version.slug}")
    view.request = request

    # call get_context_data and check the context
    view.object_list = view.get_queryset()
    context = view.get_context_data()
    assert context["version"] == old_version
    assert context["latest_version"] == latest_version
    assert context["version_alert"]
