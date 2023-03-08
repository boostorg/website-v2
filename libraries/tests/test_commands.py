from ..management.commands.load_contributors import extract_names


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
