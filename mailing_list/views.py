import datetime
import logging
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince
from django.views import View

from mailing_list import constants
from mailing_list.client import MailmanAPIError
from mailing_list.client import MailmanClient
from mailing_list.constants import MAILING_LIST_LABELS
from mailing_list.models import SubscriptionStatus
from mailing_list.models import UserMailingListSubscription

logger = logging.getLogger(__name__)

_CONFIRM_SALT = "mailing-list-confirm-a40b24dc-a26d-49ca-81d1-5b2fccb5fd7b"
_CONFIRM_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds


def _get_list_prefix(list_id: str) -> str:
    return list_id.split(".")[0]


def _is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _prg_redirect(request, **params) -> HttpResponseRedirect:
    """Redirect back to the referring page, with optional query params for card state.

    Strips the referer to path-only to prevent open-redirect issues.
    """
    referer = request.headers.get("referer", "/")
    path = urlparse(referer).path or "/"
    qs = urlencode({k: v for k, v in params.items() if v})
    return HttpResponseRedirect(f"{path}?{qs}" if qs else path)


def _format_duration(seconds: int) -> str:
    now = timezone.now()
    return timesince(now - datetime.timedelta(seconds=seconds), now, depth=1)


_SUBSCRIBE_RATE_LIMIT = 5
_SUBSCRIBE_RATE_WINDOW = 3600  # seconds


