import subprocess


ASCIIDOCTOR_COMMAND = ["asciidoctor", "-r", "asciidoctor_boost", "-e", "-o", "-", "-"]


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
        ASCIIDOCTOR_COMMAND,
        check=True,
        capture_output=True,
        text=True,
        input=input,
    )

    # Get the output from the command
    return result.stdout


def convert_md_to_html(input):
    # first convert gfm to asciidoctor
    pandoc = subprocess.Popen(
        ["pandoc", "-f", "gfm", "-t", "asciidoctor"],
        stdout=subprocess.PIPE,
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # then convert asciidoctor to html
    ad = subprocess.Popen(
        ASCIIDOCTOR_COMMAND,
        stdin=pandoc.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    pandoc.stdin.write(input)
    pandoc.stdin.close()
    pandoc_stderr = pandoc.stderr.read()
    stdout, ad_stderr = ad.communicate()
    pandoc.wait()
    assert (
        ad.returncode == 0
    ), f"asciidoctor command returned {ad.returncode}: {ad_stderr}"
    assert (
        pandoc.returncode == 0
    ), f"pandoc command returned {pandoc.returncode}: {pandoc_stderr}"

    return stdout
