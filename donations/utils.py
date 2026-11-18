from stripe import StripeClient

from django.conf import settings

client = StripeClient(settings.STRIPE_PRIVATE_KEY)


def get_prices_for_product(prod_id: str):
    return client.v1.prices.list({"product": prod_id})
