from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import DetailView, UpdateView
from django.views.generic.edit import FormView

from rest_framework import generics
from rest_framework import renderers
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import PreferencesForm, UserProfilePhotoForm
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


class CurrentUserFragmentView(viewsets.ViewSet):

    serializer_class = CurrentUserSerializer
    # permission_classes = [IsAuthenticated]
    template_name = "users/includes/user_join.html"
    renderer_classes = (renderers.TemplateHTMLRenderer,)

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return Response(
                {"user": self.serializer_class.data},
                template_name="users/includes/user_profile_image.html",
            )
        return Response({}, template_name="users/includes/user_join.html")


class ProfileView(DetailView):
    """
    ViewSet to show statistics about a user to include
    stats, badges, forum posts, reviews, etc.
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


class CurrentUserProfileView(LoginRequiredMixin, ProfileView):
    def get_object(self):
        return self.request.user


class ProfilePhotoUploadView(LoginRequiredMixin, FormView):
    """Allows a user to change their profile photo"""

    template_name = "users/photo_upload.html"
    form_class = UserProfilePhotoForm
    success_url = reverse_lazy("profile-account")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["user_has_gh_username"] = bool(user.github_username)
        return context

    def get_success_url(self, **kwargs):
        return reverse_lazy("profile-account")

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST, request.FILES, instance=self.request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile photo has been updated")
            return super().form_valid(form)
        else:
            return super().form_invalid()


class ProfilePhotoGitHubUpdateView(LoginRequiredMixin, UpdateView):
    """Allow a user to sync their profile photo to their current GitHub photo."""

    http_method_names = ["post"]

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self, **kwargs):
        return reverse_lazy("profile-user", args=[self.request.user.pk])

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        tasks.update_user_github_photo.delay(user.pk)
        return HttpResponseRedirect(self.get_success_url())


class ProfilePreferencesView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    form_class = PreferencesForm
    template_name = "users/profile_preferences.html"
    success_url = reverse_lazy("profile-preferences")
    success_message = "Your preferences were successfully updated."

    def get_object(self):
        return self.request.user.preferences
