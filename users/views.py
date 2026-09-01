import datetime

from allauth.account import app_settings
from allauth.socialaccount.adapter import get_adapter, DefaultSocialAccountAdapter
from allauth.socialaccount.forms import DisconnectForm
from allauth.socialaccount.models import SocialApp
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import auth
from django.contrib.messages.views import SuccessMessageMixin
from django.http import (
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, FormView, View
from django.views.generic.base import TemplateView
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django import forms

from allauth.account.forms import ChangePasswordForm, ResetPasswordForm
from allauth.account.views import (
    LoginView,
    SignupView,
    EmailVerificationSentView,
    PasswordResetView,
    PasswordResetFromKeyView,
)
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.views import SignupView as SocialSignupView

from rest_framework import generics
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny

from waffle import flag_is_active

from badges import display as badge_display
from core.context_processors import edit_profile_url
from core.mixins import V3Mixin, V3AuthContextMixin
from libraries.constants import (
    COMMIT_EMAIL_ADD_FAILED_ERROR,
    COMMIT_EMAIL_STALE_ACTION_ERROR,
)
from libraries.forms import V3CommitAuthorEmailForm
from libraries.models import CommitAuthorEmail
from mailing_list.mixins import MailingListCardMixin
from .forms import (
    PreferencesForm,
    UserProfileForm,
    UserProfilePhotoForm,
    DeleteAccountForm,
    V3UserProfileForm,
    CustomSignUpForm,
    SLACK_PROFILE_URL_PREFIX,
)
from .mixins import V3UserProfileContextMixin
from .models import (
    NO_PUBLIC_ROLE_OPTION,
    User,
    UserProfileRoutingKey,
    encode_role_option,
)
from .password_rules import build_password_rules
from .permissions import CustomUserPermissions
from .profile_cards import github_activity_card_context
from .serializers import UserSerializer, FullUserSerializer, CurrentUserSerializer
from . import tasks


class UserViewSet(viewsets.ModelViewSet):
    """
    Main User API ViewSet
    """

    queryset = User.objects.all()
    permission_classes = [CustomUserPermissions]

    def get_serializer_class(self):
        """Pick the right serializer based on the user"""
        if self.request.user.is_staff or self.request.user.is_superuser:
            return FullUserSerializer
        else:
            return UserSerializer


class CurrentUserAPIView(generics.RetrieveUpdateAPIView):
    """
    This gives the current user a convenient way to retrieve or
    update slightly more detailed information about themselves.

    Typically set to a route of `/api/v1/users/me`
    """

    serializer_class = CurrentUserSerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer: CurrentUserSerializer):
        instance: User = serializer.save()
        # Only allow for image deletion if the user is allowed to update their image.
        if (
            self.request.POST.get("delete_profile_image", "").lower() == "true"
            and instance.can_update_image
        ):
            instance.profile_image.delete()
            instance.image_uploaded = False
            instance.save()

    def get_object(self):
        return self.request.user


