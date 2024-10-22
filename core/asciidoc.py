import subprocess

from .asciidoc_translators import (
    AtLinkTranslator,
    GithubIssueTranslator,
    GithubPRTranslator,
    PhraseTranslator,
)


def convert_adoc_to_html(input):
    """
    Converts an AsciiDoc file to HTML.

    Note: This returns an html fragment, not the full <html> document with the
    <head> and <body> tags.

    The asciidoctor package is a Ruby gem, which is why we're using subprocess
    to run the command.
    https://docs.asciidoctor.org/asciidoctor/latest/

    :param input: The contents of the AsciiDoc file
    """
    result = subprocess.run(
        ["asciidoctor", "-e", "-o", "-", "-"],
        check=True,
        capture_output=True,
        text=True,
        input=boost_macro_translator(input),
    )

    # Get the output from the command
    return result.stdout


def boost_macro_translator(content: str) -> str:
    parsers = [
        AtLinkTranslator(),
        GithubIssueTranslator(),
        GithubPRTranslator(),
        PhraseTranslator(),
    ]

    def process_lines(lines):
        for line in lines:
            for fn in parsers:
                line = fn(line)
            yield line

    translated_input = []
    for line in process_lines(content.splitlines()):
        translated_input.append(line)

    return "\n".join(translated_input)
