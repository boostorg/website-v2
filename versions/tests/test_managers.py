import pytest
from model_bakery import baker
from django.db.models import Q

from versions.models import Version, VersionFile


def test_active_manager(version):
    baker.make("versions.Version", name="Sample 1", active=False)
    baker.make("versions.Version", name="Sample 2", active=False)

    assert Version.objects.active().count() == 1


def test_most_recent_manager(version, inactive_version, old_version, beta_version):
    assert Version.objects.most_recent() == version


def test_most_recent_beta_manager(version, inactive_version, old_version, beta_version):
    assert Version.objects.most_recent_beta() == beta_version

    version.name = "1.0.beta"
    version.beta = True
    version.save()
    beta_version.name = "1.1.beta"
    beta_version.save()

    assert Version.objects.most_recent_beta() == beta_version

    version.name = "2.0.beta"
    version.save()
    assert Version.objects.most_recent_beta() == version


@pytest.mark.django_db
@pytest.mark.parametrize(
    "most_recent_name,most_recent_beta_name,should_show_beta",
    [
        # Beta is newer than newest version
        ("1.84.0", "1.85.0.beta1", True),
        # Beta is newer minor version than newest version
        ("1.84.0", "1.84.1.beta1", True),
        # Beta is for the newest version
        ("1.84.0", "1.84.0.beta1", False),
        # Beta is older than newest version
        ("1.84.0", "1.83.0.beta1", False),
        # There is no beta
        ("1.84.0", None, False),
    ],
)
def test_version_dropdown(
    most_recent_name, most_recent_beta_name, should_show_beta, version, beta_version
):
    """Test the version_dropdown manager method"""
    version.name = most_recent_name
    version.save()

    if most_recent_beta_name:
        beta_version.name = most_recent_beta_name
        beta_version.save()
        most_recent_beta = beta_version
    else:
        most_recent_beta = None

    queryset = Version.objects.version_dropdown()

    if should_show_beta:
        beta_queryset = Version.objects.active().filter(Q(name=most_recent_beta.name))
        expected = list(
            (
                Version.objects.active().filter(beta=False).order_by("-release_date")
                | beta_queryset
            ).order_by("-release_date")
        )
    else:
        expected = list(
            Version.objects.active().filter(beta=False).order_by("-release_date")
        )

    assert list(queryset) == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "version_name, beta, full_release, most_recent_name, most_recent_beta_name, should_be_included",  # noqa
    [
        # Version is the most recent, full release
        ("1.84.0", False, True, "1.84.0", "1.85.0.beta1", True),
        # Version is the most recent beta, not full release
        ("1.85.0.beta1", True, False, "1.84.0", "1.85.0.beta1", True),
        # Version is not the most recent, not full release
        ("1.83.0", False, False, "1.84.0", "1.85.0.beta1", False),
        # No beta, version is full release
        ("1.84.0", False, True, "1.84.0", None, True),
        # No beta, version is not full release
        ("develop", False, False, "1.84.0", None, False),
    ],
)
def test_version_dropdown_strict(
    version_name,
    beta,
    full_release,
    most_recent_name,
    most_recent_beta_name,
    should_be_included,
    version,
    beta_version,
):
    """Test the version_dropdown_strict method"""

    # Additional setup for most recent non-beta version
    most_recent_version = Version.objects.create(
        name=most_recent_name, beta=False, full_release=True
    )
    most_recent_version.save()

    # Setup version instance
    version.name = version_name
    version.beta = beta
    version.full_release = full_release
    version.save()

    if most_recent_beta_name:
        beta_version.name = most_recent_beta_name
        beta_version.beta = True
        beta_version.full_release = False
        beta_version.save()

    queryset = Version.objects.version_dropdown_strict()
    assert (version in queryset) == should_be_included


def test_active_file_manager(version, inactive_version):
    assert Version.objects.active().count() == 1
    assert VersionFile.objects.active().count() == 1
