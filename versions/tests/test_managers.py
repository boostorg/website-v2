from model_bakery import baker

from versions.models import Version


def test_active_manager(version):
    v2 = baker.make("versions.Version", active=False)
    v3 = baker.make("versions.Version", active=False)

    assert Version.objects.active().count() == 1
