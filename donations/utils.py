from dataclasses import dataclass
from typing import List

from stripe import StripeClient
from stripe import PaymentMethod

from django.conf import settings

client = StripeClient(settings.STRIPE_PRIVATE_KEY)


@dataclass
class OrderItem:
    price: int
    amount: int


def get_prices_for_product(
    prod_id: str,
):
    return client.v1.prices.list({"product": prod_id})


def get_default_price_for_product(
    prod_id: str,
):
    return client.v1.products.retrieve(prod_id).to_dict().get("default_price")


def get_payment_method(pm_id: str) -> PaymentMethod:
    return client.v1.payment_methods.retrieve(pm_id)


def create_payment_intent(
    amount: int,
    payment_method: str,
):
    return client.v1.payment_intents.create(
        {
            "currency": "usd",
            "confirm": True,
            "payment_method": payment_method,
            "amount": amount,
            "automatic_payment_methods": {
                "enabled": True,
                "allow_redirects": "never",
            },
        }
    )


def retrive_price(
    price_id: str,
):
    return client.v1.prices.retrieve(price_id)


def create_payment_intent_from_products(
    order_items: List[OrderItem],
    payment_method: str,
):
    total = 0
    for item in order_items:
        total += item.amount * item.price
    return create_payment_intent(total, payment_method)
