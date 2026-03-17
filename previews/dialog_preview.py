from django_lookbook.preview import LookbookPreview
from django.template import Context, Template


class DialogPreview(LookbookPreview):

    def with_description(self, **kwargs):
        """
        Dialog modal with title, description, and two action buttons.

        Template: `v3/includes/_dialog.html`

        | Variable | Required | Description |
        |---|---|---|
        | `dialog_id` | Yes | Unique ID for this dialog instance |
        | `title` | Yes | Dialog title |
        | `description` | No | Descriptive text below the title |
        | `primary_label` | Yes | Primary action button text |
        | `secondary_label` | Yes | Secondary action button text |
        | `primary_style` | No | Primary button style. Default: "secondary-grey" |
        | `secondary_style` | No | Secondary button style. Default: "primary" |
        | `primary_url` | No | Primary button URL |
        | `secondary_url` | No | Secondary button URL. Default: "#" (closes dialog) |
        """
        template = Template(
            """
        <a href="#demo-dialog-with-desc" class="btn btn-primary">Open dialog</a>
        {% include "v3/includes/_dialog.html" with dialog_id="demo-dialog-with-desc" title="Title of Dialog" description="Description that can go inside of Dialog" primary_url="#_" secondary_url="#_" primary_label="Button" secondary_label="Button" %}
        """
        )
        return template.render(Context({}))
