import hashlib
from django.db import models

# Create your models here.


class Version(models.Model):
    name = models.CharField(
        max_length=256, null=False, blank=False, help_text="Version name"
    )
    checksum = models.CharField(max_length=64, unique=True, default=None)
    file = models.FileField(upload_to="uploads/")
    release_date = models.DateField(auto_now=False, auto_now_add=False)

    def save(self, *args, **kwargs):
        if self.checksum is None:
            self.checksum = hashlib.sha256(self.name.encode("utf-8")).hexdigest()
        super().save(*args, **kwargs)
