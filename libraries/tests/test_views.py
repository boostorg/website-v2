from unittest.mock import patch


def test_library_list(library, tp):
    res = tp.get("libraries")
    tp.response_200(res)


def test_library_detail(library, tp):
    url = tp.reverse("library-detail", library.slug)

    with patch("libraries.views.LibraryDetail.get_open_issues_count") as count_mock:
        count_mock.return_value = 21
        res = tp.get(url)
        tp.response_200(res)
