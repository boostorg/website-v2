from django_lookbook.preview import LookbookPreview
from django.template import Context, Template


class TooltipsPreview(LookbookPreview):

    def tooltip_buttons_with_text(self, **kwargs):
        """
        Tooltip buttons that include visible button text alongside the icon.

        Template: `v3/includes/_button_tooltip_v3.html`

        | Variable | Required | Description |
        |---|---|---|
        | `label` | Yes | Tooltip content text |
        | `position` | No | Tooltip position: `top`, `right`, `bottom`, `left`. Default: `bottom` |
        | `button_text` | No | Visible text on the trigger button |
        | `url` | No | If set, renders as `<a>` instead of `<button>` |
        | `aria_label` | No | Accessible name. Default: "More information" |
        | `icon_html` | No | Custom icon HTML; defaults to info-box icon |
        | `tooltip_id` | No | Unique id suffix (for multiple tooltips with same label) |
        """
        template = Template(
            '<div style="display: flex; gap: 16px; flex-wrap: wrap; align-items: center;">'
            '{% include "v3/includes/_button_tooltip_v3.html" with label="Top" position="top" button_text="Help" %}'
            '{% include "v3/includes/_button_tooltip_v3.html" with label="Right" position="right" button_text="Help" %}'
            '{% include "v3/includes/_button_tooltip_v3.html" with label="Bottom" position="bottom" button_text="Help" %}'
            '{% include "v3/includes/_button_tooltip_v3.html" with label="Left" position="left" button_text="Help" %}'
            '{% include "v3/includes/_button_tooltip_v3.html" with label="More information here" position="bottom" button_text="Info" %}'
            "</div>"
        )
        return template.render(Context({}))

    def tooltip_icon_only(self, **kwargs):
        """
        Icon-only tooltip buttons (no visible button text, just the icon trigger).
        """
        template = Template(
            '<div style="display: flex; gap: 16px; flex-wrap: wrap; align-items: center;">'
            '{% include "v3/includes/_button_tooltip_v3.html" with label="Top" position="top" tooltip_id="ico-top" %}'
            '{% include "v3/includes/_button_tooltip_v3.html" with label="Right" position="right" tooltip_id="ico-right" %}'
            '{% include "v3/includes/_button_tooltip_v3.html" with label="Bottom" position="bottom" tooltip_id="ico-bottom" %}'
            '{% include "v3/includes/_button_tooltip_v3.html" with label="Left" position="left" tooltip_id="ico-left" %}'
            '{% include "v3/includes/_button_tooltip_v3.html" with label="Icon only tooltip" position="bottom" tooltip_id="ico-only" %}'
            "</div>"
        )
        return template.render(Context({}))