class PublicUserProfileView(V3UserProfileContextMixin, V3Mixin, DetailView):
    """Another user's profile page, at /users/<routing-key>/.

    V3-only: with no `template_name`, `V3Mixin` 404s the route while the v3
    flag is off. Deactivated accounts (which is what account deletion leaves
    behind) 404 rather than staying publicly reachable."""

    model = User
    v3_template_name = "v3/user_profile_page.html"
    # Not the default "user": that would shadow the request user the site
    # chrome (header avatar, nav) renders from.
    context_object_name = "profile_user"

    def get(self, request, *args, **kwargs):
        self.requested_key = get_object_or_404(
            UserProfileRoutingKey.objects.select_related("user"),
            routing_key=kwargs["routing_key"],
            user__is_active=True,
        )
        # Superseded keys are kept rather than deleted, so one still resolves to
        # its owner. Redirect it instead of serving the same profile at two
        # URLs, which is also what makes a shared link survive a rename.
        canonical = self.requested_key.user.profile_routing_key
        if canonical is not None and canonical.pk != self.requested_key.pk:
            return HttpResponsePermanentRedirect(
                self.requested_key.user.get_absolute_url()
            )
        return super().get(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.requested_key.user

    def get_v3_context_data(self, **kwargs):
        context = super().get_v3_context_data(**kwargs)
        context.update(self.get_v3_public_context(self.object))
        return context


class GithubActivityFragmentView(TemplateView):
    """Re-render just the GitHub activity card for one profile.

    Polled by the card itself while a background refresh runs, so the numbers
    appear without the user reloading. Read-only: it renders whatever is stored
    and never waits on GitHub.

    Keyed by routing key rather than the logged-in user: the card now appears
    on public profiles, so a visitor polling must get the numbers of the
    profile they are looking at, not their own. No login required, for the
    same reason.
    """

    template_name = "v3/includes/_github_activity_card.html"

    def get_context_data(self, **kwargs):
        # Deactivated accounts 404 here as they do on the profile page, so the
        # fragment cannot serve a profile the page itself refuses to.
        key = get_object_or_404(
            UserProfileRoutingKey.objects.select_related("user"),
            routing_key=self.kwargs["routing_key"],
            user__is_active=True,
        )
        try:
            attempt = int(self.request.GET.get("attempt", 0))
        except ValueError:
            attempt = 0
        return github_activity_card_context(key.user, attempt=attempt)


class CurrentUserProfileView(
    V3UserProfileContextMixin,
    MailingListCardMixin,
    V3Mixin,
    LoginRequiredMixin,
    SuccessMessageMixin,
    TemplateView,
):
    template_name = "users/profile.html"
    success_message = "Your profile was successfully updated."
    success_url = reverse_lazy("profile-account")
    v3_template_name = "v3/user_profile_page.html"
    v3_edit_template_name = "v3/user_profile_edit.html"

    def dispatch(self, request, *args, **kwargs):
        # V3Mixin.dispatch() renders unconditionally (for every HTTP method)
        # whenever the v3 flag is active, so it never reaches
        # LoginRequiredMixin's check, nor post(). This page always requires
        # login, so enforce that first, then route v3 POSTs to post()
        # directly since V3Mixin would otherwise never reach it.
        if flag_is_active(request, "v3") and not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.method == "POST" and flag_is_active(request, "v3"):
            self._v3_active = True
            return self.post(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get_v3_role_options(self):
        """Role options offered by the edit-page dropdown, cached per request
        so seeding the initial data and building the field agree on one list."""
        if not hasattr(self, "_v3_role_options"):
            self._v3_role_options = self.request.user.get_role_options()
        return self._v3_role_options

    def get_v3_edit_initial(self, badge_options=None):
        """Current values for the v3 edit form.

        ``badge_options`` lets the display-badge field fall back to the best badge
        the member holds when their stored choice is gone or they never made one.
        Only the page render passes it; the POST path has no picker to seed.
        """
        user = self.request.user
        # Preselect the stored role only if it's still an offered option:
        # `encoded_displayed_role` resolves via the `resolved_profile_role`
        # cache, which can lag the live eligibility that builds the choices
        # (and the save-time validation). Seeding a stale value would render
        # an un-saveable selection.
        role_options = self.get_v3_role_options()
        offered = {
            encode_role_option(o["role"], o["library"].id if o["library"] else "")
            for o in role_options
        }
        if role_options:
            # The form offers the opt-out only when the user holds roles.
            offered.add(NO_PUBLIC_ROLE_OPTION)
        encoded_role = user.encoded_displayed_role
        # A revoked badge is no longer one of the field's choices, so seeding it
        # would fail validation and block the whole section from saving.
        display_badge = user.display_badge
        if display_badge is not None and not display_badge.is_active:
            display_badge = None
        display_badge_id = display_badge and display_badge.pk
        if badge_options is not None:
            display_badge_id = badge_display.resolve_selection(
                badge_options, display_badge_id
            )
        return {
            "avatar": user.avatar_url,
            "username": user.display_name,
            "email": user.email,
            "tagline": user.tagline,
            "bio": user.biography,
            "role": encoded_role if encoded_role in offered else "",
            "country": user.country.code,
            "indicate_last_login_method": user.indicate_last_login_method,
            "override_commit_author_name": user.is_commit_author_name_overridden,
            "hide_github": user.hide_github_activity,
            "hide_ml": user.hide_mailing_list_activity,
            "hide_ach": user.hide_badges,
            "display_badge": display_badge_id,
            "allow_notification_own_news_approved": (
                user.preferences.allow_notification_own_news_approved
            ),
            "allow_notification_others_news_posted": (
                user.preferences.allow_notification_others_news_posted
            ),
        }

    def get_v3_edit_url(self):
        return edit_profile_url()

    def get_v3_commit_email_form(self):
        """Build the commit-email card's add form for this render.

        Unbound normally. After a rejected add with JS off, the card's create
        view redirects here with the address it refused (`ce_email`) and no
        message: re-validating that address regenerates the identical error,
        so the message has exactly one source - the form - whichever way the
        card was rendered, and the card template only ever reads a bound form.
        """
        email = self.request.GET.get("ce_email", "")
        if not email:
            return V3CommitAuthorEmailForm()

        form = V3CommitAuthorEmailForm(
            data={"commit_email": email}, user=self.request.user
        )
        if form.is_valid():
            # whatever blocked the add cleared between that POST and this GET,
            # so there is no validation error left to show - say something
            # rather than re-rendering as though nothing had happened
            form.add_error("commit_email", COMMIT_EMAIL_ADD_FAILED_ERROR)
        return form

    def get_v3_edit_context(self, form=None):
        """Context for the v3 edit-profile template. `form` is a bound form
        (with errors) when re-rendering after a failed POST; otherwise a
        fresh form seeded from the user's current data is built."""
        badge_options = badge_display.badge_options(self.request.user)
        if form is None:
            form = V3UserProfileForm(
                user=self.request.user,
                user_links=self.request.user.profile_links,
                role_options=self.get_v3_role_options(),
                initial=self.get_v3_edit_initial(badge_options),
            )
        saved_section = self.request.GET.get("saved")
        user = self.request.user
        is_gh_conn: bool = user.is_github_connected
        is_go_conn: bool = user.is_google_connected

        def _get_connection_context_data(platform: str, connected: bool) -> dict | None:
            adapter: DefaultSocialAccountAdapter = get_adapter(self.request)
            try:
                provider = adapter.get_provider(self.request, platform)
            except SocialApp.DoesNotExist:
                return None
            if platform not in ["github", "google"]:
                return None
            label = ""
            if platform == "github":
                label = "GitHub"
            else:
                label = platform.capitalize()
            return {
                "platform": platform,
                "label": label,
                "status_text": "Connected" if connected else "Not Connected",
                "action_label": "Manage" if connected else "Connect",
                "connected": connected,
                # If not connected, we provide the login url for the chosen platform
                # else, this points to the name of the disconnect modal associated with this platform
                "action_url": (
                    provider.get_login_url(
                        self.request,
                        **{auth.REDIRECT_FIELD_NAME: self.request.get_full_path()},
                        process="connect",
                    )
                    if not connected
                    else f"#disconnect-{platform}"
                ),
                "disconnect_text": f"This will remove the link between your Boost account and {label}. You can reconnect at any time.",
                "disconnect_url": f"{reverse('profile-disconnect-social', kwargs={"platform": platform})}?redirect_url={reverse("profile-account")}?edit=True",
            }

        ctx = {
            "user_profile_form": form,
            "SLACK_PROFILE_URL_PREFIX": SLACK_PROFILE_URL_PREFIX,
            "biography_max_length": User.BIOGRAPHY_MAX_LENGTH,
            "country_options": form.fields["country"].choices,
            "badge_options": badge_options,
            "profile_account_edit_url": self.get_v3_edit_url(),
            "saved_sections": {
                key: key == saved_section for key in self.V3_EDIT_SECTIONS
            },
            "profile_account_url": reverse("profile-account"),
            "commit_email_addresses": CommitAuthorEmail.claimed_by_user(
                self.request.user
            ),
            # The commit-email card's no-JS PRG landing (see
            # V3CommitAuthorEmailCardMixin._redirect_to_profile). These are
            # the same two variables the card's own htmx responses set, so the
            # template never branches on how it was reached.
            "commit_email_form": self.get_v3_commit_email_form(),
            "commit_email_card_error": (
                COMMIT_EMAIL_STALE_ACTION_ERROR
                if self.request.GET.get("ce_alert")
                else ""
            ),
            "account_connections": [],
        }
        # Delete-account card: the modal schedules deletion, and once
        # scheduled the card swaps to a single "Cancel deletion" control.
        # A failed confirmation redirects back here with ?delete_error=1 and
        # reopens the modal, which renders this inline on the verify field.
        if self.request.GET.get("delete_error"):
            ctx["delete_account_error"] = DELETE_CONFIRM_ERROR
        ctx["delete_permanently_at"] = user.delete_permanently_at
        grace_days = settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS
        ctx["ACCOUNT_DELETION_GRACE_PERIOD_DAYS"] = grace_days
        ctx["delete_schedule_warning"] = (
            f"Your account will be scheduled for deletion in {grace_days} "
            f"{'day' if grace_days == 1 else 'days'}. You can cancel the "
            "deletion before then."
        )
        ctx["profile_delete_url"] = reverse("profile-delete")
        ctx["postorius_url"] = settings.POSTORIUS_URL

        gh_conn_data = _get_connection_context_data("github", is_gh_conn)
        go_conn_data = _get_connection_context_data("google", is_go_conn)
        if gh_conn_data:
            ctx["account_connections"].append(gh_conn_data)
        if go_conn_data:
            ctx["account_connections"].append(go_conn_data)
        return ctx

    def get_v3_context_data(self, **kwargs):
        if self.request.GET.get("edit", "").lower() == "true":
            return self.get_v3_edit_context()
        ctx = self.get_v3_public_context(self.request.user)
        # Counted here rather than in the shared context so only the owner's own
        # page can produce real tallies.
        ctx["achievement_dialog_items"] = badge_display.achievement_dialog_rows(
            self.request.user
        )
        return ctx

    def get_template_names(self):
        if (
            getattr(self, "_v3_active", False)
            and self.request.GET.get("edit", "").lower() == "true"
            and self.request.user.is_authenticated
        ):
            return [self.v3_edit_template_name]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context["change_password_form"] = ChangePasswordForm(user=self.request.user)
            context["profile_form"] = UserProfileForm(instance=self.request.user)
            context["profile_photo_form"] = UserProfilePhotoForm(
                instance=self.request.user
            )
            context["can_update_image"] = self.request.user.can_update_image
            context["profile_preferences_form"] = PreferencesForm(
                instance=self.request.user.preferences
            )
            context["social_accounts"] = self.get_social_accounts()
            if flag_is_active(self.request, "v3"):
                # NB: on v3 edit-profile renders this line runs after (and
                # overwrites) the get_v3_edit_context value, because V3Mixin's
                # get_context_data re-enters this method - so it must build
                # the exact same queryset
                context["commit_email_addresses"] = CommitAuthorEmail.claimed_by_user(
                    self.request.user
                )
            else:
                context["commit_email_addresses"] = CommitAuthorEmail.objects.filter(
                    author__user=self.request.user
                )
        return context

    def get_social_accounts(self):
        account_data = []
        for account in SocialAccount.objects.filter(user=self.request.user):
            try:
                provider_account = account.get_provider_account()
            except SocialApp.DoesNotExist:
                continue
            account_data.append(
                {
                    "id": account.pk,
                    "provider": account.provider,
                    "name": provider_account.to_str(),
                }
            )
        return account_data

    def post(self, request, *args, **kwargs):
        """
        Process each form submission individually if present
        """
        if getattr(self, "_v3_active", False):
            return self.post_v3(request, *args, **kwargs)

        if "change_password" in request.POST:
            change_password_form = ChangePasswordForm(
                data=request.POST, user=self.request.user
            )
            self.change_password(change_password_form, request)

        if "update_profile" in request.POST:
            profile_form = UserProfileForm(
                self.request.POST, instance=self.request.user
            )
            self.update_profile(profile_form, request)

        if "update_photo" in request.POST:
            profile_photo_form = UserProfilePhotoForm(
                self.request.POST, self.request.FILES, instance=self.request.user
            )
            self.update_photo(profile_photo_form, request)

        if "update_github_photo" in request.POST:
            self.update_github_photo(request)

        if "update_preferences" in request.POST:
            profile_preferences_form = PreferencesForm(
                self.request.POST, instance=request.user.preferences
            )
            self.update_preferences(profile_preferences_form, request)

        return HttpResponseRedirect(self.success_url)

    # Maps each section's submit-button name to the fields it owns and the
    # method that persists them. Keeps the button name, the validated field
    # set, and the save logic in one place instead of two parallel if/elif
    # chains keyed on the same button names.
    V3_EDIT_SECTIONS = {
        "v3_update_profile": (
            ["display_badge", "hide_github", "hide_ml", "hide_ach"],
            "_save_v3_visibility_section",
        ),
        "v3_update_details": (
            [
                "username",
                "country",
                "indicate_last_login_method",
                "override_commit_author_name",
            ],
            "_save_v3_details_section",
        ),
        "v3_update_email_preferences": (
            [
                "allow_notification_own_news_approved",
                "allow_notification_others_news_posted",
            ],
            "_save_v3_email_preferences_section",
        ),
    }

    def post_v3(self, request, *args, **kwargs):
        """Handle the v3 edit-profile page's independently-submitted section
        forms. Each section has its own <form>/submit button; only the
        fields owned by that section are validated and persisted."""
        edit_url = self.get_v3_edit_url()

        section_key = next(
            (key for key in self.V3_EDIT_SECTIONS if key in request.POST),
            None,
        )
        if section_key is None:
            return HttpResponseRedirect(edit_url)
        section_fields, save_method_name = self.V3_EDIT_SECTIONS[section_key]

        # Each section is submitted independently, so request.POST only
        # carries this section's fields; every other field on the shared
        # form would otherwise be treated as blank/unchecked when
        # re-rendering after a validation error. Fill those in from the
        # user's current values so a failed save on one section doesn't
        # wipe the displayed state of the others.
        initial = self.get_v3_edit_initial()
        data = request.POST.copy()
        for field_name, value in initial.items():
            if field_name in data or field_name in section_fields:
                continue
            if value is True:
                data[field_name] = "on"
            elif value in (False, None):
                continue
            elif isinstance(value, (list, tuple)):
                valid_choices = {
                    choice
                    for choice, _ in getattr(
                        V3UserProfileForm.base_fields.get(field_name), "choices", []
                    )
                }
                values = [v for v in value if v in valid_choices]
                if values:
                    data.setlist(field_name, values)
            else:
                data[field_name] = value

        form = V3UserProfileForm(
            data,
            user=request.user,
            user_links=request.user.profile_links,
            role_options=self.get_v3_role_options(),
            initial=initial,
        )
        # Only the submitted section's fields are validated; the other fields
        # share this form but have no save handler yet, so neither their
        # required-ness nor their validators (e.g. max_length) should block
        # this section's save.
        for name, field in form.fields.items():
            if name not in section_fields:
                field.required = False
                field.validators = []

        if not form.is_valid():
            context = self.get_v3_edit_context(form=form)
            return self.render_to_response(context)

        getattr(self, save_method_name)(request.user, form)

        # The saved section's submit button shows a "Changes Saved" state
        # instead (see get_v3_edit_context's saved_sections); the legacy
        # toast is suppressed on this page. JS submits this fetch-style (see
        # createSectionForm in user_profile_edit.html) so a successful save
        # can flip the button state without a full-page navigation; a plain
        # HTML form post (no JS) still gets the redirect it needs to see the
        # saved state on reload.
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"saved": section_key})
        return HttpResponseRedirect(f"{edit_url}&saved={section_key}")

    def _save_v3_visibility_section(self, user, form):
        user.hide_github_activity = form.cleaned_data["hide_github"]
        user.hide_mailing_list_activity = form.cleaned_data["hide_ml"]
        user.hide_badges = form.cleaned_data["hide_ach"]
        user.display_badge = form.cleaned_data["display_badge"]
        user.save()

    def _save_v3_details_section(self, user, form):
        user.display_name = form.cleaned_data["username"]
        user.country = form.cleaned_data["country"]
        user.indicate_last_login_method = form.cleaned_data[
            "indicate_last_login_method"
        ]
        user.is_commit_author_name_overridden = form.cleaned_data[
            "override_commit_author_name"
        ]
        user.save()
        # Only mints when the name actually changed; this handler also runs for
        # country and the toggles, and every mint moves the user's public URL.
        UserProfileRoutingKey.objects.sync_for(user)

    def _save_v3_email_preferences_section(self, user, form):
        """Save the v3 page's email-preference checkboxes. The v3 page only
        shows a subset of news types (V3_EMAIL_PREFERENCE_CHOICES); any other
        type the user already had allowed (e.g. "poll") is preserved rather
        than being dropped just because it has no checkbox here.
        """
        preferences = user.preferences
        v3_managed_types = {
            key
            for key, _ in form.fields["allow_notification_own_news_approved"].choices
        }
        for field_name in (
            "allow_notification_own_news_approved",
            "allow_notification_others_news_posted",
        ):
            preserved = [
                news_type
                for news_type in getattr(preferences, field_name)
                if news_type not in v3_managed_types
            ]
            setattr(preferences, field_name, preserved + form.cleaned_data[field_name])
        preferences.save()

    def change_password(self, form, request):
        """Change the password of the user."""
        if form.is_valid():
            self.object = request.user
            self.object.set_password(form.cleaned_data["password1"])
            self.object.save()

            # Resetting the password acts as confirmation that the user has
            # claimed their account, so mark it claimed.
            self.object.claim()
            messages.success(request, "Your password was successfully updated.")
        else:
            for error in form.errors.values():
                messages.error(request, f"{error}")

    def update_photo(self, form, request):
        """Update the profile photo of the user."""
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile photo was successfully updated.")
        else:
            for error in form.errors.values():
                messages.error(request, f"{error}")

    def update_github_photo(self, request):
        """Update the GitHub photo of the user."""
        tasks.update_user_github_photo(str(request.user.pk))
        messages.success(request, "Your GitHub photo has been retrieved.")

    def update_preferences(self, form, request):
        """Update the preferences of the user."""
        if form.is_valid():
            form.save()
            messages.success(request, "Your preferences were successfully updated.")
        else:
            for error in form.errors.values():
                messages.error(request, f"{error}")

    def update_profile(self, form, request):
        """Update the profile of the user."""
        if form.is_valid():
            user = form.save()
            # This form carries display_name too, so a rename here has to mint a
            # key just as the v3 handler does. Without it, anyone renaming while
            # the v3 flag is off keeps a profile URL built from their old name.
            UserProfileRoutingKey.objects.sync_for(user)
            messages.success(request, "Your profile was successfully updated.")
        else:
            for error in form.errors.values():
                messages.error(request, f"{error}")


