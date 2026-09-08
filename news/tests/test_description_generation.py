"""Daily cap on the AI description generation endpoints."""

from datetime import timedelta

import pytest
import waffle.testutils
from django.urls import reverse
from django.utils.html import escape
from model_bakery import baker

from ..constants import (
    BYPASS_DESCRIPTION_LIMIT_PERMISSION,
    DESCRIPTION_RATE_LIMIT_MESSAGE,
)
from ..models import (
    AIDescriptionSettings,
    DescriptionGenerationAttempt,
    DescriptionGenerationOutcome,
    DescriptionInputType,
)
from ..services import utc_day_start

pytestmark = pytest.mark.django_db


@pytest.fixture
def set_limit():
    """Sets the admin-editable daily limit."""

    def _set(value):
        settings_obj = AIDescriptionSettings.load()
        settings_obj.daily_limit = value
        settings_obj.save()
        return settings_obj

    return _set


@pytest.fixture
def spend(regular_user):
    """Records `count` generations already spent by a user today."""

    def _spend(count, user=None, outcome=DescriptionGenerationOutcome.SUCCESS):
        return baker.make(
            DescriptionGenerationAttempt,
            user=user or regular_user,
            input_type=DescriptionInputType.CONTENT,
            input_size=10,
            outcome=outcome,
            _quantity=count,
        )

    return _spend


@pytest.fixture
def generate(client, monkeypatch):
    """POSTs to the content generator with the model call stubbed out."""

    def _generate(summary="A generated description.", raises=False):
        def fake(*args, **kwargs):
            if raises:
                raise RuntimeError("upstream exploded")
            return summary

        monkeypatch.setattr("news.views.generate_summary", fake)
        return client.post(
            reverse("v3-news-generate-description"),
            {"title": "T", "content": "Some post body worth summarizing."},
        )

    return _generate


