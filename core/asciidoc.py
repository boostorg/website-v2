import subprocess


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
        input=input,
    )

    # Get the output from the command
    return result.stdout
