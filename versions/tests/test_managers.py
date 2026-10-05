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

    queryset = Version.objects.get_dropdown_versions()

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
        name=most_recent_name, beta=False, full_release=True, fully_imported=True
    )
    most_recent_version.save()

    # Setup version instance
    version.name = version_name
    version.beta = beta
    version.full_release = full_release
    version.fully_imported = True
    version.save()

    if most_recent_beta_name:
        beta_version.name = most_recent_beta_name
        beta_version.beta = True
        beta_version.full_release = False
        beta_version.fully_imported = True
        beta_version.save()

    queryset = Version.objects.get_dropdown_versions()
    assert (version in queryset) == should_be_included


def test_active_file_manager(version, inactive_version):
    assert Version.objects.active().count() == 1
    assert VersionFile.objects.active().count() == 1


def test_default_manager_filters_fully_imported(version, not_imported_version):
    """Test that the default manager only returns fully_imported=True objects."""
    # Default queryset should only include fully imported versions
    default_versions = Version.objects.all()
    assert version in default_versions
    assert not_imported_version not in default_versions

    # Count should reflect this
    assert default_versions.count() == 1


def test_with_partials_manager_method(version, not_imported_version):
    """Test that with_partials() returns all objects regardless of fully_imported status."""
    # with_partials should include all versions
    all_versions = Version.objects.with_partials().all()
    assert version in all_versions
    assert not_imported_version in all_versions

    # Should have more (or equal) count than default
    default_count = Version.objects.all().count()
    partials_count = all_versions.count()
    assert partials_count >= default_count


def test_with_partials_active_method():
    """Test that with_partials().active() works correctly."""
    from model_bakery import baker

    # Create test versions with different combinations
    active_imported = baker.make(
        "versions.Version", name="test-1.0.0", fully_imported=True, active=True
    )
    active_not_imported = baker.make(
        "versions.Version", name="test-2.0.0", fully_imported=False, active=True
    )
    inactive_imported = baker.make(
        "versions.Version", name="test-3.0.0", fully_imported=True, active=False
    )
    inactive_not_imported = baker.make(
        "versions.Version", name="test-4.0.0", fully_imported=False, active=False
    )

    # Default active() should only show active + fully_imported
    default_active = Version.objects.active()
    assert active_imported in default_active
    assert active_not_imported not in default_active
    assert inactive_imported not in default_active
    assert inactive_not_imported not in default_active

    # with_partials().active() should show both active versions regardless of fully_imported
    partials_active = Version.objects.with_partials().active()
    assert active_imported in partials_active
    assert active_not_imported in partials_active
    assert inactive_imported not in partials_active
    assert inactive_not_imported not in partials_active


def test_with_partials_can_be_chained():
    """Test that with_partials() returns a queryset that can be further filtered."""
    from model_bakery import baker

    # Create test versions
    fully_imported_active = baker.make(
        "versions.Version", name="test-1.0.0", fully_imported=True, active=True
    )
    not_fully_imported_active = baker.make(
        "versions.Version", name="test-2.0.0", fully_imported=False, active=True
    )
    not_fully_imported_inactive = baker.make(
        "versions.Version", name="test-3.0.0", fully_imported=False, active=False
    )

    # Using with_partials() and then filtering
    active_with_partials = Version.objects.with_partials().filter(active=True)
    assert fully_imported_active in active_with_partials
    assert not_fully_imported_active in active_with_partials
    assert not_fully_imported_inactive not in active_with_partials


def test_with_partials_ordering_and_filtering():
    """Test that with_partials() works with ordering and complex filtering."""
    from model_bakery import baker
    import datetime

    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    # Create test versions with different dates
    v1 = baker.make(
        "versions.Version",
        name="boost-1.0.0",
        fully_imported=True,
        active=True,
        release_date=yesterday,
    )
    v2 = baker.make(
        "versions.Version",
        name="boost-2.0.0",
        fully_imported=False,
        active=True,
        release_date=today,
    )
    v3 = baker.make(
        "versions.Version",
        name="boost-3.0.0",
        fully_imported=True,
        active=False,
        release_date=today,
    )

    # Test ordering with partials
    ordered_partials = Version.objects.with_partials().order_by("-release_date")
    ordered_list = list(ordered_partials)

    # Should include all versions and be properly ordered
    assert len(ordered_list) >= 3
    assert v2 in ordered_list
    assert v1 in ordered_list
    assert v3 in ordered_list

    # Test filtering with partials
    active_partials = Version.objects.with_partials().filter(active=True)
    assert v1 in active_partials
    assert v2 in active_partials
    assert v3 not in active_partials


@pytest.mark.django_db
def test_backward_compatibility_existing_methods(
    version, not_imported_version, beta_version
):
    """Test that existing manager methods work correctly with the new default filtering."""
    # Ensure test versions are set up correctly
    version.fully_imported = True
    version.save()
    beta_version.fully_imported = True
    beta_version.save()
    not_imported_version.fully_imported = False
    not_imported_version.save()

    # active() should work as before (only fully imported active versions)
    active_versions = Version.objects.active()
    assert version in active_versions
    assert not_imported_version not in active_versions

    # most_recent() should work as before
    most_recent = Version.objects.most_recent()
    assert most_recent is not None
    assert most_recent.fully_imported is True

    # most_recent_beta() should work as before
    most_recent_beta = Version.objects.most_recent_beta()
    assert most_recent_beta is not None
    assert most_recent_beta.fully_imported is True


@pytest.mark.django_db
def test_get_dropdown_versions_with_partials():
    """Test that get_dropdown_versions works correctly with the new default filtering."""
    from model_bakery import baker

    # Create versions with different fully_imported states
    full_release = baker.make(
        "versions.Version",
        name="boost-1.84.0",
        beta=False,
        full_release=True,
        fully_imported=True,
        active=True,
    )
    partial_release = baker.make(
        "versions.Version",
        name="boost-1.85.0",
        beta=False,
        full_release=True,
        fully_imported=False,
        active=True,
    )

    # get_dropdown_versions should only include fully imported versions by default
    dropdown_versions = Version.objects.get_dropdown_versions()
    assert full_release in dropdown_versions
    assert partial_release not in dropdown_versions

    # But with_partials should allow access to all versions for custom use cases
    all_versions_dropdown = (
        Version.objects.with_partials()
        .filter(active=True, beta=False, full_release=True)
        .order_by("-name")
    )
    assert full_release in all_versions_dropdown
    assert partial_release in all_versions_dropdown


@pytest.mark.django_db
def test_count_operations():
    """Test count operations with default filtering and with_partials."""
    from model_bakery import baker

    # Create test data
    baker.make("versions.Version", name="test-1", fully_imported=True, active=True)
    baker.make("versions.Version", name="test-2", fully_imported=True, active=False)
    baker.make("versions.Version", name="test-3", fully_imported=False, active=True)
    baker.make("versions.Version", name="test-4", fully_imported=False, active=False)

    # Count with default filtering
    default_count = Version.objects.count()

    # Count with partials
    partials_count = Version.objects.with_partials().count()

    # Count active with default filtering
    active_count = Version.objects.active().count()

    # Count active with partials
    active_partials_count = Version.objects.with_partials().active().count()

    # Assertions
    assert partials_count >= default_count  # partials should include more or equal
    assert default_count >= active_count  # default should include active
    assert (
        active_partials_count >= active_count
    )  # partials active should include more or equal
    assert (
        partials_count >= active_partials_count
    )  # all partials should be >= active partials