class TestQuotaEnforcement:
    def test_under_the_limit_succeeds_and_records_the_attempt(
        self, client, regular_user, set_limit, generate
    ):
        """A generation below the cap returns the summary and logs a SUCCESS."""
        set_limit(5)
        client.force_login(regular_user)

        response = generate()

        assert response.status_code == 200
        assert response.json()["description"] == "A generated description."
        attempt = DescriptionGenerationAttempt.objects.get(user=regular_user)
        assert attempt.outcome == DescriptionGenerationOutcome.SUCCESS
        assert attempt.input_type == DescriptionInputType.CONTENT
        assert attempt.input_size > 0

    def test_at_the_limit_returns_429_with_the_specified_copy(
        self, client, regular_user, set_limit, spend, generate
    ):
        """The user sees the ticket's copy, not a generic error."""
        set_limit(2)
        spend(2)
        client.force_login(regular_user)

        response = generate()

        assert response.status_code == 429
        body = response.json()
        assert body["error"] == DESCRIPTION_RATE_LIMIT_MESSAGE
        assert body["rate_limited"] is True

    def test_rejection_is_recorded_separately(
        self, client, regular_user, set_limit, spend, generate
    ):
        """Rejections are logged so the cap can be tuned from real usage."""
        set_limit(1)
        spend(1)
        client.force_login(regular_user)

        generate()

        assert DescriptionGenerationAttempt.objects.filter(
            user=regular_user, outcome=DescriptionGenerationOutcome.RATE_LIMITED
        ).exists()

    def test_rejections_do_not_consume_quota(
        self, client, regular_user, set_limit, spend, generate
    ):
        """A refused attempt never reached the model, so it must not count."""
        set_limit(2)
        spend(1)
        client.force_login(regular_user)
        baker.make(
            DescriptionGenerationAttempt,
            user=regular_user,
            input_type=DescriptionInputType.CONTENT,
            input_size=1,
            outcome=DescriptionGenerationOutcome.RATE_LIMITED,
            _quantity=5,
        )

        assert generate().status_code == 200

    def test_a_pending_attempt_still_consumes_quota(
        self, client, regular_user, set_limit, spend, generate
    ):
        """A request that died mid-flight left its reservation standing."""
        set_limit(1)
        spend(1, outcome=DescriptionGenerationOutcome.PENDING)
        client.force_login(regular_user)

        assert generate().status_code == 429

    def test_upstream_failure_still_consumes_quota(
        self, client, regular_user, set_limit, generate
    ):
        """The model call was made and billed, so it counts even when it fails."""
        set_limit(1)
        client.force_login(regular_user)

        response = generate(raises=True)

        assert response.status_code == 502
        attempt = DescriptionGenerationAttempt.objects.get(user=regular_user)
        assert attempt.outcome == DescriptionGenerationOutcome.UPSTREAM_ERROR
        assert generate().status_code == 429

    def test_yesterdays_attempts_do_not_count(
        self, client, regular_user, set_limit, spend, generate
    ):
        """The count resets at midnight UTC."""
        set_limit(1)
        client.force_login(regular_user)
        stale = spend(1)[0]
        DescriptionGenerationAttempt.objects.filter(pk=stale.pk).update(
            created_at=utc_day_start() - timedelta(minutes=1)
        )

        assert generate().status_code == 200

    def test_limit_change_applies_to_the_next_request(
        self, client, regular_user, set_limit, spend, generate
    ):
        """No deploy or restart: the new value is read per request."""
        set_limit(1)
        spend(1)
        client.force_login(regular_user)
        assert generate().status_code == 429

        set_limit(5)

        assert generate().status_code == 200

    def test_the_two_input_types_share_one_limit(
        self, client, regular_user, set_limit, spend, generate, monkeypatch
    ):
        """One cap covers body content and links, not one each."""
        set_limit(2)
        spend(2, outcome=DescriptionGenerationOutcome.SUCCESS)
        client.force_login(regular_user)
        monkeypatch.setattr("news.views.safe_get", _fake_safe_get)
        monkeypatch.setattr(
            "news.views.extract_article", lambda *a, **kw: ("Title", "Body text")
        )

        response = client.post(
            reverse("v3-news-generate-link-description"),
            {"url": "https://example.com/post"},
        )

        assert response.status_code == 429
        assert response.json()["error"] == DESCRIPTION_RATE_LIMIT_MESSAGE

    def test_a_spent_user_never_reaches_the_outbound_fetch(
        self, client, regular_user, set_limit, spend, monkeypatch
    ):
        """Otherwise the endpoint is an unmetered fetcher for anyone logged in."""
        set_limit(1)
        spend(1)
        client.force_login(regular_user)
        fetched = []
        monkeypatch.setattr(
            "news.views.safe_get",
            lambda *a, **kw: fetched.append(a) or _FakeResponse(),
        )

        response = client.post(
            reverse("v3-news-generate-link-description"),
            {"url": "https://example.com/post"},
        )

        assert response.status_code == 429
        assert fetched == []
        # Still recorded, so refusals before the fetch show in the usage figures.
        assert (
            DescriptionGenerationAttempt.objects.filter(
                user=regular_user,
                input_type=DescriptionInputType.LINK,
                outcome=DescriptionGenerationOutcome.RATE_LIMITED,
            ).count()
            == 1
        )


class TestExemptions:
    def test_superuser_is_exempt_but_still_logged(
        self, client, superuser, set_limit, spend, generate
    ):
        """Exempt users skip the cap; their spend still shows in the numbers."""
        set_limit(1)
        spend(3, user=superuser)
        client.force_login(superuser)

        assert generate().status_code == 200
        assert (
            DescriptionGenerationAttempt.objects.filter(
                user=superuser, outcome=DescriptionGenerationOutcome.SUCCESS
            ).count()
            == 4
        )

    def test_group_member_is_exempt(
        self, client, regular_user, set_limit, spend, generate, ratelimit_exempt_group
    ):
        """Membership of the seeded group lifts the cap."""
        set_limit(1)
        spend(3)
        regular_user.groups.add(ratelimit_exempt_group)
        client.force_login(regular_user)

        assert generate().status_code == 200

    def test_removing_the_user_from_the_group_restores_the_cap(
        self, client, regular_user, set_limit, spend, generate, ratelimit_exempt_group
    ):
        """Exemption is revocable without a deploy."""
        set_limit(1)
        spend(3)
        group = ratelimit_exempt_group
        regular_user.groups.add(group)
        client.force_login(regular_user)
        assert generate().status_code == 200

        regular_user.groups.remove(group)

        assert generate().status_code == 429

    def test_the_migration_grants_the_permission_to_the_group(
        self, ratelimit_exempt_group
    ):
        """Guards the post_migrate ordering trap in the seeding migration.

        The fixture runs the migration's own function, so this fails if the
        permission is ever looked up instead of created explicitly.
        """
        assert ratelimit_exempt_group.permissions.filter(
            codename=BYPASS_DESCRIPTION_LIMIT_PERMISSION
        ).exists()


