from os import getcwd, makedirs
from unittest.mock import patch

import pytest


from core.asciidoc import (
    convert_adoc_to_html,
    boost_macro_translator,
)
from core.asciidoc_translators import (
    GithubIssueTranslator,
    GithubPRTranslator,
    PhraseTranslator,
    AtLinkTranslator,
)


def test_convert_adoc_to_html_subprocess():
    # The content of the sample adoc file
    sample_adoc_content = "= Document Title\n\nThis is a sample document.\n"

    # Execute the task
    with patch("core.asciidoc.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "html_content"
        result = convert_adoc_to_html(sample_adoc_content)
    assert result == "html_content"


def test_convert_adoc_to_html_content():
    """Test the process_adoc_to_html_content function."""
    content = "sample"
    expected_html = '<div class="paragraph">\n<p>sample</p>\n</div>\n'  # noqa: E501

    result = convert_adoc_to_html(content)
    assert result == expected_html


def test_at_link_asciidoc_translator():
    filter = AtLinkTranslator()
    content = "at::/tools/build/doc/html/#_version_5_1_0[B2 version 5.1.0]"
    expected_result = "link:/tools/build/doc/html/#_version_5_1_0[B2 version 5.1.0]"
    translator_result = filter(content)
    assert translator_result == expected_result


def test_heading_asciidoc_translator():
    translator = PhraseTranslator()
    content = "phrase::[library,Hi!]"
    expected_result = "[.library]#Hi!#"
    translator_result = translator(content)
    assert translator_result == expected_result


def test_github_pr_asciidoc_translator():
    translator = GithubPRTranslator()
    content = "github_pr::[geometry,1247]"
    expected_result = "https://github.com/boostorg/geometry/pull/1247[PR#1247]"
    translator_result = translator(content)
    assert translator_result == expected_result


def test_github_issue_asciidoc_translator():
    translator = GithubIssueTranslator()
    content = "github_issue::[geometry,1231]"
    expected_result = "https://github.com/boostorg/geometry/issues/1231[#1231]"
    translator_result = translator(content)
    assert translator_result == expected_result


def test_boost_translate_phrase_nested():
    content = "phrase::[library,at::/libs/charconv/[Charconv:]]"
    expected_result = "[.library]#link:/libs/charconv/[Charconv:]#"
    filter_result = boost_macro_translator(content)
    assert filter_result == expected_result


@pytest.mark.asciidoctor
def test_asciidoc_translated():
    # for dev, change this to false, and updaet the test_pytest_asciidoctor run
    #  command to include "-v /tmp/asciidocs:/tmp/asciidocs" after "run"
    local_test = False
    expected_output = open(f"{getcwd()}/core/tests/content/asciidoc.html").read()
    adoc_file_path = f"{getcwd()}/core/tests/content/asciidoc.adoc"
    output = convert_adoc_to_html(open(adoc_file_path).read())
    if local_test:
        makedirs("/tmp/asciidocs", exist_ok=True)
        open("/tmp/asciidocs/tmp.html", "w").write(output)
    assert output == expected_output
