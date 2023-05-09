from django.forms import Form, ModelChoiceField, ModelForm
from .models import Library
from versions.models import Version


class LibraryForm(ModelForm):
    class Meta:
        model = Library
        fields = ["categories"]


class VersionSelectionForm(Form):
    version = ModelChoiceField(
        queryset=Version.objects.all(),
        label="Select a version",
        empty_label="Choose a version...",
    )