class TestEndpointAccess:
    def test_anonymous_is_redirected_to_login(self, client):
        """The cap is not the only gate: the endpoint requires a session."""
        response = client.post(
            reverse("v3-news-generate-description"), {"content": "x"}
        )

        assert response.status_code == 302
        assert not DescriptionGenerationAttempt.objects.exists()

    def test_get_is_rejected(self, client, regular_user):
        """POST only, so a bare browser hit cannot spend a generation."""
        client.force_login(regular_user)

        response = client.get(reverse("v3-news-generate-description"))

        assert response.status_code == 405

    def test_missing_csrf_token_is_rejected(self, client, regular_user, set_limit):
        """A cross-origin script without the token gets nothing."""
        set_limit(5)
        client.force_login(regular_user)
        csrf_client = client.__class__(enforce_csrf_checks=True)
        csrf_client.force_login(regular_user)

        response = csrf_client.post(
            reverse("v3-news-generate-description"), {"content": "x"}
        )

        assert response.status_code == 403
        assert not DescriptionGenerationAttempt.objects.exists()

    def test_empty_content_is_rejected_without_spending_quota(
        self, client, regular_user, set_limit
    ):
        """Validation failures never reach the model, so they cost nothing."""
        set_limit(5)
        client.force_login(regular_user)

        response = client.post(reverse("v3-news-generate-description"), {"content": ""})

        assert response.status_code == 400
        assert not DescriptionGenerationAttempt.objects.exists()


class _FakeResponse:
    """Stands in for a `requests` response in the link-generator path."""

    text = "<html><body><p>Body text</p></body></html>"

    def raise_for_status(self):
        """No-op: the fake fetch always succeeds."""


def _fake_safe_get(*args, **kwargs):
    """Replaces the outbound fetch in the link generator."""
    return _FakeResponse()


class TestCreatePageState:
    """The create page's exhausted state, seeded from the server."""

    def get_page(self, client, user):
        """Renders the v3 create-post page as `user`, with the v3 flag on."""
        user.display_name = "Poster"
        user.save()
        client.force_login(user)
        with waffle.testutils.override_flag("v3", active=True):
            return client.get(reverse("v3-news-create"))

    def test_the_button_state_is_seeded_from_the_server(
        self, client, regular_user, set_limit
    ):
        """With generations left, the page renders unrestricted."""
        set_limit(5)

        response = self.get_page(client, regular_user)

        assert response.status_code == 200
        assert response.context["description_generation_limit_reached"] is False
        assert "rateLimited: false" in response.content.decode()

    def test_an_exhausted_user_gets_the_limit_message_on_load(
        self, client, regular_user, set_limit, spend
    ):
        """No button, and the specified copy, without waiting for a 429."""
        set_limit(1)
        spend(1)

        response = self.get_page(client, regular_user)

        content = response.content.decode()
        assert response.context["description_generation_limit_reached"] is True
        assert "rateLimited: true" in content
        # Django escapes the apostrophe in the copy on the way out.
        assert escape(DESCRIPTION_RATE_LIMIT_MESSAGE) in content

    def test_an_exempt_user_is_never_shown_as_limited(
        self, client, superuser, set_limit, spend
    ):
        """Exempt users keep the button however much they have generated."""
        set_limit(1)
        spend(5, user=superuser)

        response = self.get_page(client, superuser)

        assert response.context["description_generation_limit_reached"] is False
