from django.db import models
from django.utils import timezone
from django.conf import settings


class SandboxDocument(models.Model):
    """Model to store asciidoctor sandbox documents."""

    title = models.CharField(max_length=200, help_text="Document title")
    asciidoc_content = models.TextField(blank=True, help_text="Asciidoc source content")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        help_text="User who created this document",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    def __repr__(self):
        return f"<{self.__class__.__name__} object ({self.pk}): {self}>"
