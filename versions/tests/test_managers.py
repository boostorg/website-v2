from model_bakery import baker

from versions.models import Version, VersionFile


def test_active_manager(version):
    baker.make("versions.Version", name="Sample 1", active=False)
    baker.make("versions.Version", name="Sample 2", active=False)

    assert Version.objects.active().count() == 1


def test_most_recent_manager(version, inactive_version, old_version):
    assert Version.objects.most_recent() == version


def test_active_file_manager(version, inactive_version):
    assert Version.objects.active().count() == 1
    assert VersionFile.objects.active().count() == 1
