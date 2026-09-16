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


def is_verified_email_for_user(user, email: str) -> bool:
    """True if `email` is already proven to belong to this user elsewhere on the
    site - their account email, or a commit-author email they've verified via the
    claim flow. A subscription to an already-verified address doesn't need its own
    double opt-in: the ownership check that confirmation email exists to perform
    has already happened.
    """
    if not user.is_authenticated or not email:
        return False
    email = email.strip().lower()
    if user.email and user.email.strip().lower() == email:
        return True

    # Local import: libraries.models imports mailing_list.models at module level,
    # so importing libraries.models back at mixins.py's module level would risk a
    # circular import during app loading.
    from libraries.models import CommitAuthorEmail

    return CommitAuthorEmail.objects.filter(
        claimed_by=user, claim_verified=True, email__iexact=email
    ).exists()


def has_active_subscription(user, list_ids) -> bool:
    """True if the user already has at least one ACTIVE (confirmed) subscription
    among list_ids. Used to distinguish "verify ownership of this address" (which
    only makes sense before the user has proven they own any address at all) from
    a returning subscriber adding one more list to an address already confirmed.
    """
    if not user.is_authenticated:
        return False
    return UserMailingListSubscription.objects.filter(
        user=user, list_id__in=list_ids, status=SubscriptionStatus.ACTIVE
    ).exists()


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
      mailing_list_card_user_email         (the subscription email if one exists, else the
                                            account email; authenticated users only, or
                                            from PRG params)
      mailing_list_card_manage_url         (authenticated users only)
      mailing_list_card_subscription_count (authenticated users only — ACTIVE count only)
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_mailing_list_card_context())
        return context

    def get_mailing_list_card_context(self) -> dict:
        """Build the card context once per request.

        V3Mixin.get_context_data() re-enters self.get_context_data(), so any view
        combining both mixins would otherwise run these queries twice per request.
        """
        if not hasattr(self, "_mailing_list_card_context"):
            self._mailing_list_card_context = self._build_mailing_list_card_context()
        return self._mailing_list_card_context

    def _build_mailing_list_card_context(self) -> dict:
        request = self.request
        context = {
            "mailing_list_card_subscribe_url": reverse("mailing-list-quick-subscribe"),
            "mailing_list_card_modal_subscribe_url": reverse(
                "mailing-list-modal-subscribe"
            ),
            "mailing_list_card_list_id": _DEFAULT_LIST_ID,
            "mailing_list_card_lists": constants.MAILING_LIST_LABELS.values(),
        }

        if request.user.is_authenticated:
            managed_lists = set(constants.MAILMAN_LISTS)
            state = get_subscription_state_count_and_email(request.user, managed_lists)

            context["mailing_list_card_state"] = state.state
            context["mailing_list_card_subscription_count"] = state.count
            context["mailing_list_card_user_email"] = state.email or request.user.email
            context["mailing_list_card_manage_url"] = reverse("profile-account")
            context["mailing_list_card_has_active_subscription"] = (
                state.state == SubscriptionStatus.PENDING
                and has_active_subscription(request.user, managed_lists)
            )
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
