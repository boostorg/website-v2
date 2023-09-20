from versions.management.commands.import_versions import skip_tag


def test_skip_tag(version):
    # Assert that existing tag names are skipped if new is True
    assert skip_tag(version.name, True) is True

    # Assert that existing tag names are not skipped if new is False
    assert skip_tag(version.name, False) is False

    # Assert that if it's on the exclusion list, it's skipped
    assert skip_tag("boost-beta-1.0") is True

    # Assert that if the version is lower that the min, it's skipped
    assert skip_tag("boost-0.9.0") is True

    # Assert a random tag name is not skipped
    assert skip_tag("sample") is False
