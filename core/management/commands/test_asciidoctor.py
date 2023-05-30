import djclick as click
import subprocess


@click.command()
@click.argument("source_file", type=click.Path(exists=True))
@click.argument("destination_file", type=click.Path())
def command(source_file, destination_file):
    """Runs Asciidoctor to convert an AsciiDoc file to HTML"""
    click.echo(f"Running Asciidoctor on {source_file}...")
    subprocess.run(["asciidoctor", "-o", destination_file, source_file], check=True)
    click.echo(f"Converted {source_file} to HTML at {destination_file}!")
