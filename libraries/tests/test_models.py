def test_github_properties(library):
    properties = library.github_properties()
    assert properties["owner"] == "boostorg"
    assert properties["repo"] == "multi_array"


def test_github_owner(library):
    assert library.github_owner == "boostorg"


def test_github_repo(library):
    assert library.github_repo == "multi_array"
