"""Forms shared across apps, for surfaces that don't belong to a single app."""

from django import forms
from django.conf import settings

from core.validators import downscale_image_file_size_validator, image_validator
from news.utils import downsize_uploaded_image


class WysiwygImageUploadForm(forms.Form):
    """Validates an image dropped into the V3 WYSIWYG editor.

    Deliberately the same gate as the V3 post forms apply to a cover image
    (`news.forms.V3BlogPostForm`) — editor images end up in the same content.
    """

    image = forms.ImageField(
        validators=[image_validator, downscale_image_file_size_validator]
    )

    def clean_image(self):
        image = self.cleaned_data["image"]
        if image.size > settings.DOWNSCALE_IMAGE_THRESHOLD:
            return downsize_uploaded_image(image)
        return image
