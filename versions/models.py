import hashlib
from django.db import models
from django.utils.text import slugify

from .managers import VersionManager, VersionFileManager


class Version(models.Model):
    name = models.CharField(
        max_length=256, null=False, blank=False, help_text="Version name"
    )
    slug = models.SlugField(blank=True, null=True)
    release_date = models.DateField(auto_now=False, auto_now_add=False)
    description = models.TextField(blank=True)
    active = models.BooleanField(
        default=True,
        help_text="Control whether or not this version is available on the website",
    )

    objects = VersionManager()

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.get_slug()
        return super(Version, self).save(*args, **kwargs)

    def get_slug(self):
        if self.slug:
            return self.slug
        name = self.name.replace(".", " ")
        return slugify(name)[:50]


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

    objects = VersionFileManager()

    def save(self, *args, **kwargs):
        # Calculate sha256 hash
        if self.file is not None and self.checksum is None:
            h = hashlib.sha256()
            with self.file.open("rb") as f:
                data = f.read()
                while data:
                    h.update(data)
                    data = f.read()

            self.checksum = h.hexdigest()

        super().save(*args, **kwargs)