# Custom Allauth Views


class ClaimExistingAccountMixin:
    """
    When a new user attempts to register with an email address that exists, but
    has not been claimed, send the user a password reset for that account so they can
    claim it.
    """

    message = """
        We recognize your email address as matching that of a Boost Author or
        Maintainer, and have already created an account for you. We have sent you an
        email to reset the password for your account. Once your password has been
        reset, your account is claimed.
    """

    def check_and_send_reset_email(self, form, message=None):
        if not message:
            message = self.message

        for field, errors in form.errors.items():
            if field == "email":
                email = form.data.get("email")
                user = User.objects.filter(email__iexact=email).first()

                if user and not user.claimed:
                    form = ResetPasswordForm({"email": email})
                    if form.is_valid():
                        form.save(request=self.request)
                        self.request.session["contributor_account_redirect_message"] = (
                            message
                        )
                        return HttpResponseRedirect(reverse_lazy("account_login"))

        return None


#
class CustomSocialSignupViewView(ClaimExistingAccountMixin, SocialSignupView):
    """
    Override the allauth social account SignupView to customize behavior:
    """

    message = """
        We recognize your email address as matching that of a Boost Author or
        Maintainer, and have already created an account for you. We have sent you an
        email to reset the password for your account. Once your password has been
        reset, your account is claimed and you can connect your social account
        from your Profile.
        """

    def form_invalid(self, form):
        """
        Override this form to catch users who were created as part of the GitHub data
        import and who need to create their accounts
        """
        res = self.check_and_send_reset_email(form, message=self.message)
        return res if res else super().form_invalid(form)


