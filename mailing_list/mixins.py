from typing import Union, Tuple

from django.conf import settings
from django.urls import reverse

from mailing_list.models import SubscriptionStatus
from mailing_list.models import UserMailingListSubscription

_DEFAULT_LIST_ID = "boost.lists.boost.org"


def get_subscription_state_count_and_email(
    user, list_ids
) -> Tuple[Union[str, None], int, Union[str, None]]:
    """Return the subscription state for a single user/list pair.

    Returns:
        "pending"  — a subscription record exists with PENDING status
        "active"   — a subscription record exists with ACTIVE status
        None       — user is not authenticated or has no subscription for list_id
    """
    if not user.is_authenticated:
        return None, 0, None

    subscriptions = list(
        UserMailingListSubscription.objects.filter(user=user, list_id__in=list_ids)
    )

    pending_subs = [
        sub for sub in subscriptions if sub.status == SubscriptionStatus.PENDING
    ]
    pending_count = len(pending_subs)

    active_subs = [
        sub for sub in subscriptions if sub.status == SubscriptionStatus.ACTIVE
    ]
    active_count = len(active_subs)

    if pending_count > 0:
        return SubscriptionStatus.PENDING, pending_count, subscriptions[0].email
    elif active_count > 0:
        return SubscriptionStatus.ACTIVE, active_count, subscriptions[0].email
    else:
        return None, 0, None


class MailingListCardMixin:
    """Injects mailing-list card context into any class-based view.

    Adds the variables needed by v3/includes/_mailing_list_card.html:
      mailing_list_card_subscribe_url
      mailing_list_card_list_id
      mailing_list_card_state              ("pending", "active", "error", or None)
      mailing_list_card_error_message      (set on error state, used by no-JS PRG flow)
      mailing_list_card_user_email         (authenticated users only, or from PRG params)
      mailing_list_card_manage_url         (authenticated users only)
      mailing_list_card_subscription_count (authenticated users only — ACTIVE count only)
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        context["mailing_list_card_subscribe_url"] = reverse(
            "mailing-list-quick-subscribe"
        )
        context["mailing_list_card_list_id"] = _DEFAULT_LIST_ID

        if request.user.is_authenticated:
            managed_lists = set(settings.MAILMAN_LISTS)
            state = get_subscription_state_count_and_email(request.user, managed_lists)

            context["mailing_list_card_state"] = state[0]
            context["mailing_list_card_subscription_count"] = state[1]
            context["mailing_list_card_user_email"] = state[2]
            context["mailing_list_card_manage_url"] = reverse("profile-account")

        # URL-param overrides for the no-JS PRG flow.
        # Error state always wins (DB record was rolled back on failure).
        # Anonymous pending has no DB record so the URL param is the only source.
        ml_state_param = request.GET.get("ml_state")
        if ml_state_param == "error":
            context["mailing_list_card_state"] = "error"
            context["mailing_list_card_error_message"] = request.GET.get("ml_error", "")
            context["mailing_list_card_user_email"] = request.GET.get("ml_email", "")
        elif ml_state_param == "pending" and not request.user.is_authenticated:
            context["mailing_list_card_state"] = "pending"
            context["mailing_list_card_user_email"] = request.GET.get("ml_email", "")

        return context
