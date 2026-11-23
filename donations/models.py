from uuid import uuid4
from django.db import models

from wagtail.snippets.models import register_snippet
from wagtail.admin.panels import FieldPanel


@register_snippet
class CharitableDonation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    donation_name = models.CharField(max_length=255, editable=False)
    email = models.EmailField(editable=False)
    amount = models.PositiveIntegerField(editable=False)
    stripe_payment_id = models.CharField(max_length=255, editable=False)
    corporation_name = models.CharField(
        max_length=255, editable=False, blank=True, default=""
    )
    uuid = models.UUIDField(default=uuid4())

    def __str__(self):
        return (
            f"{self.donation_name} - {self.display_amount()} - {self.created_at.date()}"
        )

    def display_amount(self):
        return f"${str(self.amount)[:-2]}"

    def send_thank_you_email(self):
        pass

    panels = [
        FieldPanel("created_at", read_only=True),
        FieldPanel("donation_name", read_only=True),
        FieldPanel("email", read_only=True),
        FieldPanel("amount", read_only=True),
        FieldPanel("stripe_payment_id", read_only=True),
        FieldPanel("corporation_name", read_only=True),
        FieldPanel("uuid", read_only=True),
    ]
