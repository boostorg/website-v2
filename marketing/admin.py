from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields

from marketing.models import CapturedEmail


class CapturedEmailResource(resources.ModelResource):
    email = fields.Field(column_name="Email", attribute="email")
    first_name = fields.Field(column_name="Name (First Name)", attribute="first_name")
    last_name = fields.Field(column_name="Name (Last Name)", attribute="last_name")
    mi = fields.Field(column_name="Name (M.I.)", attribute="mi")
    title = fields.Field(column_name="Title", attribute="title")
    company = fields.Field(column_name="Company", attribute="company")
    address_city = fields.Field(column_name="Address (City)", attribute="address_city")
    address_state = fields.Field(
        column_name="Address (State)", attribute="address_state"
    )
    address_country = fields.Field(
        column_name="Address (Country)", attribute="address_country"
    )

    class Meta:
        model = CapturedEmail
        # Use email as the natural key so re-imports update instead of duplicating
        import_id_fields = ["email"]
        skip_unchanged = True
        report_skipped = True
        fields = (
            "email",
            "first_name",
            "last_name",
            "mi",
            "title",
            "company",
            "address_city",
            "address_state",
            "address_country",
        )


@admin.register(CapturedEmail)
class CapturedEmailAdmin(ImportExportModelAdmin):
    resource_class = CapturedEmailResource
    list_display = (
        "email",
        "first_name",
        "last_name",
        "company",
        "address_city",
        "address_state",
        "address_country",
    )
