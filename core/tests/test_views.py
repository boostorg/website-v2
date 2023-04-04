# import pytest


# def test_markdown_view_top_level(tp):
#     """GET /content/map"""
#     res = tp.get("/foo")
#     tp.response_200(res)


# def test_markdown_view_trailing_slash(tp):
#     res = tp.get("/foo/")
#     tp.response_200(res)


# def test_markdown_view_top_level_includes_extension(tp):
#     res = tp.get("/foo.html")
#     tp.response_200(res)


# def test_markdown_view_nested(tp):
#     res = tp.get("/more_content/bar")
#     tp.response_200(res)


# def test_markdown_view_nested_trailing_slash(tp):
#     res = tp.get("/more_content/bar/")
#     tp.response_200(res)


# def test_markdown_view_nested_includes_extenstion(tp):
#     res = tp.get("/more_content/bar.md")
#     tp.response_200(res)


# def test_markdown_view_nested_index_direct_path(tp):
#     res = tp.get("/more_content/index.html")
#     tp.response_200(res)


# def test_markdown_view_nested_should_load_an_index(tp):
#     res = tp.get("/more_content")
#     tp.response_200(res)


# def test_markdown_view_nested_three_levels(tp):
#     res = tp.get("/more_content/even_more_content/sample")
#     tp.response_200(res)
