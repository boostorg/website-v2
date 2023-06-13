from datetime import datetime
import os

from libraries.utils import (
    decode_content,
    generate_fake_email,
    parse_date,
    write_content_to_tempfile,
)


def test_decode_content():
    byte_content = b"This is a test content"
    str_content = "This is a test content"
    decoded_byte_content = decode_content(byte_content)
    decoded_str_content = decode_content(str_content)
    assert decoded_byte_content == str_content
    assert decoded_str_content == str_content


def test_generate_fake_email():
    sample = "Tester de Testerson"
    expected = "tester_de_testerson"
    result = generate_fake_email(sample)
    assert expected in result
    assert "@example.com" in result


def test_parse_date_iso():
    expected = datetime.now()
    result = parse_date(expected.isoformat())
    assert expected == result


def test_parse_date_str():
    expected = datetime.now()
    input_date = f"{expected.month}-{expected.day}-{expected.year}"
    result = parse_date(input_date)
    assert expected.date() == result.date()


def test_parse_date_str_none():
    expected = None
    result = parse_date("")
    assert expected == result


def test_write_content_to_tempfile():
    content = b"This is a test content"
    temp_file = write_content_to_tempfile(content)
    assert os.path.exists(temp_file.name)
    with open(temp_file.name, "rb") as f:
        file_content = f.read()
    assert file_content == content
    os.remove(temp_file.name)
