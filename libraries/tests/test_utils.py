from datetime import datetime

from libraries.utils import extract_email, generate_email, parse_date


def test_extract_email():
    expected = "t_testerson@example.com"
    result = extract_email("Tester Testerston <t_testerson -at- example.com>")
    assert expected == result


def test_extract_email_no_email():
    expected = None
    result = extract_email("Tester Testeron")
    assert expected == result


def test_generate_email():
    expected = "tester_testerson@example.com"
    result = generate_email("Tester Testerson")
    assert expected == result


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
