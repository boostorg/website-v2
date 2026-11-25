from django import forms

from donations.utils import (
    create_payment_intent_from_products,
    retrive_price,
    OrderItem,
    get_payment_method,
)


class DonationForm(forms.Form):
    first_name = forms.CharField(max_length=120)
    last_name = forms.CharField(max_length=120)
    email = forms.EmailField(
        help_text="We'll send your receipt here.",
    )
    organization = forms.CharField(
        required=False,
    )
    giving_for_org = forms.BooleanField(
        label="Giving on behalf of an organization?",
        required=False,
    )
    subscribe_mailing = forms.BooleanField(
        label="Send me occassional updates about boost.",
        required=False,
    )
    donor_opt_out = forms.BooleanField(
        label="Don't list my name publicly.",
        required=False,
    )
    price = forms.CharField()
    custom_amount = forms.IntegerField(
        min_value=10,
        required=False,
        widget=forms.TextInput(),
        label="Custom Amount",
        help_text="Donation amount in USD. Minimum $10.",
    )
    payment_method = forms.CharField()

    def clean(self):
        cleaned_data = super().clean()
        price = retrive_price(cleaned_data.get("price"))
        custom_amount = cleaned_data.get("custom_amount")
        if price.custom_unit_amount and not custom_amount:
            raise forms.ValidationError(
                "When selecting other, you must select an amount."
            )
        else:
            if (
                price.custom_unit_amount.minimum
                and custom_amount * 100 < price.custom_unit_amount.minimum
            ):
                raise forms.ValidationError("Selected price less than the minimum.")
        return cleaned_data

    def save(self):
        data = self.cleaned_data
        payment_method = data.get("payment_method")
        price = retrive_price(data.get("price"))
        price_amount = (
            price.unit_amount
            if not price.custom_unit_amount
            else data.get("custom_amount") * 100
        )

        order_items = [
            OrderItem(
                price=price_amount,
                amount=1,
            )
        ]

        payment_method_object = get_payment_method(payment_method)
        payment_intent = create_payment_intent_from_products(
            order_items=order_items, payment_method=payment_method
        )
        return {
            **data,
            "payment_intent_id": payment_intent.id,
            "amount": payment_intent.amount,
            "card4": payment_method_object.card.last4,
            "card_brand": payment_method_object.card.display_brand,
        }
