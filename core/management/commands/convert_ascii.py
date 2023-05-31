from django.conf import settings
import djclick as click
import subprocess
import os


@click.command()
@click.argument("source_filename")
def command(source_filename):
    """Runs Asciidoctor to convert an AsciiDoc file to HTML

    Note: Asiidoctor is a Ruby gem that is installed as part of the Dockerfile.
    That is why subprocess.run is used instead of the asciidoctor Python package,
    which is not sufficiently up-to-date to support the latest AsciiDoc features.
    """

    base_dir = settings.BASE_DIR
    source_file = os.path.join(base_dir, source_filename)
    destination_file = os.path.join(
        base_dir, f"{os.path.splitext(source_filename)[0]}.html"
    )

    click.echo(f"Running Asciidoctor on {source_file}...")
    subprocess.run(["asciidoctor", "-o", destination_file, source_file], check=True)
    click.secho(f"Converted {source_file} to HTML at {destination_file}!", fg="green")
