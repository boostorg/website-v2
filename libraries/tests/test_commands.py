from ..management.commands.load_contributors import (
    extract_email,
    extract_names,
    generate_fake_email,
    get_contributor_data,
)


def test_extract_names():
    sample = "Tester Testerson <tester -at- gmail.com>"
    expected = ["Tester", "Testerson"]
    result = extract_names(sample)
    assert expected == result

    sample = "Tester Testerson"
    expected = ["Tester", "Testerson"]
    result = extract_names(sample)
    assert expected == result

    sample = "Tester de Testerson <tester -at- gmail.com>"
    expected = ["Tester de", "Testerson"]
    result = extract_names(sample)
    assert expected == result

    sample = "Tester de Testerson"
    expected = ["Tester de", "Testerson"]
    result = extract_names(sample)
    assert expected == result


def test_generate_fake_email():
    sample = "Tester de Testerson"
    expected = "tester_de_testerson"
    result = generate_fake_email(sample)
    assert expected in result
    assert "@example.com" in result


def test_extract_email():
    expected = "t_testerson@example.com"
    result = extract_email("Tester Testerston <t_testerson -at- example.com>")
    assert expected == result

    expected = "t.t.testerson@example.com"
    result = extract_email("Tester Testerston <t.t.testerson -at- example.com>")
    assert expected == result

    expected = "t.t.testerson@example.sample.com"
    result = extract_email("Tester Testerston <t.t.testerson -at- example.sample.com> ")
    assert expected == result

    expected = None
    result = extract_email("Tester Testeron")
    assert expected == result


def test_get_contributor_data():
    sample = "Tester Testerson <tester -at- gmail.com>"
    expected = {
        "meta": sample,
        "valid_email": True,
        "email": "tester@gmail.com",
        "first_name": "Tester",
        "last_name": "Testerson",
    }
    result = get_contributor_data(sample)
    assert expected == result

    sample = "Tester Testerson"
    expected = {
        "meta": sample,
        "valid_email": False,
        "first_name": "Tester",
        "last_name": "Testerson",
    }
    result = get_contributor_data(sample)
    assert expected["meta"] == result["meta"]
    assert expected["valid_email"] is False
    assert expected["first_name"] == result["first_name"]
    assert expected["last_name"] == result["last_name"]
    assert "email" in result
