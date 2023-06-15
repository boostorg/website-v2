import datetime

from model_bakery import baker


def test_library_list(library_version, tp, url_name="libraries"):
    """GET /libraries/"""
    last_year = datetime.date.today() - datetime.timedelta(days=365)
    v2 = baker.make("versions.Version", name="Version 1.78.0", release_date=last_year)
    lib2 = baker.make(
        "libraries.Library",
        name="sample",
    )
    baker.make("libraries.LibraryVersion", library=lib2, version=v2)
    res = tp.get(url_name)
    tp.response_200(res)
    assert "library_list" in res.context
    assert library_version.library in res.context["library_list"]
    assert lib2 not in res.context["library_list"]


def test_library_list_mini(library_version, tp):
    """GET /libraries/mini/"""
    test_library_list(library_version, tp, url_name="libraries-mini")


def test_library_list_no_pagination(library_version, tp):
    """Library list is not paginated."""
    libs = [
        baker.make(
            "libraries.LibraryVersion",
            library=baker.make("libraries.Library", name=f"lib-{i}"),
            version=library_version.version,
        ).library
        for i in range(30)
    ] + [library_version.library]
    res = tp.get("libraries")
    tp.response_200(res)

    library_list = res.context.get("library_list")
    assert library_list is not None
    assert len(library_list) == len(libs)
    assert all(library in library_list for library in libs)
    page_obj = res.context.get("page_obj")
    assert getattr(page_obj, "paginator", None) is None


def test_library_list_select_category(library_version, category, tp):
    """GET /libraries/?category={{ slug }} loads filtered results"""
    library_version.library.categories.add(category)
    # Create a new library version that is not in the selected category
    new_lib_version = baker.make(
        "libraries.LibraryVersion", version=library_version.version
    )
    res = tp.get(f"/libraries/?category={category.slug}")
    tp.response_200(res)
    assert library_version.library in res.context["library_list"]
    assert new_lib_version.library not in res.context["library_list"]


def test_library_list_select_version(library_version, tp):
    """GET /libraries/?version={{ slug }} loads filtered results"""
    new_version = baker.make("versions.Version")
    # Create a new library version that is not in the selected version
    new_lib_version = baker.make("libraries.LibraryVersion", version=new_version)
    res = tp.get(f"/libraries/?version={library_version.version.slug}")
    tp.response_200(res)
    assert library_version.library in res.context["library_list"]
    assert new_lib_version.library not in res.context["library_list"]


def test_library_list_by_category(
    library_version, category, tp, url="libraries-by-category"
):
    """GET /libraries/by-category/"""
    library_version.library.categories.add(category)
    res = tp.get(url)
    tp.response_200(res)
    assert "library_list" in res.context
    assert "category" in res.context["library_list"][0]
    assert "libraries" in res.context["library_list"][0]


def test_library_list_by_category_mini(library_version, category, tp):
    """GET /libraries/by-category/mini/"""
    test_library_list_by_category(
        library_version, category, tp, url="libraries-by-category-mini"
    )


def test_library_detail(library_version, tp):
    """GET /libraries/{slug}/"""
    library = library_version.library
    url = tp.reverse("library-detail", library.slug)
    response = tp.get(url)
    tp.response_200(response)


def test_library_detail_404(library, tp):
    """GET /libraries/{slug}/"""
    # 404 due to bad slug
    url = tp.reverse("library-detail", "bananas")
    response = tp.get(url)
    tp.response_404(response)

    # 404 due to no existing version
    url = tp.reverse("library-detail", library.slug)
    response = tp.get(url)
    tp.response_404(response)


def test_library_detail_context_get_maintainers(tp, user, library_version):
    """
    GET /libraries/{slug}/
    Test that the maintainers var appears as expected
    """
    library_version.maintainers.add(user)
    library = library_version.library
    # Create open and closed PRs for this library, and another random PR
    lib2 = baker.make("libraries.Library", slug="sample")
    baker.make("libraries.PullRequest", library=library, is_open=True)
    baker.make("libraries.PullRequest", library=library, is_open=False)
    baker.make("libraries.PullRequest", library=lib2, is_open=True)
    url = tp.reverse("library-detail", library.slug)
    response = tp.get(url)
    tp.response_200(response)
    assert "maintainers" in response.context
    assert len(response.context["maintainers"]) == 1
    assert response.context["maintainers"][0] == user


def test_libraries_by_version_detail(tp, library_version):
    """GET /libraries/{slug}/{version_slug}/"""
    res = tp.get(
        "library-detail-by-version",
        library_version.library.slug,
        library_version.version.slug,
    )
    tp.response_200(res)
    assert "version" in res.context


def test_libraries_by_version_detail_no_library_found(tp, library_version):
    """GET /libraries/{slug}/{version_slug}/"""
    res = tp.get(
        "library-detail-by-version",
        "coffee",
        library_version.version.slug,
    )
    tp.response_404(res)


def test_libraries_by_version_detail_no_version_found(tp, library_version):
    """GET /libraries/{slug}/{version_slug}/"""
    res = tp.get(
        "library-detail-by-version",
        library_version.library.slug,
        000000,
    )
    tp.response_404(res)
