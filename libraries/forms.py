from django.forms import ModelForm
from .models import Library, Category


class LibraryForm(ModelForm):
    class Meta:
        model = Library
        fields = ["categories"]
