from typing import NamedTuple, Optional

from django.urls import reverse

from mailing_list import constants
from mailing_list.models import SubscriptionStatus
from mailing_list.models import UserMailingListSubscription

_DEFAULT_LIST_ID = constants.MAILMAN_LISTS[0] if constants.MAILMAN_LISTS else ""


class SubscriptionState(NamedTuple):
    state: Optional[str]
    count: int
    email: Optional[str]


def get_subscription_state_count_and_email(user, list_ids) -> SubscriptionState:
    if not user.is_authenticated:
        return SubscriptionState(None, 0, None)

    subscriptions = UserMailingListSubscription.objects.filter(
        user=user, list_id__in=list_ids
    )
    pending_count = subscriptions.filter(status=SubscriptionStatus.PENDING).count()
    active_count = subscriptions.filter(status=SubscriptionStatus.ACTIVE).count()

    if pending_count > 0:
        email = (
            subscriptions.filter(status=SubscriptionStatus.PENDING)
            .values_list("email", flat=True)
            .first()
        )
        return SubscriptionState(SubscriptionStatus.PENDING, pending_count, email)
    elif active_count > 0:
        email = (
            subscriptions.filter(status=SubscriptionStatus.ACTIVE)
            .values_list("email", flat=True)
            .first()
        )
        return SubscriptionState(SubscriptionStatus.ACTIVE, active_count, email)
    else:
        return SubscriptionState(None, 0, None)


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
        context["mailing_list_card_modal_subscribe_url"] = reverse(
            "mailing-list-modal-subscribe"
        )
        context["mailing_list_card_list_id"] = _DEFAULT_LIST_ID
        context["mailing_list_card_lists"] = constants.MAILING_LIST_LABELS.values()

        if request.user.is_authenticated:
            managed_lists = set(constants.MAILMAN_LISTS)
            state = get_subscription_state_count_and_email(request.user, managed_lists)

            context["mailing_list_card_state"] = state.state
            context["mailing_list_card_subscription_count"] = state.count
            context["mailing_list_card_user_email"] = state.email
            context["mailing_list_card_manage_url"] = reverse("profile-account")
            context["mailing_list_card_subscribed_ids"] = set(
                UserMailingListSubscription.objects.filter(
                    user=request.user, list_id__in=managed_lists
                ).values_list("list_id", flat=True)
            )

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
