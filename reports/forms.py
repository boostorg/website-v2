from django import forms

from versions.models import Version


class ImportWebAnalyticsForm(forms.Form):
    version = forms.ModelChoiceField(
        Version.objects.get_dropdown_versions(),
        widget=forms.Select(attrs={"class": "dropdown !mb-0 h-[38px]"}),
    )
