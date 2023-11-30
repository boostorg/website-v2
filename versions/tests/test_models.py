import datetime
import pytest

from model_bakery import baker


def test_version_creation(version):
    today = datetime.date.today()
    assert version.release_date < today


def test_version_slug(version):
    version.name = "New Name"
    version.slug = None
    version.save()
    version.refresh_from_db()
    assert version.slug is not None
    assert version.slug == "new-name"


@pytest.mark.parametrize(
    "slug, expected_slug",
    [
        ("boost-1.71.0", "boost_1_71_0"),
        ("boost-1-71-0", "boost_1_71_0"),
        ("develop", "develop"),
    ],
)
def test_boost_url_slug(slug, expected_slug):
    version = baker.make("versions.Version", name=slug)
    assert version.boost_url_slug == expected_slug


def test_version_get_slug(db):
    version = baker.prepare("versions.Version", name="Sample Library")
    assert version.get_slug() == "sample-library"


def test_version_display_name(version):
    version.name = "boost-1.81.0"
    version.save()
    assert version.display_name == "1.81.0"

    version.name = "1.79.0"
    version.save()
    del version.display_name
    assert version.display_name == "1.79.0"


def test_version_documentation_url(version):
    version.slug = "boost-1.81.0"
    version.save()
    assert version.documentation_url == "/doc/libs/boost_1_81_0/index.html"


@pytest.mark.parametrize(
    "name,expected_cleaned_parts",
    [
        ("boost-1.80.0", ["1", "80", "0"]),
        ("boost-1.79.0.beta1", ["1", "79", "0"]),
        ("Boost 1.80.9.beta", ["1", "80", "9"]),
        ("Version 1.82.0.beta1", ["1", "82", "0"]),
    ],
)
def test_cleaned_version_parts(name, expected_cleaned_parts, version):
    """Test the cleaned_version_parts property method"""
    version.name = name
    version.save()

    assert version.cleaned_version_parts == expected_cleaned_parts


def test_release_notes_cache_key(version):
    """Test the release_notes_cache_key property method"""
    expected = f"release_notes_{version.slug}"
    assert version.release_notes_cache_key == expected


def test_version_file_creation(full_version_one):
    assert full_version_one.downloads.count() == 3


@pytest.mark.parametrize(
    "slug, expected",
    [
        ("boost-1.75.0", "1_75_0"),
        ("develop", "develop"),
        ("boost_2.0.1", "2_0_1"),
    ],
)
def test_stripped_boost_url_slug(slug, expected, version):
    version.slug = slug
    version.save()
    version.refresh_from_db()
    assert version.stripped_boost_url_slug == expected
