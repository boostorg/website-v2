import datetime
import pytest
from django.test import RequestFactory
from model_bakery import baker
from libraries.mixins import VersionAlertMixin
from libraries.views import LibraryListBase


class MockView(LibraryListBase, VersionAlertMixin):
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


def _alert_message(selected, current, url="/releases/latest/"):
    return VersionAlertMixin().get_version_alert_message(
        {
            "selected_version": selected,
            "current_version": current,
            "version_alert_url": url,
        }
    )


def test_version_alert_message_none_when_inputs_missing():
    from versions.models import Version

    assert VersionAlertMixin().get_version_alert_message({}) is None
    assert _alert_message(Version(name="boost-1.90.0"), None) is None


def test_version_alert_message_sticky_latest():
    from versions.models import Version

    current = Version(name="boost-1.90.0", full_release=True)
    msg = _alert_message(current, current)
    assert "you will continue to view" in msg
    assert 'href="/releases/latest/"' in msg


def test_version_alert_message_beta():
    from versions.models import Version

    current = Version(name="boost-1.90.0", full_release=True)
    selected = Version(name="boost-1.91.0-beta", beta=True, full_release=False)
    msg = _alert_message(selected, current)
    assert "beta version of Boost" in msg
    assert "current version" in msg


def test_version_alert_message_older_release():
    from versions.models import Version

    current = Version(name="boost-1.90.0", full_release=True)
    selected = Version(
        name="boost-1.70.0",
        full_release=True,
        release_date=datetime.date(2018, 1, 1),
    )
    msg = _alert_message(selected, current)
    assert "older version of Boost" in msg
    assert "2018" in msg


def test_version_alert_message_dev_branch():
    from versions.models import Version

    current = Version(name="boost-1.90.0", full_release=True)
    selected = Version(name="develop", beta=False, full_release=False)
    msg = _alert_message(selected, current)
    assert "under active development" in msg
    assert "develop" in msg
