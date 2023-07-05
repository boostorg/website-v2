from datetime import datetime
from dateutil.relativedelta import relativedelta
import os

from libraries.utils import (
    decode_content,
    generate_fake_email,
    get_first_last_day_last_month,
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


def test_get_first_last_day_last_month():
    first_day, last_day = get_first_last_day_last_month()

    # Assert that the first day is indeed the first day of the month
    assert first_day.day == 1

    # Assert that the last day is the last day of the month
    assert (last_day + relativedelta(days=1)).day == 1

    # Assert that both dates are less than today's date
    assert first_day < datetime.now()
    assert last_day < datetime.now()

    # Assert that both dates belong to the same month and year
    assert first_day.month == last_day.month
    assert first_day.year == last_day.year


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
