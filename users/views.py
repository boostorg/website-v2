import datetime

from allauth.account import app_settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import auth
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView
from django.views.generic.base import TemplateView
from django.utils import timezone
from django.conf import settings
from django import forms

from allauth.account.forms import ChangePasswordForm, ResetPasswordForm
from allauth.account.views import LoginView, SignupView, EmailVerificationSentView
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.views import SignupView as SocialSignupView

from rest_framework import generics
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny

from libraries.models import CommitAuthorEmail
from .forms import (
    PreferencesForm,
    UserProfileForm,
    UserProfilePhotoForm,
    DeleteAccountForm,
)
from .models import User
from .permissions import CustomUserPermissions
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

    def get_object(self):
        return self.request.user


class ProfileView(DetailView):
    """
    ViewSet to show statistics about a user to include
    stats, badges, reviews, etc.
    """

    model = User
    queryset = User.objects.all()
    template_name = "users/profile.html"
    context_object_name = "user"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()
        context["authored"] = user.authors.all()
        context["maintained"] = user.maintainers.all().distinct()
        return context


class CurrentUserProfileView(LoginRequiredMixin, SuccessMessageMixin, TemplateView):
    template_name = "users/profile.html"
    success_message = "Your profile was successfully updated."
    success_url = reverse_lazy("profile-account")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["change_password_form"] = ChangePasswordForm(user=self.request.user)
        context["profile_form"] = UserProfileForm(instance=self.request.user)
        context["profile_photo_form"] = UserProfilePhotoForm(instance=self.request.user)
        context["can_update_image"] = self.request.user.can_update_image
        context["profile_preferences_form"] = PreferencesForm(
            instance=self.request.user.preferences
        )
        context["social_accounts"] = self.get_social_accounts()
        context["commit_email_addresses"] = CommitAuthorEmail.objects.filter(
            author__user=self.request.user
        )
        return context

    def get_social_accounts(self):
        account_data = []
        for account in SocialAccount.objects.filter(user=self.request.user):
            provider_account = account.get_provider_account()
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
            form.save()
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


class CustomSignupView(ClaimExistingAccountMixin, SignupView):
    """
    Override the allauth SignupView to customize behavior:

    - Check to see if the user who is registering already has an account
    because one was created for them, and it has not been claimed. This happens
    with authors and maintainers.
    """

    def form_invalid(self, form):
        """
        Override this form to catch users who were created as part of the GitHub data
        import and who need to create their accounts
        """
        res = self.check_and_send_reset_email(form, message=self.message)
        return res if res else super().form_invalid(form)


class CustomLoginView(LoginView):
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
        user.save()
        return super().form_valid(form)

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

    def form_valid(self, form):
        user = self.get_object()
        user.delete_permanently_at = None
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
        user.delete_account()
        auth.logout(self.request)
        return super().form_valid(form)
