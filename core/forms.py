"""Forms shared across apps, for surfaces that don't belong to a single app."""

from django import forms
from django.conf import settings

from core.validators import downscale_image_file_size_validator, image_validator
from news.utils import downsize_uploaded_image


class WysiwygImageUploadForm(forms.Form):
    """Validates an image dropped into the V3 WYSIWYG editor.

    Mirrors the limits the V3 post forms already apply to their cover image
    (`news.forms.V3BlogPostForm`): jpg/png only, 5 MB ceiling, and anything over
    `DOWNSCALE_IMAGE_THRESHOLD` re-encoded to a smaller webp before it is
    stored. Editor images are pasted into user-visible content, so they go
    through the same gate rather than a looser one.
    """

    image = forms.ImageField(
        validators=[image_validator, downscale_image_file_size_validator]
    )

    def clean_image(self):
        """Downscale oversized uploads, as the post forms do."""
        image = self.cleaned_data["image"]
        if image.size > settings.DOWNSCALE_IMAGE_THRESHOLD:
            return downsize_uploaded_image(image)
        return image
