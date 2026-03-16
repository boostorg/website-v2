import json

from django_lookbook.preview import LookbookPreview
from django.template.loader import render_to_string


class FormsPreview(LookbookPreview):

    def text_field(self, **kwargs):
        """
        Basic text input field.

        Template: `v3/includes/_field_text.html`

        | Variable | Required | Description |
        |---|---|---|
        | `name` | Yes | Input name attribute |
        | `label` | No | Label text |
        | `placeholder` | No | Placeholder text |
        | `value` | No | Pre-filled value |
        | `type` | No | Input type. Default: "text" |
        | `help_text` | No | Help text below the field |
        | `error` | No | Error message (activates error state) |
        | `icon_left` | No | Icon name for left slot |
        | `submit_icon` | No | Icon name for a submit button in right slot |
        | `submit_label` | No | Aria-label for submit button |
        | `required` | No | Adds required attribute |
        | `disabled` | No | Adds disabled attribute |
        | `extra_class` | No | Additional CSS classes |
        """
        return render_to_string(
            "v3/includes/_field_text.html",
            {
                "name": "ex_basic",
                "label": "Text field",
                "placeholder": "Enter text...",
            },
        )

    def text_field_with_icon(self, **kwargs):
        """
        Text field with a left-side icon (e.g. search).
        """
        return render_to_string(
            "v3/includes/_field_text.html",
            {
                "name": "ex_search",
                "label": "With icon",
                "placeholder": "Search...",
                "icon_left": "search",
            },
        )

    def text_field_error(self, **kwargs):
        """
        Text field in error state with a validation message.
        """
        return render_to_string(
            "v3/includes/_field_text.html",
            {
                "name": "ex_error",
                "label": "Error state",
                "placeholder": "Enter value",
                "error": "This field is required.",
            },
        )

    def checkbox(self, **kwargs):
        """
        Checkbox field.

        Template: `v3/includes/_field_checkbox.html`

        | Variable | Required | Description |
        |---|---|---|
        | `name` | Yes | Input name attribute |
        | `label` | Yes | Label text |
        | `checked` | No | If truthy, checkbox is checked |
        | `value` | No | Input value. Default: "on" |
        | `required` | No | Adds required attribute |
        | `disabled` | No | Adds disabled attribute |
        | `extra_class` | No | Additional CSS classes |
        """
        return render_to_string(
            "v3/includes/_field_checkbox.html",
            {
                "name": "ex_agree",
                "label": "I agree to the terms and conditions",
            },
        )

    def combo_field(self, **kwargs):
        """
        Searchable combo (dropdown) field. Requires Alpine.js.

        Template: `v3/includes/_field_combo.html`

        | Variable | Required | Description |
        |---|---|---|
        | `name` | Yes | Input name attribute |
        | `label` | No | Label text |
        | `placeholder` | No | Placeholder when nothing selected |
        | `options_json` | Yes | JSON string of options `[{"value":"...","label":"..."}]` |
        | `selected` | No | Pre-selected value |
        | `help_text` | No | Help text |
        | `error` | No | Error message |
        | `required` | No | Adds required attribute |
        | `extra_class` | No | Additional CSS classes |
        """
        options = json.dumps(
            [
                {"value": "asio", "label": "Asio"},
                {"value": "beast", "label": "Beast"},
                {"value": "filesystem", "label": "Filesystem"},
                {"value": "json", "label": "JSON"},
                {"value": "spirit", "label": "Spirit"},
            ]
        )
        return render_to_string(
            "v3/includes/_field_combo.html",
            {
                "name": "ex_library",
                "label": "Combo (searchable)",
                "placeholder": "Search libraries...",
                "options_json": options,
            },
        )

    def multiselect_field(self, **kwargs):
        """
        Multi-select dropdown field. Requires Alpine.js.

        Template: `v3/includes/_field_multiselect.html`

        | Variable | Required | Description |
        |---|---|---|
        | `name` | Yes | Input name attribute |
        | `label` | No | Label text |
        | `placeholder` | No | Placeholder when nothing selected |
        | `options_json` | Yes | JSON string of options |
        | `selected_json` | No | JSON string of pre-selected values |
        | `help_text` | No | Help text |
        | `error` | No | Error message |
        | `extra_class` | No | Additional CSS classes |
        """
        options = json.dumps(
            [
                {"value": "algorithms", "label": "Algorithms"},
                {"value": "containers", "label": "Containers"},
                {"value": "io", "label": "I/O"},
                {"value": "math", "label": "Math & Numerics"},
                {"value": "networking", "label": "Networking"},
            ]
        )
        return render_to_string(
            "v3/includes/_field_multiselect.html",
            {
                "name": "ex_categories",
                "label": "Multi-select",
                "placeholder": "Select categories...",
                "options_json": options,
            },
        )
