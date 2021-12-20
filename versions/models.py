import hashlib
from django.db import models

# Create your models here.


class VersionFile(models.Model):
    Unix = 'Unix'
    Windows = 'Windows'
    OPERATING_SYSTEM_CHOICES = (
        (Unix, 'Unix'),
        (Windows, 'Windows'),
    )
    checksum = models.CharField(max_length=64, unique=True, default=None)
    file = models.FileField(upload_to="uploads/")
    operating_system = models.CharField(
        choices=OPERATING_SYSTEM_CHOICES, max_length=15, null=False, blank=False)
    
    def save(self, *args, **kwargs):
        if self.file is not None:
            if self.checksum is None:
                self.checksum = hashlib.sha256(self.file.name.encode("utf-8")).hexdigest()
            super().save(*args, **kwargs)


class Version(models.Model):
    name = models.CharField(
        max_length=256, null=False, blank=False, help_text="Version name"
    )
    files = models.ManyToManyField(VersionFile)
    release_date = models.DateField(auto_now=False, auto_now_add=False)