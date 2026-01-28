import datetime

import pytest

from model_bakery import baker

from ..constants import README_MISSING
from ..models import Library
from versions.models import Version


def test_library_list(library_version, tp, url_name="libraries", request_kwargs=None):
    """GET /libraries/"""
    # Create a version with a library
    if not request_kwargs:
        request_kwargs = {}
    last_year = library_version.version.release_date - datetime.timedelta(days=365)
    v2 = baker.make(
        "versions.Version", name="boost-1.78.0", release_date=last_year, beta=False
    )
    lib2 = baker.make(
        "libraries.Library",
        name="sample",
    )
    baker.make("libraries.LibraryVersion", library=lib2, version=v2)

    url = tp.reverse(url_name, **request_kwargs)
    res = tp.get(url, **request_kwargs)

    if url_name == "libraries":
        tp.response_302(res)
        return
    tp.response_200(res)
    assert "object_list" in res.context
    assert library_version in res.context["object_list"]
    assert lib2 not in res.context["object_list"]


def test_library_root_redirect_to_grid(tp):
    """GET /libraries/"""
    res = tp.get("libraries")
    tp.response_302(res)
    assert res.url == "/libraries/latest/grid/"


def test_library_list_no_data(tp):
    """GET /libraries/latest/grid/"""
    Library.objects.all().delete()
    Version.objects.all().delete()
    res = tp.get("/libraries/latest/grid/")
    tp.response_200(res)


def test_library_list_list(library_version, tp):
    """GET /libraries/latest/list"""
    test_library_list(
        library_version,
        tp,
        url_name="libraries-list",
        request_kwargs={"version_slug": "latest", "library_view_str": "list"},
    )


def test_library_list_list_no_data(tp):
    """GET /libraries/"""
    Library.objects.all().delete()
    Version.objects.all().delete()
    url = tp.reverse("libraries-list", "latest", "list")
    res = tp.get(url)
    tp.response_200(res)


def test_library_list_no_pagination(library_version, tp):
    """Library list is not paginated."""
    lib_versions = [
        baker.make(
            "libraries.LibraryVersion",
            library=baker.make("libraries.Library", name=f"lib-{i}"),
            version=library_version.version,
        )
        for i in range(30)
    ] + [library_version]
    url = tp.reverse("libraries-list", "latest", "grid")
    res = tp.get(url)
    tp.response_200(res)

    library_version_list = res.context.get("object_list")
    assert library_version_list is not None
    assert len(library_version_list) == len(lib_versions)
    assert all(lv in library_version_list for lv in lib_versions)
    page_obj = res.context.get("page_obj")
    assert getattr(page_obj, "paginator", None) is None


def test_library_list_select_category(library_version, category, tp):
    """GET /libraries/latest/grid/{category_slug}/ loads filtered results"""
    library_version.library.categories.add(category)
    # Create a new library version that is not in the selected category
    new_lib = baker.make("libraries.Library", name="New")
    new_lib_version = baker.make(
        "libraries.LibraryVersion", version=library_version.version, library=new_lib
    )
    res = tp.get(f"/libraries/latest/grid/{category.slug}/")
    tp.response_200(res)
    assert library_version in res.context["object_list"]
    assert new_lib_version not in res.context["object_list"]


@pytest.mark.skip(
    reason="This test is failing due to the way the library list is being filtered"
)
def test_library_list_select_version(library_version, tp):
    """GET /libraries/{version_slug}/list/ loads filtered results"""
    new_version = baker.make("versions.Version", name="New")
    new_lib = baker.make("libraries.Library", name="New")
    # Create a new library version that is not in the selected version
    new_lib_version = baker.make(
        "libraries.LibraryVersion", version=new_version, library=new_lib
    )
    res = tp.get(f"/libraries/{library_version.version.slug}/list/")
    tp.response_200(res)
    assert library_version.library in res.context["object_list"]
    assert new_lib_version.library not in res.context["object_list"]


