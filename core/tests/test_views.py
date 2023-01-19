import pytest


def test_markdown_view_top_level(tp):
    """GET /content/map"""
    res = tp.get("/map")
    tp.response_200(res)


def test_markdown_view_trailing_slash(tp):
    res = tp.get("/map/")
    tp.response_200(res)


def test_markdown_view_top_level_includes_extension(tp):
    res = tp.get("/map.html")
    tp.response_200(res)


def test_markdown_view_nested(tp):
    res = tp.get("/community/policy")
    tp.response_200(res)


def test_markdown_view_nested_trailing_slash(tp):
    res = tp.get("/community/policy/")
    tp.response_200(res)


def test_markdown_view_nested_includes_extenstion(tp):
    res = tp.get("/community/policy.html")
    tp.response_200(res)


def test_markdown_view_nested_index_direct_path(tp):
    res = tp.get("/community/index.html")
    tp.response_200(res)


def test_markdown_view_nested_should_load_an_index(tp):
    res = tp.get("/community")
    tp.response_200(res)
