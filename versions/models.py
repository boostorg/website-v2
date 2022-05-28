import hashlib
from django.db import models

from .managers import VersionManager


class Version(models.Model):
    name = models.CharField(
        max_length=256, null=False, blank=False, help_text="Version name"
    )
    release_date = models.DateField(auto_now=False, auto_now_add=False)
    description = models.TextField(blank=True)
    active = models.BooleanField(
        default=True,
        help_text="Control whether or not this version is available on the website",
    )

    objects = VersionManager()

    def __str__(self):
        return self.name


class VersionFile(models.Model):
    Unix = "Unix"
    Windows = "Windows"
    OPERATING_SYSTEM_CHOICES = (
        (Unix, "Unix"),
        (Windows, "Windows"),
    )

    version = models.ForeignKey(Version, related_name="files", on_delete=models.CASCADE)
    operating_system = models.CharField(
        choices=OPERATING_SYSTEM_CHOICES, max_length=15, default=Unix
    )
    checksum = models.CharField(max_length=64, unique=True, default=None)
    file = models.FileField(upload_to="uploads/")

    def save(self, *args, **kwargs):
        if self.file is not None:
            if self.checksum is None:
                self.checksum = hashlib.sha256(
                    self.file.file.encode("utf-8")
                ).hexdigest()
            super().save(*args, **kwargs)
