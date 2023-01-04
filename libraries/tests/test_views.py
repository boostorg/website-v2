from model_bakery import baker


def test_library_list(library, tp):
    """GET /libraries/"""
    res = tp.get("libraries")
    tp.response_200(res)


def test_library_detail(library, tp):
    """GET /libraries/{repo}/"""
    url = tp.reverse("library-detail", library.slug)
    response = tp.get(url)
    tp.response_200(response)


def test_library_detail_context_get_closed_prs_count(tp, library):
    """
    GET /libraries/{repo}/
    Test that the custom closed_prs_count var appears as expected
    """
    # Create open and closed PRs for this library, and another random PR
    lib2 = baker.make("libraries.Library", slug="sample")
    baker.make("libraries.PullRequest", library=library, is_open=True)
    baker.make("libraries.PullRequest", library=library, is_open=False)
    baker.make("libraries.PullRequest", library=lib2, is_open=True)
    url = tp.reverse("library-detail", library.slug)
    response = tp.get(url)
    tp.response_200(response)
    assert "closed_prs_count" in response.context
    # Verify that the count only includes the one open PR for this library
    assert response.context["closed_prs_count"] == 1


def test_library_detail_context_get_open_issues_count(tp, library):
    """
    GET /libraries/{repo}/
    Test that the custom open_issues_count var appears as expected
    """
    # Create open and closed issues for this library, and another random issue
    lib2 = baker.make("libraries.Library", slug="sample")
    baker.make("libraries.Issue", library=library, is_open=True)
    baker.make("libraries.Issue", library=library, is_open=False)
    baker.make("libraries.Issue", library=lib2, is_open=True)
    url = tp.reverse("library-detail", library.slug)
    response = tp.get(url)
    tp.response_200(response)
    assert "open_issues_count" in response.context
    # Verify that the count only includes the one open issue for this library
    assert response.context["open_issues_count"] == 1
