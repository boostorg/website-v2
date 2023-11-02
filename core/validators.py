import os

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class FileTypeValidator:
    """
    Validates that a file is of the permitted types.
    """

    def __init__(self, extensions):
        self.extensions = extensions

    def __call__(self, value):
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in self.extensions:
            raise ValidationError(
                f"Unsupported file extension. Allowed types are: {', '.join(self.extensions)}"  # noqa
            )


image_validator = FileTypeValidator(extensions=[".jpg", ".jpeg", ".png"])


@deconstructible
class MaxFileSizeValidator:
    """
    Validates that a file is not larger than a certain size.
    """

    def __init__(self, max_size):
        self.max_size = max_size

    def __call__(self, value):
        if value.size > self.max_size:
            raise ValidationError(
                f"File too large. Size should not exceed {self.max_size / 1024 / 1024} MB."  # noqa
            )


# 1 MB max file size
max_file_size_validator = MaxFileSizeValidator(max_size=1 * 1024 * 1024)
