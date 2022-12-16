import pytest
from model_bakery import baker


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
    return {
        "url": "https://api.github.com/repos/boostorg/system/pulls/90",
        "id": 1032140532,
        "node_id": "PR_kwDOAHPQi849hTb0",
        "html_url": "https://github.com/boostorg/system/pull/90",
        "diff_url": "https://github.com/boostorg/system/pull/90.diff",
        "patch_url": "https://github.com/boostorg/system/pull/90.patch",
        "issue_url": "https://api.github.com/repos/boostorg/system/issues/90",
        "number": 90,
        "state": "open",
        "locked": False,
        "title": "add boost_system.natvis and interface source files",
        "user": {
            "login": "vinniefalco",
            "id": 1503976,
            "node_id": "MDQ6VXNlcjE1MDM5NzY=",
            "avatar_url": "https://avatars.githubusercontent.com/u/1503976?v=4",
            "gravatar_id": "",
            "url": "https://api.github.com/users/vinniefalco",
            "html_url": "https://github.com/vinniefalco",
            "followers_url": "https://api.github.com/users/vinniefalco/followers",
            "following_url": "https://api.github.com/users/vinniefalco/following{/other_user}",
            "gists_url": "https://api.github.com/users/vinniefalco/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/vinniefalco/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/vinniefalco/subscriptions",
            "organizations_url": "https://api.github.com/users/vinniefalco/orgs",
            "repos_url": "https://api.github.com/users/vinniefalco/repos",
            "events_url": "https://api.github.com/users/vinniefalco/events{/privacy}",
            "received_events_url": "https://api.github.com/users/vinniefalco/received_events",
            "type": "User",
            "site_admin": False,
        },
        "body": None,
        "created_at": "2022-08-21T22:24:43Z",
        "updated_at": "2022-08-21T22:24:43Z",
        "closed_at": None,
        "merged_at": None,
        "merge_commit_sha": "37653ac206475a046d7e7abadaf823430e564572",
        "assignee": None,
        "assignees": [],
        "requested_reviewers": [],
        "requested_teams": [],
        "labels": [],
        "milestone": None,
        "draft": False,
        "commits_url": "https://api.github.com/repos/boostorg/system/pulls/90/commits",
        "review_comments_url": "https://api.github.com/repos/boostorg/system/pulls/90/comments",
        "review_comment_url": "https://api.github.com/repos/boostorg/system/pulls/comments{/number}",
        "comments_url": "https://api.github.com/repos/boostorg/system/issues/90/comments",
        "statuses_url": "https://api.github.com/repos/boostorg/system/statuses/fe48c3058daaa31da6c50c316d63aa5f185dacb8",
        "head": {
            "label": "vinniefalco:natvis",
            "ref": "natvis",
            "sha": "fe48c3058daaa31da6c50c316d63aa5f185dacb8",
            "user": {
                "login": "vinniefalco",
                "id": 1503976,
                "node_id": "MDQ6VXNlcjE1MDM5NzY=",
                "avatar_url": "https://avatars.githubusercontent.com/u/1503976?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/vinniefalco",
                "html_url": "https://github.com/vinniefalco",
                "followers_url": "https://api.github.com/users/vinniefalco/followers",
                "following_url": "https://api.github.com/users/vinniefalco/following{/other_user}",
                "gists_url": "https://api.github.com/users/vinniefalco/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/vinniefalco/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/vinniefalco/subscriptions",
                "organizations_url": "https://api.github.com/users/vinniefalco/orgs",
                "repos_url": "https://api.github.com/users/vinniefalco/repos",
                "events_url": "https://api.github.com/users/vinniefalco/events{/privacy}",
                "received_events_url": "https://api.github.com/users/vinniefalco/received_events",
                "type": "User",
                "site_admin": False,
            },
            "repo": {
                "id": 526406204,
                "node_id": "R_kgDOH2BSPA",
                "name": "boost-system",
                "full_name": "vinniefalco/boost-system",
                "private": False,
                "owner": {
                    "login": "vinniefalco",
                    "id": 1503976,
                    "node_id": "MDQ6VXNlcjE1MDM5NzY=",
                    "avatar_url": "https://avatars.githubusercontent.com/u/1503976?v=4",
                    "gravatar_id": "",
                    "url": "https://api.github.com/users/vinniefalco",
                    "html_url": "https://github.com/vinniefalco",
                    "followers_url": "https://api.github.com/users/vinniefalco/followers",
                    "following_url": "https://api.github.com/users/vinniefalco/following{/other_user}",
                    "gists_url": "https://api.github.com/users/vinniefalco/gists{/gist_id}",
                    "starred_url": "https://api.github.com/users/vinniefalco/starred{/owner}{/repo}",
                    "subscriptions_url": "https://api.github.com/users/vinniefalco/subscriptions",
                    "organizations_url": "https://api.github.com/users/vinniefalco/orgs",
                    "repos_url": "https://api.github.com/users/vinniefalco/repos",
                    "events_url": "https://api.github.com/users/vinniefalco/events{/privacy}",
                    "received_events_url": "https://api.github.com/users/vinniefalco/received_events",
                    "type": "User",
                    "site_admin": False,
                },
                "html_url": "https://github.com/vinniefalco/boost-system",
                "description": "Boost.org system module ",
                "fork": True,
                "url": "https://api.github.com/repos/vinniefalco/boost-system",
                "forks_url": "https://api.github.com/repos/vinniefalco/boost-system/forks",
                "keys_url": "https://api.github.com/repos/vinniefalco/boost-system/keys{/key_id}",
                "collaborators_url": "https://api.github.com/repos/vinniefalco/boost-system/collaborators{/collaborator}",
                "teams_url": "https://api.github.com/repos/vinniefalco/boost-system/teams",
                "hooks_url": "https://api.github.com/repos/vinniefalco/boost-system/hooks",
                "issue_events_url": "https://api.github.com/repos/vinniefalco/boost-system/issues/events{/number}",
                "events_url": "https://api.github.com/repos/vinniefalco/boost-system/events",
                "assignees_url": "https://api.github.com/repos/vinniefalco/boost-system/assignees{/user}",
                "branches_url": "https://api.github.com/repos/vinniefalco/boost-system/branches{/branch}",
                "tags_url": "https://api.github.com/repos/vinniefalco/boost-system/tags",
                "blobs_url": "https://api.github.com/repos/vinniefalco/boost-system/git/blobs{/sha}",
                "git_tags_url": "https://api.github.com/repos/vinniefalco/boost-system/git/tags{/sha}",
                "git_refs_url": "https://api.github.com/repos/vinniefalco/boost-system/git/refs{/sha}",
                "trees_url": "https://api.github.com/repos/vinniefalco/boost-system/git/trees{/sha}",
                "statuses_url": "https://api.github.com/repos/vinniefalco/boost-system/statuses/{sha}",
                "languages_url": "https://api.github.com/repos/vinniefalco/boost-system/languages",
                "stargazers_url": "https://api.github.com/repos/vinniefalco/boost-system/stargazers",
                "contributors_url": "https://api.github.com/repos/vinniefalco/boost-system/contributors",
                "subscribers_url": "https://api.github.com/repos/vinniefalco/boost-system/subscribers",
                "subscription_url": "https://api.github.com/repos/vinniefalco/boost-system/subscription",
                "commits_url": "https://api.github.com/repos/vinniefalco/boost-system/commits{/sha}",
                "git_commits_url": "https://api.github.com/repos/vinniefalco/boost-system/git/commits{/sha}",
                "comments_url": "https://api.github.com/repos/vinniefalco/boost-system/comments{/number}",
                "issue_comment_url": "https://api.github.com/repos/vinniefalco/boost-system/issues/comments{/number}",
                "contents_url": "https://api.github.com/repos/vinniefalco/boost-system/contents/{+path}",
                "compare_url": "https://api.github.com/repos/vinniefalco/boost-system/compare/{base}...{head}",
                "merges_url": "https://api.github.com/repos/vinniefalco/boost-system/merges",
                "archive_url": "https://api.github.com/repos/vinniefalco/boost-system/{archive_format}{/ref}",
                "downloads_url": "https://api.github.com/repos/vinniefalco/boost-system/downloads",
                "issues_url": "https://api.github.com/repos/vinniefalco/boost-system/issues{/number}",
                "pulls_url": "https://api.github.com/repos/vinniefalco/boost-system/pulls{/number}",
                "milestones_url": "https://api.github.com/repos/vinniefalco/boost-system/milestones{/number}",
                "notifications_url": "https://api.github.com/repos/vinniefalco/boost-system/notifications{?since,all,participating}",
                "labels_url": "https://api.github.com/repos/vinniefalco/boost-system/labels{/name}",
                "releases_url": "https://api.github.com/repos/vinniefalco/boost-system/releases{/id}",
                "deployments_url": "https://api.github.com/repos/vinniefalco/boost-system/deployments",
                "created_at": "2022-08-18T23:48:50Z",
                "updated_at": "2022-08-19T01:05:39Z",
                "pushed_at": "2022-08-21T22:22:12Z",
                "git_url": "git://github.com/vinniefalco/boost-system.git",
                "ssh_url": "git@github.com:vinniefalco/boost-system.git",
                "clone_url": "https://github.com/vinniefalco/boost-system.git",
                "svn_url": "https://github.com/vinniefalco/boost-system",
                "homepage": "http://boost.org/libs/system",
                "size": 781,
                "stargazers_count": 0,
                "watchers_count": 0,
                "language": "C++",
                "has_issues": False,
                "has_projects": True,
                "has_downloads": True,
                "has_wiki": True,
                "has_pages": False,
                "has_discussions": False,
                "forks_count": 0,
                "mirror_url": None,
                "archived": False,
                "disabled": False,
                "open_issues_count": 0,
                "license": None,
                "allow_forking": True,
                "is_template": False,
                "web_commit_signoff_required": False,
                "topics": [],
                "visibility": "public",
                "forks": 0,
                "open_issues": 0,
                "watchers": 0,
                "default_branch": "develop",
            },
        },
        "base": {
            "label": "boostorg:develop",
            "ref": "develop",
            "sha": "8c740705e6a221ef5fed7402338ba475df84077d",
            "user": {
                "login": "boostorg",
                "id": 3170529,
                "node_id": "MDEyOk9yZ2FuaXphdGlvbjMxNzA1Mjk=",
                "avatar_url": "https://avatars.githubusercontent.com/u/3170529?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/boostorg",
                "html_url": "https://github.com/boostorg",
                "followers_url": "https://api.github.com/users/boostorg/followers",
                "following_url": "https://api.github.com/users/boostorg/following{/other_user}",
                "gists_url": "https://api.github.com/users/boostorg/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/boostorg/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/boostorg/subscriptions",
                "organizations_url": "https://api.github.com/users/boostorg/orgs",
                "repos_url": "https://api.github.com/users/boostorg/repos",
                "events_url": "https://api.github.com/users/boostorg/events{/privacy}",
                "received_events_url": "https://api.github.com/users/boostorg/received_events",
                "type": "Organization",
                "site_admin": False,
            },
            "repo": {
                "id": 7590027,
                "node_id": "MDEwOlJlcG9zaXRvcnk3NTkwMDI3",
                "name": "system",
                "full_name": "boostorg/system",
                "private": False,
                "owner": {
                    "login": "boostorg",
                    "id": 3170529,
                    "node_id": "MDEyOk9yZ2FuaXphdGlvbjMxNzA1Mjk=",
                    "avatar_url": "https://avatars.githubusercontent.com/u/3170529?v=4",
                    "gravatar_id": "",
                    "url": "https://api.github.com/users/boostorg",
                    "html_url": "https://github.com/boostorg",
                    "followers_url": "https://api.github.com/users/boostorg/followers",
                    "following_url": "https://api.github.com/users/boostorg/following{/other_user}",
                    "gists_url": "https://api.github.com/users/boostorg/gists{/gist_id}",
                    "starred_url": "https://api.github.com/users/boostorg/starred{/owner}{/repo}",
                    "subscriptions_url": "https://api.github.com/users/boostorg/subscriptions",
                    "organizations_url": "https://api.github.com/users/boostorg/orgs",
                    "repos_url": "https://api.github.com/users/boostorg/repos",
                    "events_url": "https://api.github.com/users/boostorg/events{/privacy}",
                    "received_events_url": "https://api.github.com/users/boostorg/received_events",
                    "type": "Organization",
                    "site_admin": False,
                },
                "html_url": "https://github.com/boostorg/system",
                "description": "Boost.org system module ",
                "fork": False,
                "url": "https://api.github.com/repos/boostorg/system",
                "forks_url": "https://api.github.com/repos/boostorg/system/forks",
                "keys_url": "https://api.github.com/repos/boostorg/system/keys{/key_id}",
                "collaborators_url": "https://api.github.com/repos/boostorg/system/collaborators{/collaborator}",
                "teams_url": "https://api.github.com/repos/boostorg/system/teams",
                "hooks_url": "https://api.github.com/repos/boostorg/system/hooks",
                "issue_events_url": "https://api.github.com/repos/boostorg/system/issues/events{/number}",
                "events_url": "https://api.github.com/repos/boostorg/system/events",
                "assignees_url": "https://api.github.com/repos/boostorg/system/assignees{/user}",
                "branches_url": "https://api.github.com/repos/boostorg/system/branches{/branch}",
                "tags_url": "https://api.github.com/repos/boostorg/system/tags",
                "blobs_url": "https://api.github.com/repos/boostorg/system/git/blobs{/sha}",
                "git_tags_url": "https://api.github.com/repos/boostorg/system/git/tags{/sha}",
                "git_refs_url": "https://api.github.com/repos/boostorg/system/git/refs{/sha}",
                "trees_url": "https://api.github.com/repos/boostorg/system/git/trees{/sha}",
                "statuses_url": "https://api.github.com/repos/boostorg/system/statuses/{sha}",
                "languages_url": "https://api.github.com/repos/boostorg/system/languages",
                "stargazers_url": "https://api.github.com/repos/boostorg/system/stargazers",
                "contributors_url": "https://api.github.com/repos/boostorg/system/contributors",
                "subscribers_url": "https://api.github.com/repos/boostorg/system/subscribers",
                "subscription_url": "https://api.github.com/repos/boostorg/system/subscription",
                "commits_url": "https://api.github.com/repos/boostorg/system/commits{/sha}",
                "git_commits_url": "https://api.github.com/repos/boostorg/system/git/commits{/sha}",
                "comments_url": "https://api.github.com/repos/boostorg/system/comments{/number}",
                "issue_comment_url": "https://api.github.com/repos/boostorg/system/issues/comments{/number}",
                "contents_url": "https://api.github.com/repos/boostorg/system/contents/{+path}",
                "compare_url": "https://api.github.com/repos/boostorg/system/compare/{base}...{head}",
                "merges_url": "https://api.github.com/repos/boostorg/system/merges",
                "archive_url": "https://api.github.com/repos/boostorg/system/{archive_format}{/ref}",
                "downloads_url": "https://api.github.com/repos/boostorg/system/downloads",
                "issues_url": "https://api.github.com/repos/boostorg/system/issues{/number}",
                "pulls_url": "https://api.github.com/repos/boostorg/system/pulls{/number}",
                "milestones_url": "https://api.github.com/repos/boostorg/system/milestones{/number}",
                "notifications_url": "https://api.github.com/repos/boostorg/system/notifications{?since,all,participating}",
                "labels_url": "https://api.github.com/repos/boostorg/system/labels{/name}",
                "releases_url": "https://api.github.com/repos/boostorg/system/releases{/id}",
                "deployments_url": "https://api.github.com/repos/boostorg/system/deployments",
                "created_at": "2013-01-13T15:59:31Z",
                "updated_at": "2022-12-14T22:25:46Z",
                "pushed_at": "2022-12-14T15:17:31Z",
                "git_url": "git://github.com/boostorg/system.git",
                "ssh_url": "git@github.com:boostorg/system.git",
                "clone_url": "https://github.com/boostorg/system.git",
                "svn_url": "https://github.com/boostorg/system",
                "homepage": "http://boost.org/libs/system",
                "size": 852,
                "stargazers_count": 26,
                "watchers_count": 26,
                "language": "C++",
                "has_issues": True,
                "has_projects": False,
                "has_downloads": True,
                "has_wiki": False,
                "has_pages": False,
                "has_discussions": False,
                "forks_count": 82,
                "mirror_url": None,
                "archived": False,
                "disabled": False,
                "open_issues_count": 10,
                "license": None,
                "allow_forking": True,
                "is_template": False,
                "web_commit_signoff_required": False,
                "topics": [],
                "visibility": "public",
                "forks": 82,
                "open_issues": 10,
                "watchers": 26,
                "default_branch": "develop",
            },
        },
        "_links": {
            "self": {"href": "https://api.github.com/repos/boostorg/system/pulls/90"},
            "html": {"href": "https://github.com/boostorg/system/pull/90"},
            "issue": {"href": "https://api.github.com/repos/boostorg/system/issues/90"},
            "comments": {
                "href": "https://api.github.com/repos/boostorg/system/issues/90/comments"
            },
            "review_comments": {
                "href": "https://api.github.com/repos/boostorg/system/pulls/90/comments"
            },
            "review_comment": {
                "href": "https://api.github.com/repos/boostorg/system/pulls/comments{/number}"
            },
            "commits": {
                "href": "https://api.github.com/repos/boostorg/system/pulls/90/commits"
            },
            "statuses": {
                "href": "https://api.github.com/repos/boostorg/system/statuses/fe48c3058daaa31da6c50c316d63aa5f185dacb8"
            },
        },
        "author_association": "MEMBER",
        "auto_merge": None,
        "active_lock_reason": None,
    }


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