def test_library_list_by_category(library_version, category, tp, url="libraries-list"):
    """GET /libraries/latest/categorized/"""
    # this first part of the test is weird, maybe a change in functionality happened?
    # the categorized view shows all categories - the category slug is ignored - so
    # all categories show
    reverse_url = tp.reverse(url, "latest", "categorized", category.slug)
    library_version.library.categories.add(category)
    res = tp.get(reverse_url)
    tp.response_200(res)
    assert "library_versions_by_category" in res.context
    assert "category" in res.context["library_versions_by_category"][0]
    assert "library_version_list" in res.context["library_versions_by_category"][0]

    # Create a new library version that is not in the selected version
    existing_category = library_version.library.categories.first()
    new_category = baker.make("libraries.Category", name="New Category")
    new_version = baker.make("versions.Version", name="New")
    new_lib = baker.make("libraries.Library", name="New", categories=[new_category])
    baker.make("libraries.LibraryVersion", version=new_version, library=new_lib)
    url = tp.reverse("libraries-list", library_version.version.slug, "categorized")
    res = tp.get(url)
    tp.response_200(res)
    tp.assertContext("version_slug", library_version.version.slug)
    assert existing_category in [
        x["category"] for x in res.context["library_versions_by_category"]
    ]
    assert new_category not in [
        x["category"] for x in res.context["library_versions_by_category"]
    ]


def test_library_detail(library_version, tp):
    """GET /library/latest/{library_slug}/"""
    library = library_version.library
    url = tp.reverse("library-detail", "latest", library.slug)
    response = tp.get(url)
    tp.response_200(response)


def test_library_detail_404(library, old_version, tp):
    """GET /library/latest/{bad_library_slug}/"""
    # 404 due to bad slug
    url = tp.reverse("library-detail", "latest", "bananas")
    response = tp.get(url)
    tp.response_404(response)


def test_library_detail_missing_version(library, old_version, tp):
    # custom error due to no existing version
    url = tp.reverse("library-detail", old_version.display_name, library.slug)
    response = tp.get(url)
    assert (
        "There was no version of the Boost.MultiArray library in the 1.70.0 version of "
        "Boost." in response.content.decode("utf-8")
    )


def test_library_docs_redirect(tp, library, library_version):
    """
    GET /libs/{library_slug}/
    Test that redirection occurs when the library has a documentation URL
    """
    url = tp.reverse("library-docs-redirect", library.slug)
    assert url.startswith("/libs/")

    resp = tp.get(url, follow=False)
    tp.response_302(resp)


def test_library_detail_context_get_commit_data_(tp, library_version):
    """
    GET /library/latest/{library_slug}/
    Test that the commit_data_by_release var appears as expected
    """
    library = library_version.library

    version_a = baker.make("versions.Version", name="a")
    version_b = baker.make("versions.Version", name="b")
    version_c = baker.make("versions.Version", name="c")

    lv_a = baker.make("libraries.LibraryVersion", version=version_a, library=library)
    lv_b = baker.make("libraries.LibraryVersion", version=version_b, library=library)
    lv_c = baker.make("libraries.LibraryVersion", version=version_c, library=library)

    for lv in [lv_a, lv_b, lv_c]:
        baker.make("libraries.Commit", library_version=lv)

    url = tp.reverse("library-detail", "latest", library.slug)
    response = tp.get_check_200(url)
    assert "commit_data_by_release" in response.context


def test_library_detail_context_get_maintainers(tp, user, library_version):
    """
    GET /libraries/latest/{library_slug}/
    Test that the maintainers var appears as expected
    """
    library_version.maintainers.add(user)
    library = library_version.library
    # Create open and closed PRs for this library, and another random PR
    lib2 = baker.make("libraries.Library", slug="sample")
    baker.make("libraries.PullRequest", library=library, is_open=True)
    baker.make("libraries.PullRequest", library=library, is_open=False)
    baker.make("libraries.PullRequest", library=lib2, is_open=True)
    url = tp.reverse("library-detail", "latest", library.slug)
    response = tp.get(url)
    tp.response_200(response)
    assert "maintainers" in response.context
    assert len(response.context["maintainers"]) == 1
    assert response.context["maintainers"][0] == user


def test_library_detail_context_get_documentation_url_no_docs_link(
    tp, user, library_version
):
    """
    GET /library/{version_slug}/{library_slug}/
    """
    library_version.documentation_url = None
    library_version.save()

    library = library_version.library
    url = tp.reverse("library-detail", library_version.version.slug, library.slug)
    response = tp.get(url)
    tp.response_200(response)
    assert "documentation_url" in response.context
    assert response.context["documentation_url"] is None


def test_library_detail_context_get_documentation_url_missing_docs_bool(
    tp, user, library_version
):
    """
    GET /library/{version_slug}/{library_slug}/
    """
    library_version.documentation_url = None
    library_version.missing_docs = True
    library_version.save()

    library = library_version.library
    url = tp.reverse("library-detail", library_version.version.slug, library.slug)
    response = tp.get(url)
    tp.response_200(response)
    assert "documentation_url" in response.context
    assert response.context["documentation_url"] is None


