from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel

from .managers import RenderedContentManager


class RenderedContent(TimeStampedModel):
    """Stores a copy of rendered content. Generally, this content is retrieved
    from the S3 buckets and, if necessary, converted to HTML.

    This model is intended to be used as a cache. If the content is not found,
    it will be retrieved from S3 and stored in this model. If the content is
    found, it will be returned from this model.

    TimeStampedModel adds `created` and `modified` fields:
    https://django-extensions.readthedocs.io/en/latest/model_extensions.html
    """

    cache_key = models.CharField(
        max_length=255,
        unique=True,
        help_text=_("The cache key for the content."),
        db_index=True,
    )
    content_type = models.CharField(
        max_length=255,
        help_text=_("The content type/MIME type."),
        null=True,
        blank=True,
    )
    content_original = models.TextField(
        help_text=_("The original content."), null=True, blank=True
    )
    content_html = models.TextField(
        help_text=_("The rendered HTML content."), null=True, blank=True
    )
    last_updated_at = models.DateTimeField(
        help_text=_("The last time the content was updated in S3."),
        null=True,
        blank=True,
    )

    objects = RenderedContentManager()

    class Meta:
        verbose_name = _("rendered content")
        verbose_name_plural = _("rendered contents")

    def __str__(self):
        return self.cache_key

    def save(self, *args, **kwargs):
        if isinstance(self.content_original, bytes):
            self.content_original = self.content_original.decode("utf-8")
        if isinstance(self.content_html, bytes):
            self.content_html = self.content_html.decode("utf-8")
        if isinstance(self.content_type, bytes):
            self.content_type = self.content_type.decode("utf-8")

        super().save(*args, **kwargs)
