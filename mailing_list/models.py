from django.db import models
from django.contrib.auth import get_user_model
from mptt.models import MPTTModel, TreeForeignKey
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class MailingListMessage(MPTTModel):
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text=_("The registered user who sent the message."),
    )
    sender_email = models.EmailField(
        null=True, blank=True, help_text=_("The email address of the sender.")
    )
    sender_display = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=_("The display name of the sender."),
    )
    subject = models.CharField(
        max_length=255, help_text=_("The subject of the message.")
    )
    body = models.TextField(help_text=_("The body of the message."))
    parent = TreeForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
        help_text=_("The parent message to which this message is a reply."),
    )
    sent_at = models.DateTimeField(
        help_text=_("The date and time when the message was sent.")
    )

    class MPTTMeta:
        order_insertion_by = ["-sent_at"]
