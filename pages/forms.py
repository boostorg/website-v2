from django import forms

from donations.utils import (
    create_payment_intent_from_products,
    retrive_price,
    OrderItem,
)


class DonationForm(forms.Form):
    first_name = forms.CharField()
    last_name = forms.CharField()
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
    payment_method = forms.CharField()

    def save(self):
        data = self.cleaned_data
        payment_method = data.get("payment_method")

        order_items = [
            OrderItem(
                price=retrive_price(
                    data.get("price"),
                ),
                amount=1,
            )
        ]

        payment_intent = create_payment_intent_from_products(
            order_items=order_items, payment_method=payment_method
        )
        return {
            **data,
            "payment_intent_id": payment_intent.id,
            "amount": payment_intent.amount,
        }
