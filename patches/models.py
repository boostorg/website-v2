from django.db import models


# Create your models here.
class LibraryPatch(models.Model):
    """
    Represents a patch to a specific library of a specific version of a given
    boost library.
    """

    library_version = models.ForeignKey(
        "libraries.LibraryVersion",
        on_delete=models.CASCADE,
        help_text="Library version that this patch applies to. Will be used to sort and display this patch.",
    )
    patch_name = models.CharField(
        max_length=256,
        help_text="A descriptive name of this patch. Also used to generate the slug for the patch page.",
        unique=True,
    )
    patch_file = models.FileField(help_text="Patch File generated from the patch diff.")

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse(
            "patches-urls:detail-view",
            kwargs={
                "version_slug": self.library_version.version.slug,
                "patch_name": self.patch_name,
            },
        )

    def __str__(self):
        return self.patch_name
