import waffle.testutils
from django.core.cache import cache
from django.urls import reverse
from model_bakery import baker
from users.models import GithubActivity


@waffle.testutils.override_flag("v3", active=True)
def test_profile_page_renders_activity_card(client, user, db, settings):
    cache.clear()
    # allauth resolves the provider app when rendering the connections list,
    # so the page needs a SocialApp even though this test is about the card.
    from django.contrib.sites.models import Site
    from allauth.socialaccount.models import SocialApp

    app = SocialApp.objects.create(
        provider="github", name="GitHub", client_id="x", secret="y"
    )
    app.sites.add(Site.objects.get_current())
    baker.make(
        "socialaccount.SocialAccount",
        user=user,
        provider="github",
        extra_data={"login": "testuser"},
    )
    user.github_username = "testuser"
    user.save()
    GithubActivity.upsert_for_user(
        user,
        {
            "total_commits": 24,
            "commit_repo_count": 7,
            "featured_pr": {
                "repo": "boostorg/url",
                "url": "https://github.com/boostorg/url/pull/932",
                "comment_count": 6,
            },
        },
    )
    client.force_login(user)

    resp = client.get(reverse("profile-account"))
    html = resp.content.decode()

    assert resp.status_code == 200
    assert 'id="github-activity-card"' in html
    assert "Created 24 Commits" in html
    assert "boostorg/url" in html
    # the hardcoded placeholder card is gone
    assert "cppalliance/buffers" not in html
