import datetime

from django.utils import timezone
from dateutil.relativedelta import relativedelta

from model_bakery import baker


def test_library_list(library_version, tp, url_name="libraries"):
    """GET /libraries/"""
    # Create a version with a library
    last_year = library_version.version.release_date - datetime.timedelta(days=365)
    v2 = baker.make(
        "versions.Version", name="boost-1.78.0", release_date=last_year, beta=False
    )
    lib2 = baker.make(
        "libraries.Library",
        name="sample",
    )
    baker.make("libraries.LibraryVersion", library=lib2, version=v2)

    # Create a version with no libraries
    v_no_libraries = baker.make(
        "versions.Version", name="boost-1.0.0", release_date=last_year, beta=False
    )

    res = tp.get(url_name)
    tp.response_200(res)
    assert "library_list" in res.context
    assert library_version.library in res.context["library_list"]
    assert lib2 not in res.context["library_list"]
    assert v_no_libraries not in res.context["versions"]


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
    new_lib = baker.make("libraries.Library", name="New")
    new_lib_version = baker.make(
        "libraries.LibraryVersion", version=library_version.version, library=new_lib
    )
    res = tp.get(f"/libraries/?category={category.slug}")
    tp.response_200(res)
    assert library_version.library in res.context["library_list"]
    assert new_lib_version.library not in res.context["library_list"]


def test_library_list_select_version(library_version, tp):
    """GET /libraries/?version={{ slug }} loads filtered results"""
    new_version = baker.make("versions.Version", name="New")
    new_lib = baker.make("libraries.Library", name="New")
    # Create a new library version that is not in the selected version
    new_lib_version = baker.make(
        "libraries.LibraryVersion", version=new_version, library=new_lib
    )
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


def test_library_detail_context_get_commit_data_annual(tp, library_version):
    """
    GET /libraries/{slug}/
    Test that the method correctly retrieves the commit data
    """
    library = library_version.library
    random_library = baker.make("libraries.Library", slug="random")
    current_year = timezone.now().year
    for i in range(10):
        year = current_year - i
        date = datetime.date(year, 1, 1)
        # Valid data
        baker.make(
            "libraries.CommitData",
            library=library,
            month_year=date,
            commit_count=i + 1,
            branch="master",
        )
        # Wrong library
        baker.make(
            "libraries.CommitData",
            library=random_library,
            month_year=date,
            commit_count=i + 1,
            branch="master",
        )
        # Wrong branch
        baker.make(
            "libraries.CommitData",
            library=library,
            month_year=date,
            commit_count=i + 1,
            branch="wrong-branch",
        )

    url = tp.reverse("library-detail", library.slug)
    response = tp.get_check_200(url)
    assert "commit_data_annual" in response.context
    commit_data_annual = response.context["commit_data_annual"]
    # Verify that the data is only for last 12 months for this library
    assert len(commit_data_annual) == 10
    for i, data in enumerate(reversed(commit_data_annual)):
        assert data["date"] == datetime.date(current_year - i, 1, 1)
        assert data["commit_count"] == i + 1


def test_library_detail_context_get_commit_data_last_12_months(tp, library_version):
    """
    GET /libraries/{slug}/
    Test that the commit_data_last_12_months var appears as expected
    """
    library = library_version.library

    # Create CommitData for the library and another random library
    random_library = baker.make("libraries.Library", slug="random")

    current_month = timezone.now().date().replace(day=1)
    for i in range(12):
        date = current_month - relativedelta(months=i)
        baker.make(
            "libraries.CommitData", library=library, month_year=date, commit_count=i + 1
        )
        baker.make(
            "libraries.CommitData",
            library=random_library,
            month_year=date,
            commit_count=i + 1,
        )

    url = tp.reverse("library-detail", library.slug)
    response = tp.get_check_200(url)
    assert "commit_data_last_12_months" in response.context
    commit_data_last_12_months = response.context["commit_data_last_12_months"]
    # Verify that the data is only for last 12 months for this library
    assert len(commit_data_last_12_months) == 12
    for i, data in enumerate(reversed(commit_data_last_12_months)):
        assert data["date"] == current_month - relativedelta(months=i)
        assert data["commit_count"] == i + 1


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


def test_library_detail_context_get_documentation_url(tp, user, library_version):
    """
    GET /libraries/{slug}/
    Test that the maintainers var appears as expected
    """
    library_version.documentation_url = None
    library_version.save()

    library = library_version.library
    url = tp.reverse("library-detail", library.slug)
    response = tp.get(url)
    tp.response_200(response)
    assert "documentation_url" in response.context
    assert (
        response.context["documentation_url"]
        == library_version.version.documentation_url
    )


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
