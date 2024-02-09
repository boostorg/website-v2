import os
import pytest
from datetime import datetime
from dateutil.relativedelta import relativedelta

from libraries.utils import (
    decode_content,
    generate_fake_email,
    generate_library_docs_url,
    generate_library_docs_url_v2,
    generate_library_docs_url_v3,
    generate_library_docs_url_v4,
    generate_library_docs_url_v5,
    generate_library_docs_url_circular_buffer,
    generate_library_docs_url_core,
    generate_library_docs_url_double_nested_library_htm,
    generate_library_docs_url_double_nested_library_html,
    generate_library_docs_url_numeric,
    generate_library_docs_url_string_ref,
    generate_library_docs_url_string_view,
    get_first_last_day_last_month,
    parse_date,
    version_within_range,
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


def test_generate_library_docs_url():
    expected = "/doc/libs/boost_1_84_0/libs/detail/doc/html/index.html"
    assert generate_library_docs_url("boost_1_84_0", "detail") == expected


def test_generate_library_docs_url_v2():
    expected = "/doc/libs/1_73_0/libs/io/doc/html/io.html"
    assert generate_library_docs_url_v2("boost_1_73_0", "io") == expected


def test_generate_library_docs_url_v3():
    expected = "/doc/libs/boost_1_72_0/libs/io/doc/index.html"
    assert generate_library_docs_url_v3("boost_1_72_0", "io") == expected


def test_generate_library_docs_url_v4():
    expected = "/doc/libs/boost_1_32_0/doc/html/any.html"
    assert generate_library_docs_url_v4("boost_1_32_0", "any") == expected


def test_generate_library_docs_url_v5():
    expected = "/doc/libs/boost_1_60_0/libs/utility/call_traits.htm"
    assert generate_library_docs_url_v5("boost_1_60_0", "call_traits") == expected


def test_generate_library_docs_url_circular_buffer():
    expected = "/doc/libs/boost_1_54_0/libs/circular_buffer/doc/circular_buffer.html"
    assert (
        generate_library_docs_url_circular_buffer("boost_1_54_0", "circular_buffer")
        == expected
    )


def test_generate_library_docs_url_core():
    assert generate_library_docs_url_core("boost_1_60_0", "enable_if")


def test_generate_library_docs_url_double_nested_library_html():
    expected = "/doc/libs/boost_1_60_0/libs/dynamic_bitset/dynamic_bitset.html"
    assert (
        generate_library_docs_url_double_nested_library_html(
            "boost_1_60_0", "dynamic_bitset"
        )
        == expected
    )


def test_generate_library_docs_url_double_nested_library_htm():
    expected = "/doc/libs/boost_1_60_0/libs/dynamic_bitset/dynamic_bitset.htm"
    assert (
        generate_library_docs_url_double_nested_library_htm(
            "boost_1_60_0", "dynamic_bitset"
        )
        == expected
    )


def test_generate_library_docs_url_numeric():
    expected = "/doc/libs/boost_1_60_0/libs/numeric/interval/doc/interval.htm"
    assert generate_library_docs_url_numeric("boost_1_60_0", "interval") == expected


def test_generate_library_docs_ur_string_ref():
    expected = "/doc/libs/boost_1_72_0/libs/utility/doc/html/string_ref.html"
    assert (
        generate_library_docs_url_string_ref("boost_1_72_0", "string_ref") == expected
    )


def test_generate_library_docs_url_string_view():
    expected = "/doc/libs/boost_1_72_0/libs/utility/doc/html/utility/utilities/string_view.html"  # noqa
    assert (
        generate_library_docs_url_string_view("boost_1_72_0", "string_view") == expected
    )


@pytest.mark.parametrize(
    "version, min_version, max_version, expected",
    [
        # Case: No version restrictions
        ("boost-1.84.0", None, None, True),
        # Case: Version meets minimum version requirement
        ("boost-1.84.0", "boost-1.83.0", None, True),
        # Case: Version does not meet minimum version requirement
        ("boost-1.82.0", "boost-1.83.0", None, False),
        # Case: Version meets maximum version requirement
        ("boost-1.84.0", None, "boost-1.85.0", True),
        # Case: Version does not meet maximum version requirement
        ("boost-1.86.0", None, "boost-1.85.0", False),
        # Case: Version is between min and max version
        ("boost-1.84.0", "boost-1.83.0", "boost-1.85.0", True),
        # Case: Version is exactly min version
        ("boost-1.83.0", "boost-1.83.0", "boost-1.85.0", True),
        # Case: Version is exactly max version
        ("boost-1.85.0", "boost-1.83.0", "boost-1.85.0", True),
        # Case: Version is below min version
        ("boost-1.82.0", "boost-1.83.0", "boost-1.85.0", False),
        # Case: Version is above max version
        ("boost-1.86.0", "boost-1.83.0", "boost-1.85.0", False),
    ],
)
def test_version_within_range(version, min_version, max_version, expected):
    assert version_within_range(version, min_version, max_version) == expected


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