class CustomSignupView(ClaimExistingAccountMixin, V3AuthContextMixin, SignupView):
    """
    Override the allauth SignupView to customize behavior:

    - Check to see if the user who is registering already has an account
    because one was created for them, and it has not been claimed. This happens
    with authors and maintainers.
    """

    v3_template_name = "v3/accounts/signup.html"

    def get_form_class(self):
        if flag_is_active(self.request, "v3"):
            return CustomSignUpForm
        return super().get_form_class()

    def get_v3_context_data(self, **kwargs):
        context = super().get_v3_context_data(**kwargs)
        context["password_rules"] = build_password_rules()
        return context

    def form_invalid(self, form):
        """
        Override this form to catch users who were created as part of the GitHub data
        import and who need to create their accounts
        """
        res = self.check_and_send_reset_email(form, message=self.message)
        return res if res else super().form_invalid(form)


class CustomLoginView(V3AuthContextMixin, LoginView):
    v3_template_name = "v3/accounts/login.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["contributor_account_redirect_message"] = self.request.session.pop(
            "contributor_account_redirect_message", None
        )
        return context


class CustomEmailVerificationSentView(EmailVerificationSentView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["EMAIL_CONFIRMATION_EXPIRE_DAYS"] = (
            app_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS
        )
        return context


class V3LoginView(V3AuthContextMixin, TemplateView):
    v3_template_name = "v3/accounts/login.html"
    page_title = "Login"


class V3PasswordResetView(V3AuthContextMixin, PasswordResetView):
    # Drop allauth's legacy template_name so V3AuthContextMixin 404s this
    # v3-only route when the flag is off (instead of falling back to it).
    template_name = None
    v3_template_name = "v3/accounts/password_reset.html"
    page_title = "Reset Password"
    success_url = reverse_lazy("v3-password-reset-done")


class V3PasswordResetDoneView(V3AuthContextMixin, TemplateView):
    v3_template_name = "v3/accounts/password_reset_done.html"
    page_title = "Check Your Email"


class V3PasswordResetFromKeyView(V3AuthContextMixin, PasswordResetFromKeyView):
    # See V3PasswordResetView: null template_name keeps this route v3-only.
    template_name = None
    v3_template_name = "v3/accounts/password_reset_from_key.html"
    page_title = "Change Password"
    success_url = reverse_lazy("v3-password-reset-from-key-done")

    def get_v3_context_data(self, **kwargs):
        context = super().get_v3_context_data(**kwargs)
        context["password_rules"] = build_password_rules()
        return context


class V3PasswordResetFromKeyDoneView(V3AuthContextMixin, TemplateView):
    v3_template_name = "v3/accounts/password_reset_from_key_done.html"
    page_title = "Password Changed"


class UserAvatar(TemplateView):
    """
    Returns the template for the user's avatar in the header from the htmx request.
    """

    permission_classes = [AllowAny]
    template_name = "users/includes/header_avatar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        context["mobile"] = self.request.GET.get("ui")
        return context

    def render_to_response(self, context, **response_kwargs):
        """
        Override to delete CSRF cookie when session cookie is not present.
        This cleans up CSRF cookies for anonymous users.
        TODO: december 2025 - remove this override, cookies should have been cleared
        """
        response = super().render_to_response(context, **response_kwargs)

        session_cookie_name = settings.SESSION_COOKIE_NAME
        has_session = session_cookie_name in self.request.COOKIES
        has_csrf_cookie = "csrftoken" in self.request.COOKIES

        # only delete CSRF cookie if user was previously logged in but session expired
        if (
            has_csrf_cookie
            and not has_session
            and self.request.session.session_key is None
        ):
            # check if user is on pages that require CSRF but don't require login
            # (auth pages where anonymous users submit forms)
            referer = self.request.headers.get("referer", "")
            current_path = self.request.path

            # paths that anonymous users can access and have forms
            anonymous_form_paths = [
                "/accounts/",  # login, signup, password reset, email confirm, etc.
                "/socialaccount/",  # social auth pages
            ]

            # don't delete if user is on or coming from anonymous form pages
            is_anonymous_form = any(
                path in referer for path in anonymous_form_paths
            ) or any(path in current_path for path in anonymous_form_paths)

            if not is_anonymous_form:
                response.delete_cookie("csrftoken", path="/")

        return response


# Confirmation-phrase error shown inline in the delete modal.
DELETE_CONFIRM_ERROR = DeleteAccountForm.CONFIRM_ERROR


def _v3_profile_edit_url(fragment="", error=False):
    """Edit-profile URL used as the V3 return target for the delete flow.

    The optional fragment reopens the relevant :target modal after a redirect
    (e.g. when confirmation fails), so the flow works without JavaScript.
    ``error=True`` flags a failed confirmation so the reopened modal can render
    the error inline instead of relying on a global message banner.
    """
    query = "?edit=true&delete_error=1" if error else "?edit=true"
    return f"{reverse('profile-account')}{query}{fragment}"


class DeleteUserView(LoginRequiredMixin, FormView):
    template_name = "users/delete.html"
    success_url = reverse_lazy("profile-account")
    form_class = DeleteAccountForm

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        user = self.get_object()
        user.delete_permanently_at = timezone.now() + datetime.timedelta(
            days=settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS
        )
        if flag_is_active(self.request, "v3"):
            user.deletion_extended_scrub = True
            login_url = self.request.build_absolute_uri(reverse("account_login"))
            scheme = self.request.scheme
            host = self.request.get_host()
            # Persist the schedule and enqueue the confirmation email atomically:
            # the task is published only after the row commits (mirroring
            # delete_account), so a rolled-back save never enqueues an email.
            with transaction.atomic():
                user.save()
                transaction.on_commit(
                    lambda: tasks.send_account_deletion_scheduled_email.delay(
                        email=user.email,
                        first_name=user.first_name,
                        grace_days=settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS,
                        login_url=login_url,
                        scheme=scheme,
                        host=host,
                    )
                )
            return HttpResponseRedirect(_v3_profile_edit_url())
        user.save()
        return super().form_valid(form)

    def form_invalid(self, form):
        if flag_is_active(self.request, "v3"):
            return HttpResponseRedirect(
                _v3_profile_edit_url("#delete-account-dialog", error=True)
            )
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ACCOUNT_DELETION_GRACE_PERIOD_DAYS"] = (
            settings.ACCOUNT_DELETION_GRACE_PERIOD_DAYS
        )
        return context


