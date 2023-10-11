from model_bakery import baker

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


def test_active_file_manager(version, inactive_version):
    assert Version.objects.active().count() == 1
    assert VersionFile.objects.active().count() == 1
