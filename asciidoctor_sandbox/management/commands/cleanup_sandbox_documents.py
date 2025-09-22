import djclick as click

from asciidoctor_sandbox.tasks import cleanup_old_sandbox_documents


@click.command()
def command():
    """Clean up old sandbox documents based on the configured retention period."""
    click.echo("Starting sandbox document cleanup...")

    # Run the task synchronously
    cleanup_old_sandbox_documents()

    click.echo(
        click.style("Sandbox document cleanup completed successfully.", fg="green")
    )