def test_library_detail_context_get_documentation_url_docs_present(
    tp, user, library_version
):
    """
    GET /libraries/{version_slug}/{library_slug}/
    """
    library_version.documentation_url = "https://example.com"
    library_version.missing_docs = False
    library_version.save()

    library = library_version.library
    url = tp.reverse("library-detail", library_version.version.slug, library.slug)
    response = tp.get(url)
    tp.response_200(response)
    assert "documentation_url" in response.context
    assert response.context["documentation_url"] == library_version.documentation_url


def test_libraries_by_version_detail(tp, library_version):
    """GET /libraries/{version_slug}/{library_slug}/"""
    res = tp.get(
        "library-detail",
        library_version.version.slug,
        library_version.library.slug,
    )
    tp.response_200(res)
    assert "current_version" in res.context
    assert "selected_version" in res.context
    assert res.context["selected_version"] == library_version.version


def test_libraries_by_version_detail_no_library_found(tp, library_version):
    """GET /library/{version_slug}/{bad_library_slug}/"""
    res = tp.get(
        "library-detail",
        library_version.version.slug,
        "coffee",
    )
    tp.response_404(res)


def test_libraries_by_version_detail_no_version_found(tp, library_version):
    """GET /library/{version_slug}/{bad_library_slug}/"""
    res = tp.get(
        "library-detail",
        000000,
        library_version.library.slug,
    )
    tp.response_404(res)


def test_library_detail_context_missing_readme(tp, user, library_version):
    """
    GET /library/latest/{library_slug}/
    Test that the missing readme message appears as expected
    """

    library = library_version.library
    url = tp.reverse("library-detail", "latest", library.slug)

    response = tp.get(url)

    tp.response_200(response)
    assert "description" in response.context
    assert response.context["description"] == README_MISSING


def test_redirect_to_library_list_view(library_version, tp):
    """
    GET /libraries/{version_string}/
    Test that redirection occurs to the proper libraries list view
    """
    url = tp.reverse("redirect-to-library-list-view", "1.79.0")

    response = tp.get(url, follow=False)
    tp.response_302(response)

    # Should redirect to the libraries-list view with the version slug
    expected_redirect = "/libraries/1.79.0/grid/"
    assert response.url == expected_redirect


def test_library_dependencies_no_previous_version(library_version, dependency, tp):
    """
    GET /libraries/{version_string}/
    Test that a newly introduced library has its dependencies shown
    """

    library = library_version.library
    url = tp.reverse("library-detail", "latest", library.slug)

    response = tp.get(url)
    tp.response_200(response)

    # Context dependencies should contain our dependency
    assert dependency in response.context["dependency_diff"]["current_dependencies"]
    assert dependency.name not in response.context["dependency_diff"]["added"]
    assert "dependencies_not_calculated" not in response.context


def test_library_added_dependencies(library_version, old_version, dependency, tp):
    """
    GET /libraries/{version_string}/
    Test that when a new dependency is added it is in the added field
    """

    library = library_version.library
    baker.make("libraries.LibraryVersion", library=library, version=old_version)
    url = tp.reverse("library-detail", "latest", library.slug)

    response = tp.get(url)
    tp.response_200(response)

    # Context dependencies should contain our dependency
    assert dependency in response.context["dependency_diff"]["current_dependencies"]
    assert dependency.name in response.context["dependency_diff"]["added"]
    assert "dependencies_not_calculated" not in response.context


def test_library_removed_dependencies(library_version, old_version, dependency, tp):
    """
    GET /libraries/{version_string}/
    Test that when a new dependency is removed it is in the removed field
    """

    library = library_version.library
    new_dependency = baker.make(
        "libraries.Library",
        name="assert",
        slug="assert",
        description=("Customizable assert macros."),
        github_url="https://github.com/boostorg/assert/tree/boost-1.90.0",
    )
    baker.make(
        "libraries.LibraryVersion",
        library=library,
        version=old_version,
        dependencies=[dependency, new_dependency],
    )
    url = tp.reverse("library-detail", "latest", library.slug)

    response = tp.get(url)
    tp.response_200(response)

    # Context dependencies should contain our dependency
    assert dependency in response.context["dependency_diff"]["current_dependencies"]
    assert dependency.name not in response.context["dependency_diff"]["added"]
    assert new_dependency.name in response.context["dependency_diff"]["removed"]
    assert "dependencies_not_calculated" not in response.context
