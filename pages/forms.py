from django import forms


class DonationForm(forms.Form):
    first_name = forms.CharField()
    last_name = forms.CharField()
    email = forms.EmailField(help_text="We'll send your receipt here.")
    organization = forms.CharField()
    giving_for_org = forms.BooleanField(label="Giving on behalf of an organization?")
    country = forms.CharField()
    zip_code = forms.CharField()
    subscribe_mailing = forms.BooleanField(
        label="Send me occassional updates about boost."
    )
    donor_opt_out = forms.BooleanField(label="Don't list my name publicly.")
    cc_number = forms.CharField()
    cv_number = forms.CharField(max_length=3)
    cc_name = forms.CharField()
    exp_date = forms.CharField()