class CancelDeletionView(LoginRequiredMixin, SuccessMessageMixin, FormView):
    form_class = forms.Form
    success_url = reverse_lazy("profile-account")
    template_name = "users/cancel_deletion.html"
    success_message = "Your account is no longer scheduled for deletion."

    def get_object(self):
        return self.request.user

    def get_success_url(self):
        if flag_is_active(self.request, "v3"):
            return _v3_profile_edit_url()
        return super().get_success_url()

    def get_success_message(self, cleaned_data):
        # V3 relies on the edit-page state (the scheduled banner disappears) for
        # feedback, so suppress the legacy success banner. Legacy is unchanged.
        if flag_is_active(self.request, "v3"):
            return ""
        return super().get_success_message(cleaned_data)

    def form_valid(self, form):
        user = self.get_object()
        user.delete_permanently_at = None
        user.deletion_extended_scrub = False
        user.save()
        return super().form_valid(form)


class DeleteImmediatelyView(LoginRequiredMixin, SuccessMessageMixin, FormView):
    form_class = DeleteAccountForm
    template_name = "users/delete_immediately.html"
    success_url = "/"
    success_message = "Your profile was successfully deleted."

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        user = self.get_object()
        user.delete_account(extended_scrub=flag_is_active(self.request, "v3"))
        auth.logout(self.request)
        return super().form_valid(form)


class DisconnectSocialAccountView(LoginRequiredMixin, View):
    def post(self, *args, **kwargs):
        redirect_url = self.request.GET.get("redirect_url", "").strip("'") or reverse(
            "home"
        )
        if not url_has_allowed_host_and_scheme(redirect_url, allowed_hosts=None):
            messages.error(
                self.request, "An internal error has occurred. Please contact an admin."
            )
            return HttpResponseRedirect(reverse("home"))

        platform = kwargs.get("platform")
        if not platform:
            messages.error(self.request, "Platform must be specified.")
            return HttpResponseRedirect(redirect_url)

        user = self.request.user
        try:
            sa = SocialAccount.objects.get(user=user, provider=platform)
        except SocialAccount.DoesNotExist:
            messages.error(
                self.request,
                "No social account between this user and platform exists on Boost.",
            )
            return HttpResponseRedirect(redirect_url)

        form = DisconnectForm(request=self.request, data={"account": sa.pk})
        if form.is_valid():
            form.save()
        else:
            messages.error(
                self.request,
                " ".join(form.non_field_errors())
                or "An error has occurred while removing your connection. Please try again shortly.",
            )

        return HttpResponseRedirect(redirect_url)
