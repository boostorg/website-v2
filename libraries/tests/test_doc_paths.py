"""Tests for the documentation path rules the Documenter achievement counts."""

import pytest

from libraries.doc_paths import count_doc_files, is_doc_path, resolve_rename

DOC_PATHS = [
    "doc/index.adoc",
    "docs/index.adoc",
    "doc/deep/nested/page.adoc",
    "doc/img/diagram.png",
    "doc/reference.qbk",
    "guide.rst",
    "CHANGELOG.md",
    "example/README.md",
    "doc/Makefile",
]

NON_DOC_PATHS = [
    "README.md",
    "include/boost/mp11/list.hpp",
    "test/list_test.cpp",
    "meta/libraries.json",
    "doc/build.json",
    "doc/html/index.html",
    "doc/html/reference.adoc",
    ".github/workflows/ci.yml",
    "doc/appveyor.yml",
    "doc/config.yaml",
    "doc/CMakeLists.cmake",
    "Jamfile.v2",
    "doc/Jamfile",
    "build/build.jam",
]


@pytest.mark.parametrize("path", DOC_PATHS)
def test_counts_as_documentation(path):
    assert is_doc_path(path) is True


@pytest.mark.parametrize("path", NON_DOC_PATHS)
def test_does_not_count_as_documentation(path):
    assert is_doc_path(path) is False


@pytest.mark.parametrize(
    "reported,destination",
    [
        ("doc/{old => new}/index.adoc", "doc/new/index.adoc"),
        ("{ => doc}/index.adoc", "doc/index.adoc"),
        ("doc/{sub => }/index.adoc", "doc/index.adoc"),
        ("old.adoc => new.adoc", "new.adoc"),
        ("doc/index.adoc", "doc/index.adoc"),
    ],
)
def test_resolve_rename(reported, destination):
    """git reports a rename as a single path, and the destination is what counts."""
    assert resolve_rename(reported) == destination


def test_count_doc_files_reads_numstat():
    """Binary files carry no line counts, and renames arrive as one path."""
    lines = [
        "12\t3\tdoc/index.adoc",
        "-\t-\tdoc/img/diagram.png",
        "40\t0\tinclude/boost/mp11/list.hpp",
        "2\t2\tdoc/{old => new}/guide.adoc",
        "1\t0\tREADME.md",
    ]
    assert count_doc_files(lines) == 3


def test_count_doc_files_ignores_anything_that_is_not_a_stat_line():
    assert count_doc_files(["", "not a stat line", "1\t2"]) == 0
