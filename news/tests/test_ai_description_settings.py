"""The admin-editable AI description limit, its validation, audit and usage."""

from datetime import timedelta

import pytest
from django.urls import reverse
from model_bakery import baker
from wagtail.contrib.settings.views import get_setting_edit_handler
from wagtail.log_actions import registry as log_registry

from ..constants import AI_DESCRIPTION_LIMIT_CHANGED_ACTION, DAILY_LIMIT_MIN_MESSAGE
from ..models import (
    AIDescriptionSettings,
    DescriptionGenerationAttempt,
    DescriptionGenerationOutcome,
    DescriptionInputType,
)
from ..panels import AIDescriptionUsagePanel
from ..services import description_generation_usage_today, utc_day_start

pytestmark = pytest.mark.django_db


def build_form(data, instance=None, for_user=None):
    """The settings form exactly as the Wagtail edit view builds it.

    `AIDescriptionSettingsForm` is a `base_form_class`, so Wagtail composes the
    real form class from the panels; instantiating the base directly would miss
    the model binding.
    """
    instance = instance or AIDescriptionSettings.load()
    form_class = get_setting_edit_handler(AIDescriptionSettings).get_form_class()
    return form_class(data, instance=instance, for_user=for_user)


def make_attempt(user, outcome, **kwargs):
    """One attempt row for the current UTC day."""
    return baker.make(
        DescriptionGenerationAttempt,
        user=user,
        input_type=DescriptionInputType.CONTENT,
        input_size=10,
        outcome=outcome,
        **kwargs,
    )


class TestValidation:
    @pytest.mark.parametrize("value", [0, -1])
    def test_non_positive_limits_are_rejected(self, value):
        """A limit of 0 reads as "disabled" but would lock everyone out.

        Both values get the same guidance: the generated form field would
        otherwise stop at 0 and refuse -1 in Django's default wording.
        """
        form = build_form({"daily_limit": value})

        assert not form.is_valid()
        assert form.errors["daily_limit"] == [DAILY_LIMIT_MIN_MESSAGE]

    def test_a_positive_limit_is_accepted(self):
        """The happy path still saves."""
        form = build_form({"daily_limit": 30})

        assert form.is_valid(), form.errors
        assert form.save().daily_limit == 30


class TestAuditTrail:
    def test_a_change_records_who_what_and_when(self, superuser):
        """Wagtail logs no field values for settings, so the form logs them."""
        instance = AIDescriptionSettings.load()
        form = build_form({"daily_limit": 42}, instance=instance, for_user=superuser)
        assert form.is_valid(), form.errors

        form.save()

        entry = (
            log_registry.get_logs_for_instance(instance)
            .filter(action=AI_DESCRIPTION_LIMIT_CHANGED_ACTION)
            .first()
        )
        assert entry.user == superuser
        assert entry.data["daily_limit"] == {"old": 20, "new": 42}
        assert entry.timestamp is not None

    def test_saving_an_unchanged_value_records_nothing(self, superuser):
        """Only real changes belong in the trail."""
        instance = AIDescriptionSettings.load()
        form = build_form(
            {"daily_limit": instance.daily_limit},
            instance=instance,
            for_user=superuser,
        )
        assert form.is_valid(), form.errors

        form.save()

        assert not (
            log_registry.get_logs_for_instance(instance)
            .filter(action=AI_DESCRIPTION_LIMIT_CHANGED_ACTION)
            .exists()
        )


class TestUsageFigures:
    def test_counts_todays_generations_and_users_at_the_cap(
        self, regular_user, moderator_user
    ):
        """The two numbers the admin screen has to show."""
        make_attempt(regular_user, DescriptionGenerationOutcome.SUCCESS)
        make_attempt(regular_user, DescriptionGenerationOutcome.UPSTREAM_ERROR)
        make_attempt(regular_user, DescriptionGenerationOutcome.RATE_LIMITED)
        make_attempt(regular_user, DescriptionGenerationOutcome.RATE_LIMITED)
        make_attempt(moderator_user, DescriptionGenerationOutcome.RATE_LIMITED)

        usage = description_generation_usage_today()

        # Rejections never reached the model, so they are not generations.
        assert usage["generations"] == 2
        # Rejections collapse per user: regular_user's two count once, plus
        # moderator_user.
        assert usage["users_at_limit"] == 2

    def test_yesterdays_rows_are_excluded(self, regular_user):
        """Figures cover the current UTC day only."""
        stale = make_attempt(regular_user, DescriptionGenerationOutcome.SUCCESS)
        DescriptionGenerationAttempt.objects.filter(pk=stale.pk).update(
            created_at=utc_day_start() - timedelta(seconds=1)
        )

        assert description_generation_usage_today()["generations"] == 0


class TestUsagePanel:
    def test_the_panel_reports_usage_and_recent_changes(self, superuser):
        """Usage and history render on the edit screen itself."""
        instance = AIDescriptionSettings.load()
        form = build_form({"daily_limit": 7}, instance=instance, for_user=superuser)
        assert form.is_valid(), form.errors
        form.save()
        make_attempt(superuser, DescriptionGenerationOutcome.SUCCESS)

        panel = AIDescriptionUsagePanel().bind_to_model(AIDescriptionSettings)
        bound = panel.get_bound_panel(instance=instance, request=None, form=form)
        context = bound.get_context_data()

        assert context["usage"]["generations"] == 1
        assert [e.data["daily_limit"]["new"] for e in context["recent_changes"]] == [7]


class TestSettingsScreen:
    def test_the_cms_edit_screen_renders_the_limit_and_usage(self, client, superuser):
        """Smoke test: a template error in the panel would only show here."""
        make_attempt(superuser, DescriptionGenerationOutcome.SUCCESS)
        client.force_login(superuser)

        response = client.get(
            reverse("wagtailsettings:edit", args=["news", "aidescriptionsettings"]),
            follow=True,
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "daily_limit" in content
        assert "generation so far today" in content

    def test_a_user_without_the_permission_cannot_reach_it(self, client, regular_user):
        """Admin-only: the screen is permission gated, not just unlinked."""
        client.force_login(regular_user)

        response = client.get(
            reverse("wagtailsettings:edit", args=["news", "aidescriptionsettings"]),
            follow=True,
        )

        # Bounced to the CMS login rather than shown the setting.
        assert response.redirect_chain
        assert "daily_limit" not in response.content.decode()
