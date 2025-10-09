from django.db import models


class CapturedEmail(models.Model):
    email = models.EmailField()
    referrer = models.CharField(blank=True, default="")
    page_slug = models.CharField(blank=True, default="")

    def __str__(self):
        return self.email

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.pk}): {self}>"
