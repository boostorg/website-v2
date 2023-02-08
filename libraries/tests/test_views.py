import pytest

from model_bakery import baker


def test_library_list(version, tp):
    """GET /libraries/"""
    res = tp.get("libraries")
    tp.response_200(res)


@pytest.mark.xfail(
    reason="Need to change how the category filtering works to accommodate versions"
)
def test_library_list_select_category(library, category, tp):
    """POST /libraries/ to submit a category redirects to the libraries-by-category page"""
    res = tp.post("libraries", data={"categories": category.pk})
    tp.response_302(res)


def test_library_list_by_category(library_version, category, tp):
    """GET /libraries-by-category/{category_slug}/"""
    library = library_version.library
    version = library_version.version
    library.categories.add(category)
    res = tp.get("libraries-by-category", category.slug)
    tp.response_302(res)
    assert res.url == f"/versions/{version.slug}/libraries-by-category/{category.slug}/"


def test_libraries_by_version_by_category(tp, library_version, category):
    """GET /libraries-by-category/{slug}/"""
    library = library_version.library
    version = library_version.version

    baker.make("libraries.Library", name="Sample")
    library.categories.add(category)
    res = tp.get("libraries-by-version-by-category", version.slug, category.slug)
    tp.response_200(res)
    assert "library_list" in res.context
    assert len(res.context["library_list"]) == 1
    assert library in res.context["library_list"]
    assert "category" in res.context
    assert res.context["category"] == category


def test_libraries_by_version_detail(tp, library_version):
    """GET /versions/{version_slug}/{slug}/"""
    res = tp.get(
        "libraries-by-version-detail",
        library_version.version.slug,
        library_version.library.slug,
    )
    tp.response_200(res)
    assert "version" in res.context


def test_libraries_by_version_detail_no_library_found(tp, library_version):
    """GET /versions/{version_slug}/{slug}/"""
    res = tp.get(
        "libraries-by-version-detail",
        library_version.version.slug,
        "coffee",
    )
    tp.response_404(res)


def test_libraries_by_version_detail_no_version_found(tp, library_version):
    """GET /versions/{version_slug}/{slug}/"""
    res = tp.get(
        "libraries-by-version-detail",
        0000,
        library_version.library.slug,
    )
    tp.response_404(res)


def test_libraries_by_version_list(tp, library_version):
    """GET /versions/{version_slug}/libraries/"""
    # Create a new library_version
    excluded_library = baker.make("libraries.Library", name="Sample")
    res = tp.get("libraries-by-version", library_version.version.slug)
    tp.response_200(res)
    assert "library_list" in res.context

    # Confirm that correct libraries are present
    assert len(res.context["library_list"]) == 1
    assert library_version.library in res.context["library_list"]
    assert excluded_library not in res.context["library_list"]


def test_library_detail_context_get_closed_prs_count(tp, library_version):
    """
    GET /versions/{version_slug}/{slug}/
    Test that the custom closed_prs_count var appears as expected
    """
    library = library_version.library
    version = library_version.version

    # Create open and closed PRs for this library, and another random PR
    lib2 = baker.make("libraries.Library", slug="sample")
    baker.make("libraries.PullRequest", library=library, is_open=True)
    baker.make("libraries.PullRequest", library=library, is_open=False)
    baker.make("libraries.PullRequest", library=lib2, is_open=True)
    url = tp.reverse("libraries-by-version-detail", version.slug, library.slug)
    response = tp.get(url)
    tp.response_200(response)
    assert "closed_prs_count" in response.context
    # Verify that the count only includes the one open PR for this library
    assert response.context["closed_prs_count"] == 1


def test_library_detail_context_get_open_issues_count(tp, library_version):
    """
    GET /versions/{version_slug}/{slug}/
    Test that the custom open_issues_count var appears as expected
    """
    library = library_version.library
    version = library_version.version

    # Create open and closed issues for this library, and another random issue
    lib2 = baker.make("libraries.Library", slug="sample")
    baker.make("libraries.Issue", library=library, is_open=True)
    baker.make("libraries.Issue", library=library, is_open=False)
    baker.make("libraries.Issue", library=lib2, is_open=True)
    url = tp.reverse("libraries-by-version-detail", version.slug, library.slug)
    response = tp.get(url)
    tp.response_200(response)
    assert "open_issues_count" in response.context
    # Verify that the count only includes the one open issue for this library
    assert response.context["open_issues_count"] == 1


def test_library_detail(library_version, tp):
    """GET /versions/{version_slug}/{slug}/"""
    library = library_version.library
    version = library_version.version
    url = tp.reverse("library-detail", library.slug)
    response = tp.get(url)
    tp.response_302(response)
    assert response.url == f"/versions/{version.slug}/{library.slug}/"
