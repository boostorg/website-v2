from django.contrib.auth import get_user_model
from django import forms


User = get_user_model()


class UserProfilePhotoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["image"]
