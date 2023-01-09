import pytest
from fastcore.xtras import dict2obj
from model_bakery import baker


@pytest.fixture
def category(db):
    return baker.make("libraries.Category", name="Math", slug="math")


@pytest.fixture
def library(db):
    return baker.make(
        "libraries.Library",
        name="multi_array",
        description="Boost.MultiArray provides a generic N-dimensional array concept definition and common implementations of that interface.",
        github_url="https://github.com/boostorg/multi_array",
    )


@pytest.fixture(autouse=True)
def github_api_get_ref_response(db):
    """Returns a JSON example of GhApi().api.git.get_ref(owner=owner, repo=repo, ref=ref)"""
    return {
        "ref": "refs/heads/master",
        "node_id": "sample",
        "url": "https://api.github.com/repos/boostorg/boost/git/refs/heads/master",
        "object": {
            "sha": "sample_sha",
            "type": "commit",
            "url": "https://api.github.com",
        },
    }


@pytest.fixture
def github_api_get_tree_response(db):
    """Returns a JSON example of GhApi().api.git.get_tree(owner=owner, repo="boost", tree_sha=tree_sha)"""
    return {
        "sha": "e2ae78645e6d7f6b455eea2f8c2846e67437b739",
        "url": "https://api.github.com/repos/boostorg/boost/git/trees/e2ae78645e6d7f6b455eea2f8c2846e67437b739",
        "tree": [
            {
                "path": ".circleci",
                "mode": "040000",
                "type": "tree",
                "sha": "7199ba30709deb2769d5207d24015a59eec6b9a2",
                "url": "https://api.github.com/repos/boostorg/boost/git/trees/7199ba30709deb2769d5207d24015a59eec6b9a2",
            },
            {
                "path": ".gitmodules",
                "mode": "100644",
                "type": "blob",
                "sha": "46977dba4255dcb4447e94ab5ae081ce67441aca",
                "size": 18459,
                "url": "https://api.github.com/repos/boostorg/boost/git/blobs/46977dba4255dcb4447e94ab5ae081ce67441aca",
            },
        ],
        "truncated": False,
    }


@pytest.fixture
def github_api_get_repo_response(db):
    """Returns a JSON example of GhApi().api.repos.get(owner=owner, repo=repo)"""
    return {"updated_at": "2022-09-14T22:20:38Z"}


@pytest.fixture
def github_api_repo_issues_response(db):
    """Returns the response from GhApi().issues.list_for_repo, already paged"""
    return [
        dict2obj(
            {
                "title": "Issue Number One",
                "number": 1,
                "state": "closed",
                "closed_at": "2022-04-11T12:38:24Z",
                "created_at": "2022-04-11T11:41:02Z",
                "updated_at": "2022-04-11T12:38:25Z",
                "id": 5898798798,
            }
        ),
        dict2obj(
            {
                "title": "Issue Number Two",
                "number": 2,
                "state": "open",
                "closed_at": "2022-04-11T12:38:24Z",
                "created_at": "2022-04-11T11:41:02Z",
                "updated_at": "2022-04-11T12:38:25Z",
                "id": 7395968281,
            }
        ),
        dict2obj(
            {
                "title": "Issue Number Three",
                "number": 3,
                "state": "closed",
                "closed_at": "2022-04-11T12:38:24Z",
                "created_at": "2022-04-11T11:41:02Z",
                "updated_at": "2022-04-11T12:38:25Z",
                "id": 7492027464,
            }
        ),
    ]


@pytest.fixture
def github_api_repo_prs_response(db):
    """Returns the response from GhApi().pulls.list, already paged"""
    return [
        dict2obj(
            {
                "title": "Improve logging",
                "number": 1,
                "state": "closed",
                "closed_at": "2022-04-11T12:38:24Z",
                "merged_at": "2022-04-11T12:38:24Z",
                "created_at": "2022-04-11T11:41:02Z",
                "updated_at": "2022-04-11T12:38:25Z",
                "id": 5898798798,
            }
        ),
        dict2obj(
            {
                "title": "Fix a test",
                "number": 2,
                "state": "open",
                "closed_at": "2022-04-11T12:38:24Z",
                "merged_at": "2022-04-11T12:38:24Z",
                "created_at": "2022-04-11T11:41:02Z",
                "updated_at": "2022-04-11T12:38:25Z",
                "id": 7395968281,
            }
        ),
        dict2obj(
            {
                "title": "Add a new feature",
                "number": 3,
                "state": "closed",
                "closed_at": "2022-04-11T12:38:24Z",
                "merged_at": "2022-04-11T12:38:24Z",
                "created_at": "2022-04-11T11:41:02Z",
                "updated_at": "2022-04-11T12:38:25Z",
                "id": 7492027464,
            }
        ),
    ]


@pytest.fixture
def boost_module():
    return {"module": "rational", "url": "rational"}


@pytest.fixture
def boost_modules(module):
    return [module]


@pytest.fixture
def library_metadata():
    """
    Returns a JSON example of a response from
    f"https://raw.githubusercontent.com/{self.owner}/{repo}/develop/meta/libraries.json"

    Live example: https://github.com/boostorg/align/blob/5ad7df63cd792fbdb801d600b93cad1a432f0151/meta/libraries.json
    """
    return {
        "key": "system",
        "name": "System",
        "authors": ["Tester Testerson"],
        "maintainers": ["Tester Testerston <tester -at- example.com>"],
        "description": "Extensible error reporting.",
        "category": ["System", "Error-handling", "Programming"],
        "cxxstd": "03",
    }


@pytest.fixture
def github_library():
    return {
        "name": "system",
        "github_url": "https://github.com/boostorg/system/",
        "authors": ["Tester Testerson"],
        "description": "Extensible error reporting.",
        "category": ["sample1", "sample2"],
        "maintainers": ["Tester Testerson <tester -at- example.com>"],
        "cxxstd": "03",
        "last_github_update": "2022-09-14T22:20:38Z",
    }
