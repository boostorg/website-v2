from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django import forms


User = get_user_model()


class ClaimAccountForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ("email", "password1", "password2")


class UserProfilePhotoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["image"]
