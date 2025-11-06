from django.db import models


class CapturedEmail(models.Model):
    email = models.EmailField()
    first_name = models.CharField(blank=True, default="")
    last_name = models.CharField(blank=True, default="")
    mi = models.CharField(blank=True, default="", verbose_name="M.I.")
    title = models.CharField(blank=True, default="")
    company = models.CharField(blank=True, default="")
    address_city = models.CharField(blank=True, default="")
    address_state = models.CharField(blank=True, default="")
    address_country = models.CharField(blank=True, default="")

    referrer = models.CharField(blank=True, default="")
    page_slug = models.CharField(blank=True, default="")
    opted_out = models.BooleanField(default=False)

    def __str__(self):
        return self.email

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.pk}): {self}>"
