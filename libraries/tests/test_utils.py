import os
import pytest
from datetime import datetime
from dateutil.relativedelta import relativedelta

from libraries.utils import (
    conditional_batched,
    decode_content,
    generate_fake_email,
    generate_release_report_filename,
    get_first_last_day_last_month,
    parse_date,
    update_base_tag,
    version_within_range,
    write_content_to_tempfile,
    modernize_boost_slug,
)
from libraries.constants_utils import (
    generate_library_docs_url,
    generate_library_docs_url_v2,
    generate_library_docs_url_v3,
    generate_library_docs_url_v4,
    generate_library_docs_url_bind_v1,
    generate_library_docs_url_bind_v2,
    generate_library_docs_url_math_v1,
    generate_library_docs_url_utility_v1,
    generate_library_docs_url_utility_v2,
    generate_library_docs_url_utility_v3,
    generate_library_docs_url_circular_buffer,
    generate_library_docs_url_core,
    generate_library_docs_url_double_nested_library_html,
    generate_library_docs_url_double_nested_library_htm,
    generate_library_docs_url_numeric,
    generate_library_docs_url_string_ref,
    generate_library_docs_url_string_view,
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


def test_generate_library_docs_url_bind_v1():
    expected = "/doc/libs/boost_1_60_0/libs/bind/doc/html/mem_fn.html"
    assert generate_library_docs_url_bind_v1("boost_1_60_0", "mem_fn") == expected


def test_generate_library_docs_url_bind_v2():
    expected = "/doc/libs/boost_1_49_0/libs/bind/mem_fn.html"
    assert generate_library_docs_url_bind_v2("boost_1_49_0", "mem_fn") == expected


def test_generate_library_docs_url_math_v1():
    expected = "/doc/libs/boost_1_60_0/libs/math/doc/html/gcd_lcm.html"
    assert generate_library_docs_url_math_v1("boost_1_60_0", "gcd_lcm") == expected


def test_generate_library_docs_url_utility_v1():
    expected = "/doc/libs/boost_1_60_0/libs/utility/call_traits.htm"
    assert (
        generate_library_docs_url_utility_v1("boost_1_60_0", "call_traits") == expected
    )


def test_generate_library_docs_url_utility_v2():
    expected = "/doc/libs/boost_1_60_0/libs/utility/identity_type/doc/html/index.html"
    assert (
        generate_library_docs_url_utility_v2("boost_1_60_0", "identity_type")
        == expected
    )


def test_generate_library_docs_url_utility_v3():
    expected = "/doc/libs/boost_1_60_0/libs/utility/in_place_factories.html"
    assert (
        generate_library_docs_url_utility_v3("boost_1_60_0", "in_place_factories")
        == expected
    )


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


def test_conditional_batched():
    # test basic functionality: batch consecutive items that pass condition
    items = [1, 2, 4, 3, 6, 8, 5, 10, 12, 7]
    # even numbers should be batched
    result = list(conditional_batched(items, 2, lambda x: x % 2 == 0))

    # consecutive even numbers get batched, odd numbers are individual, order preserved
    assert result == [(1,), (2, 4), (3,), (6, 8), (5,), (10, 12), (7,)]


def test_conditional_batched_all_pass():
    # test when all items pass the condition
    items = [2, 4, 6, 8, 10]
    result = list(conditional_batched(items, 2, lambda x: x % 2 == 0))

    assert result == [(2, 4), (6, 8), (10,)]


def test_conditional_batched_all_fail():
    # test when all items fail the condition
    items = [1, 3, 5, 7, 9]
    result = list(conditional_batched(items, 2, lambda x: x % 2 == 0))

    assert result == [(1,), (3,), (5,), (7,), (9,)]


def test_conditional_batched_strict_mode():
    # test strict mode with incomplete batch
    items = [2, 4, 6]
    with pytest.raises(ValueError, match="conditional_batched\\(\\): incomplete batch"):
        list(conditional_batched(items, 2, lambda x: x % 2 == 0, strict=True))


def test_conditional_batched_strict_mode_complete():
    # test strict mode with complete batches
    items = [2, 4, 6, 8]
    result = list(conditional_batched(items, 2, lambda x: x % 2 == 0, strict=True))

    assert result == [(2, 4), (6, 8)]


def test_conditional_batched_invalid_n():
    # test invalid batch size
    items = [1, 2, 3]

    with pytest.raises(ValueError, match="n must be at least one"):
        list(conditional_batched(items, 0, lambda x: True))


@pytest.mark.parametrize(
    "html, base_uri, expected",
    [
        # Test basic base tag replacement
        (
            '<html><head><base href="/old/path/"></head><body>content</body></html>',
            "/new/path/",
            '<html><head><base href="/new/path/"></head><body>content</body></html>',
        ),
        # Test with different base tag format (no trailing slash)
        (
            '<base href="https://example.com/docs">',
            "https://newsite.com/documentation",
            '<base href="https://newsite.com/documentation">',
        ),
        # Test multiple base tags (should replace all occurrences)
        (
            '<base href="/old1/"><base href="/old2/">',
            "/new/",
            '<base href="/new/"><base href="/new/">',
        ),
        # Test with empty base URI
        (
            '<base href="/docs/">',
            "",
            '<base href="">',
        ),
        # Test with complex HTML structure
        (
            """<!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <base href="/doc/libs/1_84_0/">
                    <title>Test</title>
                </head>
                <body>content</body>
                </html>""",
            "/doc/libs/latest/",
            """<!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <base href="/doc/libs/latest/">
                    <title>Test</title>
                </head>
                <body>content</body>
                </html>""",
        ),
    ],
)
def test_update_base_tag(html, base_uri, expected):
    """Test update_base_tag replaces base tag href correctly."""
    result = update_base_tag(html, base_uri)
    assert result == expected


def test_update_base_tag_no_base_tag():
    """Test update_base_tag when there is no base tag in the HTML."""
    html = "<html><head><title>Test</title></head><body>content</body></html>"
    base_uri = "/new/path/"
    result = update_base_tag(html, base_uri)
    # Should return the original HTML unchanged since there's no base tag to replace
    assert result == html


@pytest.mark.parametrize(
    "version_slug, published_format, expected_prefix, should_have_timestamp",
    [
        # Published format (no timestamp)
        ("boost-1-84-0", True, "release-report-boost-1-84-0.pdf", False),
        ("boost-1-85-0", True, "release-report-boost-1-85-0.pdf", False),
        # Draft format (with timestamp)
        ("boost-1-84-0", False, "release-report-boost-1-84-0-", True),
        ("boost-1-85-0", False, "release-report-boost-1-85-0-", True),
    ],
)
def test_generate_release_report_filename(
    version_slug, published_format, expected_prefix, should_have_timestamp
):
    """Test generate_release_report_filename generates correct filenames."""
    result = generate_release_report_filename(version_slug, published_format)
    assert result.startswith(expected_prefix)
    assert result.endswith(".pdf")

    if should_have_timestamp:
        # timestamp should be in ISO format (contains 'T' and timezone info)
        assert "T" in result
        # should have the pattern: release-report-{slug}-{timestamp}.pdf
        assert len(result.split("-")) >= 4  # release, report, slug, timestamp
    else:
        # published format should not have a timestamp
        assert "T" not in result
        # should be release-report-{slug}.pdf
        assert result == expected_prefix


def test_generate_release_report_filename_timestamp_format():
    """Test that the timestamp in the filename is a valid ISO format."""
    version_slug = "boost-1-84-0"
    result = generate_release_report_filename(version_slug, published_format=False)

    # extract the timestamp portion (between last dash and .pdf)
    # format: release-report-boost-1-84-0-{timestamp}.pdf
    timestamp_part = result.replace("release-report-boost-1-84-0-", "").replace(
        ".pdf", ""
    )
    # parse it as an ISO format datetime to ensure it's valid
    try:
        datetime.fromisoformat(timestamp_part)
    except ValueError:
        pytest.fail(f"Timestamp '{timestamp_part}' is not a valid ISO format")


def test_modernize_boost_slug():
    """Test that the modernizer turns an old style slug into the correct new style slug"""
    old_slug = "1_81_0"
    new_slug = "boost-1-81-0"
    assert new_slug == modernize_boost_slug(old_slug)
