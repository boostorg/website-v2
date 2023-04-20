from django.db import models
from mptt.models import MPTTModel, TreeForeignKey


class MailingListMessage(MPTTModel):
    subject = models.CharField(max_length=255)
    body = models.TextField()
    parent = TreeForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )

    class MPTTMeta:
        order_insertion_by = ["subject"]