def _get_client_ip(request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _is_privileged(user) -> bool:
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def _rate_limit_key(request) -> str:
    if request.user.is_authenticated:
        return f"ml_rate:user:{request.user.pk}"
    return f"ml_rate:ip:{_get_client_ip(request)}"


def _is_rate_limited(request) -> bool:
    if _is_privileged(request.user):
        return False
    key = _rate_limit_key(request)
    cache.add(key, 0, timeout=_SUBSCRIBE_RATE_WINDOW)
    return cache.incr(key) > _SUBSCRIBE_RATE_LIMIT


def _subscribe_pending(
    request, user, email: str, list_ids: list[str]
) -> tuple[list[str], str | None]:
    """Create PENDING subscription records and send a confirmation email.

    Returns (succeeded, error_message). On email failure the records are
    rolled back and error_message is set; on partial IntegrityError the
    affected list is silently skipped.
    """
    succeeded = []
    for lid in list_ids:
        try:
            with transaction.atomic():
                UserMailingListSubscription.objects.update_or_create(
                    user=user,
                    list_id=lid,
                    defaults={"email": email, "status": SubscriptionStatus.PENDING},
                )
            succeeded.append(lid)
        except IntegrityError:
            pass

    if not succeeded:
        return [], None

    try:
        _send_confirmation_email(request, email, user.pk, succeeded)
    except Exception as exc:
        logger.error("Failed to send confirmation email to %s: %s", email, exc)
        UserMailingListSubscription.objects.filter(
            user=user, list_id__in=succeeded
        ).delete()
        return [], "Could not send confirmation email. Please try again."

    return succeeded, None


def _send_confirmation_email(
    request, email: str, user_id: int | None, list_ids: list[str]
) -> None:
    payload = {"email": email, "list_ids": list_ids}
    if user_id is not None:
        payload["user_id"] = user_id

    token = signing.dumps(payload, salt=_CONFIRM_SALT)
    confirm_url = request.build_absolute_uri(
        reverse("mailing-list-confirm", args=[token])
    )
    lists = []
    for lid in list_ids:
        entry = MAILING_LIST_LABELS.get(_get_list_prefix(lid))
        if entry:
            lists.append(entry)
        else:
            lists.append({"name": lid, "address": lid, "description": None})
    message = render_to_string(
        "v3/mailing_list/email/confirm_subscription.txt",
        {
            "email": email,
            "lists": lists,
            "confirm_url": confirm_url,
            "expiry_label": _format_duration(_CONFIRM_MAX_AGE),
        },
    )
    send_mail(
        subject="Confirm your Boost mailing list subscription",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


"""
This view is currently only being used in the demo page. This will later have to be adapted to be reused
in the multi-selection modals.
"""


class SubscribeView(LoginRequiredMixin, View):
    def post(self, request):
        email = request.POST.get("email", "").strip()
        if not email:
            return render(
                request,
                "v3/mailing_list/_subscribe_result.html",
                {"error": "Email is required."},
            )

        managed_lists = set(constants.MAILMAN_LISTS)
        requested = set(request.POST.getlist("list_id")) & managed_lists
        current = set(
            UserMailingListSubscription.objects.filter(
                user=request.user, list_id__in=managed_lists
            ).values_list("list_id", flat=True)
        )

        to_subscribe = requested - current
        to_unsubscribe = current - requested

        pending = []
        unsubscribed = []
        errors = []

        for list_id in to_subscribe:
            try:
                with transaction.atomic():
                    UserMailingListSubscription.objects.update_or_create(
                        user=request.user,
                        list_id=list_id,
                        defaults={"email": email, "status": SubscriptionStatus.PENDING},
                    )
            except IntegrityError:
                errors.append(list_id)
                continue
            pending.append(list_id)

        if pending:
            try:
                _send_confirmation_email(request, email, request.user.pk, pending)
            except Exception as exc:
                logger.error("Failed to send confirmation email to %s: %s", email, exc)
                UserMailingListSubscription.objects.filter(
                    user=request.user, list_id__in=pending
                ).delete()
                return render(
                    request,
                    "v3/mailing_list/_subscribe_result.html",
                    {"error": "Could not send confirmation email. Please try again."},
                )

        for list_id in to_unsubscribe:
            sub = UserMailingListSubscription.objects.filter(
                user=request.user, list_id=list_id
            ).first()
            if sub and sub.status == SubscriptionStatus.PENDING:
                sub.delete()
                unsubscribed.append(list_id)
                continue
            try:
                MailmanClient().unsubscribe(email, list_id)
                UserMailingListSubscription.objects.filter(
                    user=request.user, list_id=list_id
                ).delete()
                unsubscribed.append(list_id)
            except MailmanAPIError as exc:
                logger.error(
                    "Mailman unsubscribe error for %s/%s: %s", email, list_id, exc
                )
                errors.append(list_id)

        return render(
            request,
            "v3/mailing_list/_subscribe_result.html",
            {
                "pending": pending,
                "unsubscribed": unsubscribed,
                "errors": errors,
                "email": email,
            },
        )


"""
This will be partially deprecated once multi-selection modals are implemented.
Although multi-selection modals will take care of the sub/unsub logic, this view still shows how you'd
want to set the _mailing_list_card.html state to show the 'pending' or 'subscribed' status.
"""


def _build_card_context(request) -> dict:
    """Build the base context dict for rendering _mailing_list_card.html."""
    managed_lists = set(constants.MAILMAN_LISTS)
    ctx = {
        "subscribe_url": reverse("mailing-list-quick-subscribe"),
        "modal_subscribe_url": reverse("mailing-list-modal-subscribe"),
        "login_url": reverse("account_login"),
        "mailing_lists": constants.MAILING_LIST_LABELS.values(),
        "subscribed_ids": set(),
    }
    if request.user.is_authenticated:
        ctx["subscribed_ids"] = set(
            UserMailingListSubscription.objects.filter(
                user=request.user, list_id__in=managed_lists
            ).values_list("list_id", flat=True)
        )
    return ctx


class QuickSubscribeView(View):
    """Subscribe to a single list. Works for both authenticated and anonymous users.

    Authenticated flow: tracks subscription state in UserMailingListSubscription.
    Anonymous flow: stateless — sends a confirmation email and calls Mailman on confirm.
    """

    def _card(self, request, **ctx):
        return render(
            request,
            "v3/includes/_mailing_list_card.html",
            {**_build_card_context(request), **ctx},
        )

    def post(self, request):
        email = request.POST.get("email", "").strip()
        managed_lists = set(constants.MAILMAN_LISTS)
        list_id = request.POST.get("list_id", "").strip()

        if not email:
            if _is_htmx(request):
                return self._card(
                    request,
                    state="error",
                    error_message="Email is required.",
                    list_id=list_id,
                )
            return _prg_redirect(
                request, ml_state="error", ml_error="Email is required."
            )

        if list_id not in managed_lists:
            if _is_htmx(request):
                return self._card(
                    request,
                    state="error",
                    error_message="Invalid mailing list.",
                    user_email=email,
                    list_id=list_id,
                )
            return _prg_redirect(
                request,
                ml_state="error",
                ml_error="Invalid mailing list.",
                ml_email=email,
            )

        if _is_rate_limited(request):
            if _is_htmx(request):
                return self._card(
                    request,
                    state="error",
                    error_message="Too many attempts. Please try again later.",
                    user_email=email,
                    list_id=list_id,
                )
            return _prg_redirect(
                request,
                ml_state="error",
                ml_error="Too many attempts. Please try again later.",
                ml_email=email,
            )

        if request.user.is_authenticated:
            return self._handle_authenticated(request, email, list_id, managed_lists)
        return self._handle_anonymous(request, email, list_id)

    def _handle_authenticated(self, request, email, list_id, managed_lists):
        existing = UserMailingListSubscription.objects.filter(
            user=request.user, list_id=list_id
        ).first()

        manage_url = reverse("profile-account")

        if existing:
            if existing.status == SubscriptionStatus.PENDING:
                if _is_htmx(request):
                    return self._card(
                        request,
                        state="pending",
                        user_email=existing.email,
                        list_id=list_id,
                        manage_url=manage_url,
                    )
                return _prg_redirect(request)
            subscription_count = UserMailingListSubscription.objects.filter(
                user=request.user, list_id__in=managed_lists
            ).count()
            if _is_htmx(request):
                return self._card(
                    request,
                    state="active",
                    user_email=existing.email,
                    subscription_count=subscription_count,
                    manage_url=manage_url,
                )
            return _prg_redirect(request)

        try:
            with transaction.atomic():
                UserMailingListSubscription.objects.create(
                    user=request.user,
                    list_id=list_id,
                    email=email,
                    status=SubscriptionStatus.PENDING,
                )
        except IntegrityError:
            if _is_htmx(request):
                return self._card(
                    request,
                    state="error",
                    error_message="This email is already registered for this list by another account.",
                    user_email=email,
                    list_id=list_id,
                )
            return _prg_redirect(
                request,
                ml_state="error",
                ml_error="This email is already registered for this list by another account.",
                ml_email=email,
            )

        try:
            _send_confirmation_email(request, email, request.user.pk, [list_id])
        except Exception as exc:
            logger.error(
                "Failed to send confirmation email to %s...: %s", email[:3], exc
            )
            UserMailingListSubscription.objects.filter(
                user=request.user, list_id=list_id
            ).delete()
            if _is_htmx(request):
                return self._card(
                    request,
                    state="error",
                    error_message="Could not send confirmation email. Please try again.",
                    user_email=email,
                    list_id=list_id,
                )
            return _prg_redirect(
                request,
                ml_state="error",
                ml_error="Could not send confirmation email. Please try again.",
                ml_email=email,
            )

        if _is_htmx(request):
            return self._card(
                request,
                state="pending",
                user_email=email,
                list_id=list_id,
                manage_url=manage_url,
            )
        return _prg_redirect(request)

    def _handle_anonymous(self, request, email, list_id):
        try:
            if MailmanClient().is_confirmed(email, list_id):
                if _is_htmx(request):
                    return self._card(
                        request,
                        state="error",
                        error_message=f"{email} is already subscribed to this list.",
                        user_email=email,
                        list_id=list_id,
                    )
                return _prg_redirect(
                    request,
                    ml_state="error",
                    ml_error=f"{email} is already subscribed to this list.",
                    ml_email=email,
                )
        except MailmanAPIError:
            pass  # can't determine — proceed and let Mailman handle it on confirm

        try:
            _send_confirmation_email(request, email, None, [list_id])
        except Exception as exc:
            logger.error("Failed to send confirmation email to %s: %s", email, exc)
            if _is_htmx(request):
                return self._card(
                    request,
                    state="error",
                    error_message="Could not send confirmation email. Please try again.",
                    user_email=email,
                    list_id=list_id,
                )
            return _prg_redirect(
                request,
                ml_state="error",
                ml_error="Could not send confirmation email. Please try again.",
                ml_email=email,
            )

        if _is_htmx(request):
            return self._card(
                request, state="pending", user_email=email, list_id=list_id
            )
        return _prg_redirect(request, ml_state="pending", ml_email=email)


class ConfirmSubscriptionView(View):
    def get(self, request, token):
        try:
            data = signing.loads(token, salt=_CONFIRM_SALT, max_age=_CONFIRM_MAX_AGE)
        except signing.BadSignature:
            return render(
                request,
                "v3/mailing_list/confirm_invalid.html",
                {
                    "home_url": "/",
                    "expiry_label": _format_duration(_CONFIRM_MAX_AGE),
                },
                status=400,
            )

        email = data.get("email")
        list_ids = data.get("list_ids", [])
        user_id = data.get("user_id")  # absent for anonymous subscriptions

        user = None
        if user_id is not None:
            User = get_user_model()
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return render(
                    request,
                    "v3/mailing_list/confirm_invalid.html",
                    {
                        "home_url": "/",
                        "expiry_label": _format_duration(_CONFIRM_MAX_AGE),
                    },
                    status=400,
                )

        confirmed = []
        errors = []

        for list_id in list_ids:
            try:
                MailmanClient().subscribe(email, list_id)
                if user is not None:
                    UserMailingListSubscription.objects.filter(
                        user=user, list_id=list_id
                    ).update(status=SubscriptionStatus.ACTIVE)
                confirmed.append(list_id)
            except MailmanAPIError as exc:
                logger.error(
                    "Mailman subscribe error during confirmation for %s/%s: %s",
                    email,
                    list_id,
                    exc,
                )
                errors.append(list_id)

        def _label(list_id):
            entry = MAILING_LIST_LABELS.get(_get_list_prefix(list_id))
            if entry:
                return {"name": entry["name"], "address": entry["address"]}
            return {"name": list_id, "address": None}

        return render(
            request,
            "v3/mailing_list/confirm_success.html",
            {
                "email": email,
                "confirmed": [_label(lid) for lid in confirmed],
                "errors": [_label(lid) for lid in errors],
                "home_url": "/",
            },
        )


class ModalSubscribeView(View):
    """Subscribe to one or more lists via the list-selection modal.

    Accepts email + one or more list_id POST values. Works for both authenticated
    and anonymous users. Only reachable via HTMX (the modal is Alpine-only).

    Authenticated flow: subscribes to newly checked lists and unsubscribes from
    any currently tracked lists that were unchecked.
    Anonymous flow: subscribe-only - sends a single confirmation email for all
    checked lists. Unsubscribe not supported for anonymous users.
    """

    def _card(self, request, **ctx):
        return render(
            request,
            "v3/includes/_mailing_list_card.html",
            {**_build_card_context(request), **ctx},
        )

    def post(self, request):
        email = request.POST.get("email", "").strip()
        managed_lists = set(constants.MAILMAN_LISTS)
        list_ids = [
            lid for lid in request.POST.getlist("list_id") if lid in managed_lists
        ]

        if not email:
            return self._card(
                request, state="error", error_message="Email is required."
            )

        if _is_rate_limited(request):
            return self._card(
                request,
                state="error",
                error_message="Too many attempts. Please try again later.",
                user_email=email,
            )

        if request.user.is_authenticated:
            return self._handle_authenticated(request, email, list_ids, managed_lists)
        return self._handle_anonymous(request, email, list_ids)

    def _handle_authenticated(self, request, email, list_ids, managed_lists):
        manage_url = reverse("profile-account")

        current_subs = {
            sub.list_id: sub
            for sub in UserMailingListSubscription.objects.filter(
                user=request.user, list_id__in=managed_lists
            )
        }
        to_subscribe = [lid for lid in list_ids if lid not in current_subs]
        to_unsubscribe = [lid for lid in current_subs if lid not in list_ids]

        for lid in to_unsubscribe:
            sub = current_subs[lid]
            if sub.status == SubscriptionStatus.PENDING:
                sub.delete()
            else:
                try:
                    MailmanClient().unsubscribe(sub.email, lid)
                    UserMailingListSubscription.objects.filter(
                        user=request.user, list_id=lid
                    ).delete()
                except MailmanAPIError as exc:
                    logger.error(
                        "Mailman unsubscribe error for %s/%s: %s", sub.email, lid, exc
                    )

        if not to_subscribe:
            subscription_count = UserMailingListSubscription.objects.filter(
                user=request.user, list_id__in=managed_lists
            ).count()
            if subscription_count == 0:
                return self._card(request, user_email=email)
            return self._card(
                request,
                state="active",
                user_email=email,
                subscription_count=subscription_count,
                manage_url=manage_url,
            )

        succeeded, error = _subscribe_pending(
            request, request.user, email, to_subscribe
        )

        if error:
            return self._card(
                request, state="error", error_message=error, user_email=email
            )

        if not succeeded:
            return self._card(
                request,
                state="error",
                error_message="Could not subscribe. Please try again.",
                user_email=email,
            )

        return self._card(
            request,
            state="pending",
            user_email=email,
            manage_url=manage_url,
        )

    def _handle_anonymous(self, request, email, list_ids):
        if not list_ids:
            return self._card(
                request,
                state="error",
                error_message="Please select at least one mailing list.",
                user_email=email,
            )

        try:
            _send_confirmation_email(request, email, None, list_ids)
        except Exception as exc:
            logger.error("Failed to send confirmation email to %s: %s", email, exc)
            return self._card(
                request,
                state="error",
                error_message="Could not send confirmation email. Please try again.",
                user_email=email,
            )

        return self._card(request, state="pending", user_email=email)


class PostAuthSubscribeView(LoginRequiredMixin, View):
    """Subscribe to one or more lists from the post-login homepage modal.

    Only for authenticated users. Returns an empty fragment so HTMX removes
    the modal from the DOM. Falls back to a homepage redirect for non-HTMX.
    """

    def post(self, request):
        email = (request.POST.get("email") or "").strip() or request.user.email
        managed_lists = set(constants.MAILMAN_LISTS)
        list_ids = [
            lid for lid in request.POST.getlist("list_id") if lid in managed_lists
        ]

        if list_ids and not _is_rate_limited(request):
            current = {
                sub.list_id
                for sub in UserMailingListSubscription.objects.filter(
                    user=request.user, list_id__in=managed_lists
                )
            }
            to_subscribe = [lid for lid in list_ids if lid not in current]

            _subscribe_pending(request, request.user, email, to_subscribe)

        if _is_htmx(request):
            return HttpResponse("")
        return _prg_redirect(request)
