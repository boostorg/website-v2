import djclick as click
import openpyxl

from libraries.models import Library


@click.command()
@click.option(
    "--filename",
    help="Optional filename to import values from. Defaults to 'boost_cxx_ceilings.xlsx",
    default="boost_cxx_ceilings.xlsx",
)
def command(filename):
    click.echo(f"Opening workbook: {filename}")
    wb = openpyxl.load_workbook(filename)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = next(rows)  # get the header row
    data = []
    for row in rows:
        data.append(dict(zip(header, row)))
    click.echo(f"Found {len(data)} rows to update.")
    libs_to_update = []
    libs_not_updated = []
    libs = Library.objects.all()
    for obj in data:
        try:
            lib = libs.get(key=obj.get("Library"))
        except Library.DoesNotExist:
            libs_not_updated.append(obj.get("Library"))
            continue
        lib.cpp_standard_maximum = obj.get("CI max tested")
        libs_to_update.append(lib)
    click.echo(f"Was able to match {len(libs_to_update)} libraries.")
    if len(libs_not_updated) > 0:
        click.echo(f"Was unable to match libraries: {(', ').join(libs_not_updated)}.")
    Library.objects.bulk_update(libs_to_update, fields=["cpp_standard_maximum"])
    click.echo("Finished.")
