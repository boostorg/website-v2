from ..management.commands.load_contributors import (
    extract_email,
    extract_names,
    generate_fake_email,
    get_contributor_data,
    process_author_data,
    process_maintainer_data,
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


def test_process_author_data_(user, library_version):
    library = library_version.library
    assert library.authors.exists() is False
    user.claimed = True
    user.email = "t_testerson@example.com"
    user.save()

    process_author_data(
        ["Tester Testerston <t_testerson -at- example.com>", "Tester2 Testerson2"],
        library,
    )
    library.refresh_from_db()
    assert library.authors.exists()
    assert library.authors.filter(email="t_testerson@example.com").exists()
    assert library.authors.filter(email="tester2_testerson2@example.com").exists()


def test_process_maintainer_data_(user, library_version):
    assert library_version.maintainers.exists() is False
    user.claimed = True
    user.email = "t_testerson@example.com"
    user.save()

    process_maintainer_data(
        ["Tester Testerston <t_testerson -at- example.com>", "Tester2 Testerson2"],
        library_version,
    )
    library_version.refresh_from_db()
    assert library_version.maintainers.exists()
    assert library_version.maintainers.filter(email="t_testerson@example.com").exists()
    assert library_version.maintainers.filter(
        email="tester2_testerson2@example.com"
    ).exists()
