import datetime
from textwrap import dedent

from allauth.account import app_settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import auth
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
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

from waffle import flag_is_active

from core.constants import BadgeToken
from core.mixins import V3Mixin, V3AuthContextMixin
from libraries.models import CommitAuthorEmail
from .forms import (
    PreferencesForm,
    UserProfileForm,
    UserProfilePhotoForm,
    DeleteAccountForm,
    V3UserProfileForm,
    CustomSignUpForm,
)
from .models import User
from .password_rules import build_password_rules
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


class CurrentUserProfileView(
    V3Mixin, LoginRequiredMixin, SuccessMessageMixin, TemplateView
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

    def get_v3_edit_initial(self):
        user = self.request.user
        return {
            "avatar": user.avatar_url,
            "username": user.display_name,
            "email": user.email,
            "country": user.country.code,
            "indicate_last_login_method": user.indicate_last_login_method,
            "override_commit_author_name": user.is_commit_author_name_overridden,
            "hide_github": user.hide_github_activity,
            "hide_ml": user.hide_mailing_list_activity,
            "hide_ach": user.hide_badges,
            "allow_notification_own_news_approved": (
                user.preferences.allow_notification_own_news_approved
            ),
            "allow_notification_others_news_posted": (
                user.preferences.allow_notification_others_news_posted
            ),
        }

    def get_v3_edit_context(self, form=None):
        """Context for the v3 edit-profile template. `form` is a bound form
        (with errors) when re-rendering after a failed POST; otherwise a
        fresh form seeded from the user's current data is built."""
        if form is None:
            form = V3UserProfileForm(
                user=self.request.user,
                user_links={"website": "www.example.com"},
                initial=self.get_v3_edit_initial(),
            )
        return {
            "user_profile_form": form,
            "country_options": form.fields["country"].choices,
            "profile_account_url": reverse("profile-account"),
            "badge_tiers": [
                {"tier": "1", "name": "Bronze"},
                {"tier": "2", "name": "Silver"},
                {"tier": "3", "name": "Gold"},
                {"tier": "4", "name": "Platinum"},
                {"tier": "5", "name": "Diamond"},
            ],
            "account_connections_mixed": [
                {
                    "platform": "github",
                    "label": "GitHub",
                    "connected": True,
                    "status_text": "Connected",
                    "action_label": "Manage",
                    "action_url": "#",
                },
                {
                    "platform": "google",
                    "label": "Google",
                    "connected": False,
                    "status_text": "Not connected",
                    "action_label": "Connect",
                    "action_url": "#",
                },
            ],
        }

    def get_v3_context_data(self, **kwargs):
        user = self.request.user
        ctx = {}

        if self.request.GET.get("edit", "").lower() == "true":
            return self.get_v3_edit_context()

        ctx["user_info"] = {
            "user_name": user.display_name,
            "avatar_url": user.get_avatar_url(),
            "featured_badge": {
                "name": "Bug Catcher",
                "badge": BadgeToken.TIER_5,
            },
            "member_since": user.date_joined.year,
            "role": "Contributor",
        }

        # Data shared between both versions, Boost Github and Mailing List activity
        ctx["github_activity_card_data"] = {
            "title": "Latest Boost Github activity",
            "markdown_text": dedent("""
                        * Created 24 Commits in [**7 repositories**](https://www.example.com)
                        * Created [**1 repository**](https://www.example.com)
                        * Created a pull request in [**cppalliance/buffers**](https://www.example.com) that received 6 comments
                        * Opened 17 other pull requests in [**6 repositories**](https://www.example.com)
                        * Reviewed 3 pull requests in [**3 repositories**](https://www.example.com)
                    """),
            "button_url": "https://www.github.com",
            "button_label": "View on Github",
        }
        ctx["mailing_list_activity_card_data"] = {
            "title": "Mailing List Activity",
            "mailing_list_items": [
                {
                    "date": datetime.date(2025, 7, 11),
                    "headline": "[release] Boost 1.90.0 Beta 1 Release Candidate 1 is available",
                    "url": "#",
                },
                {
                    "date": datetime.date(2025, 7, 11),
                    "headline": "[release] Boost 1.90.0 Beta 1 Release Candidate 1 is available",
                    "url": "#",
                },
                {
                    "date": datetime.date(2025, 7, 11),
                    "headline": "[release] Boost 1.90.0 Beta 1 Release Candidate 1 is available",
                    "url": "#",
                },
                {
                    "date": datetime.date(2025, 7, 11),
                    "headline": "[release] Boost 1.90.0 Beta 1 Release Candidate 1 is available",
                    "url": "#",
                },
                {
                    "date": datetime.date(2025, 7, 11),
                    "headline": "[release] Boost 1.90.0 Beta 1 Release Candidate 1 is available",
                    "url": "#",
                },
            ],
        }

        if self.request.GET.get("filled"):
            ctx["bio"] = dedent("""
                **Professional Profile**

                I am a software engineer and C++ expert with extensive experience in systems programming and open-source software development. My work focuses on advancing the C++ ecosystem through libraries, tools, and community leadership.

                **Boost Library Author**

                I have authored and maintain several widely-used Boost libraries that are relied upon by developers worldwide. These libraries provide robust, production-ready components for modern C++ applications.

                **President of The C++ Alliance**

                As President of The C++ Alliance, I lead initiatives to support and advance the C++ programming language and its community. The Alliance provides resources, funding, and infrastructure to support C++ development, education, and standardization efforts.

                **Creator of Mr. Docs**

                I created Mr. Docs, a documentation generation tool designed specifically for C++ projects. Mr. Docs helps developers create high-quality, maintainable documentation that keeps pace with modern C++ codebases.

                **My primary technical interests include:**

                * HTTP Protocol: Implementation and optimization of HTTP client and server libraries
                * WebSocket Protocol: Real-time bidirectional communication protocols and their practical applications
                * Network Programming: High-performance asynchronous networking solutions in C++

                These interests have shaped my contributions to the C++ ecosystem, particularly in developing libraries that make network programming more accessible and efficient for developers.
            """)
            ctx["contributor_data"] = {
                "Author": ["Beast", "JSON"],
                "Maintainer": ["Beast", "Accumulator"],
                "Contributor": [
                    "Beast",
                    "JSON",
                    "Accumulator",
                    "Asio",
                    "Blood",
                    "Redis",
                    "MQTT5",
                ],
                "Reviews": ["Asio", "Blood (Manager)", "Redis", "MQTT5"],
            }
            ctx["profile_post_cta_label"] = "View All Posts"
            ctx["profile_post_cta_url"] = "#"
            ctx["achievements_data"] = {
                "achievements": [
                    {
                        "title": "Lorem Ipsum",
                        "points": 22,
                        "description": "A longer description giving a summary of the achievement.",
                    }
                    for _ in range(6)
                ]
            }
            ctx["demo_badges"] = [
                {
                    "icon": BadgeToken.TIER_1,
                    "name": "Code Whisperer",
                    "earned_date": "01/01/2025",
                },
                {
                    "icon": BadgeToken.TIER_2,
                    "name": "Library Alchemist",
                    "earned_date": "03/04/2025",
                },
                {
                    "icon": BadgeToken.TIER_3,
                    "name": "Patch Wizard",
                    "earned_date": "08/08/2025",
                },
                {
                    "icon": BadgeToken.TIER_4,
                    "name": "Bug Catcher",
                    "earned_date": "02/04/2025",
                },
                {
                    "icon": BadgeToken.TIER_5,
                    "name": "Standard Bearer",
                    "earned_date": "03/07/2025",
                },
                {
                    "icon": BadgeToken.STAR_TIER_3,
                    "name": "Review Hawk",
                    "earned_date": "03/06/2025",
                },
            ]
            ctx["posts"] = [
                {
                    "title": "A talk by Richard Thomson at the Utah C++ Programmers Group",
                    "url": "#",
                    "date": datetime.date(2025, 3, 3),
                    "category": "Issues",
                    "tag": "beast",
                },
                {
                    "title": "A talk by Richard Thomson at the Utah C++ Programmers Group",
                    "url": "#",
                    "date": datetime.date(2025, 3, 3),
                    "category": "Issues",
                    "tag": "beast",
                },
                {
                    "title": "Boost.Bind and modern C++: a quick overview",
                    "url": "#",
                    "date": datetime.date(2025, 2, 15),
                    "category": "Releases",
                    "tag": "bind",
                },
                {
                    "title": "Boost.Bind and modern C++: a quick overview again",
                    "url": "#",
                    "date": datetime.date(2025, 2, 15),
                    "category": "Releases",
                    "tag": "bind",
                },
                {
                    "title": "utility::string_view and core::detail::string_view",
                    "url": "#",
                    "date": datetime.date(2025, 2, 15),
                    "category": "Releases",
                    "tag": "bind",
                },
            ]
            ctx["social_media_links"] = [
                {
                    "url": "#",
                    "label": "GitHub",
                    "icon": "pixel-github",
                },
                {
                    "url": "#",
                    "label": "Website",
                    "icon": "pixel-computer",
                },
                {
                    "url": "#",
                    "label": "Email",
                    "icon": "pixel-email",
                },
                {
                    "url": "#",
                    "label": "Chat on Slack",
                    "icon": "pixel-slack",
                },
            ]
            ctx["account_connections_none_connected"] = [
                {
                    "platform": "github",
                    "label": "GitHub",
                    "connected": False,
                    "status_text": "Not connected",
                    "action_label": "Connect",
                    "action_url": "#",
                },
                {
                    "platform": "google",
                    "label": "Google",
                    "connected": False,
                    "status_text": "Not connected",
                    "action_label": "Connect",
                    "action_url": "#",
                },
            ]

        else:
            ctx["posts"] = [
                {
                    "title": "Share Your Knowledge with the community",
                    "summary": "Write posts to share ideas, tutorials, announcements, or lessons learned about working with Boost",
                }
            ]
            ctx["bio"] = (
                "Add a short bio to tell the community who you are, what you work on, or what you’re passionate about."
            )
            ctx["profile_post_cta_label"] = "Create a Post"
            ctx["profile_post_cta_url"] = "#"
            ctx["social_media_links"] = [
                {
                    "icon": "pixel-github",
                    "disabled": True,
                    "extra_classes": "user-profile__btn-no-label",
                    "tp_label": "Add GitHub Profile Link",
                },
                {
                    "icon": "pixel-computer",
                    "disabled": True,
                    "extra_classes": "user-profile__btn-no-label",
                    "tp_label": "Add Website Link",
                },
                {
                    "icon": "pixel-email",
                    "disabled": True,
                    "extra_classes": "user-profile__btn-no-label",
                    "tp_label": "Add Email Address",
                },
                {
                    "icon": "pixel-slack",
                    "disabled": True,
                    "extra_classes": "user-profile__btn-no-label",
                    "tp_label": "Add CPP Slack Profile Link",
                },
            ]

        ctx["top_links"] = ctx["social_media_links"] + [
            {
                "url": "#",
                "label": "Edit Profile",
                "icon": "pixel-pencil",
            },
            {
                "url": "#",
                "label": "Share",
                "icon": "pixel-share",
            },
        ]

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
            ["hide_github", "hide_ml", "hide_ach"],
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
        edit_url = f"{reverse('profile-account')}?edit=true"

        section = next(
            (v for key, v in self.V3_EDIT_SECTIONS.items() if key in request.POST),
            None,
        )
        if section is None:
            return HttpResponseRedirect(edit_url)
        section_fields, save_method_name = section

        form = V3UserProfileForm(
            request.POST,
            user=request.user,
            user_links={"website": "www.example.com"},
            initial=self.get_v3_edit_initial(),
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

        messages.success(request, self.success_message)
        return HttpResponseRedirect(edit_url)

    def _save_v3_visibility_section(self, user, form):
        user.hide_github_activity = form.cleaned_data["hide_github"]
        user.hide_mailing_list_activity = form.cleaned_data["hide_ml"]
        user.hide_badges = form.cleaned_data["hide_ach"]
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


class V3PasswordResetView(V3AuthContextMixin, TemplateView):
    v3_template_name = "v3/accounts/password_reset.html"
    page_title = "Reset Password"


class V3PasswordResetDoneView(V3AuthContextMixin, TemplateView):
    v3_template_name = "v3/accounts/password_reset_done.html"
    page_title = "Check Your Email"


class V3PasswordResetFromKeyView(V3AuthContextMixin, TemplateView):
    v3_template_name = "v3/accounts/password_reset_from_key.html"
    page_title = "Change Password"

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
