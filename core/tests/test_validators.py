#
# Copyright (c) 2024 The C++ Alliance, Inc. (https://cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/boostorg/website-v2
#
import pytest

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from ..validators import FileTypeValidator, MaxFileSizeValidator


def test_file_type_validator():
    """
    Eensure validator only allows specific file extensions.
    """
    validator = FileTypeValidator(extensions=[".jpg", ".png"])

    # Valid file types
    valid_file = SimpleUploadedFile(
        "test.jpg", b"file_content", content_type="image/jpeg"
    )
    validator(valid_file)

    valid_file = SimpleUploadedFile(
        "test.png", b"file_content", content_type="image/jpeg"
    )
    validator(valid_file)

    # Invalid file type
    invalid_file = SimpleUploadedFile(
        "test.txt", b"file_content", content_type="text/plain"
    )
    with pytest.raises(ValidationError):
        validator(invalid_file)


def test_max_file_size_validator():
    """
    Ensure the validator enforces the file size limit.
    """
    # 1MB max file size
    validator = MaxFileSizeValidator(max_size=1 * 1024 * 1024)

    # Valid file size
    valid_file = SimpleUploadedFile(
        "small.jpg", b"a" * (1 * 1024 * 1024 - 1), content_type="image/jpeg"
    )
    validator(valid_file)  # Should not raise

    # Invalid file size
    invalid_file = SimpleUploadedFile(
        "large.jpg", b"a" * (1 * 1024 * 1024 + 1), content_type="image/jpeg"
    )
    with pytest.raises(ValidationError) as exc_info:
        validator(invalid_file)

    assert "File too large" in str(exc_info.value)
