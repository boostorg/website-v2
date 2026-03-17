from django_lookbook.preview import LookbookPreview
from django.template import Context, Template


class ButtonsPreview(LookbookPreview):

    def default_buttons(self, **kwargs):
        """
        All button style variants in their default state.

        Available styles: `primary`, `secondary`, `green`, `yellow`, `teal`, `error`.

        Template: `v3/includes/_button.html`

        | Variable | Required | Description |
        |---|---|---|
        | `label` | Yes | Button text |
        | `url` | No | If set, renders as `<a>` instead of `<button>` |
        | `style` | No | One of: primary, secondary, green, yellow, teal, error. Default: primary |
        | `icon_html` | No | HTML for a leading icon (use with `|safe`) |
        | `type` | No | Button type attribute. Default: "button" |
        | `extra_classes` | No | Additional CSS classes |
        | `aria_label` | No | Accessible label; defaults to `label` |
        """
        template = Template(
            """
        {% load static %}
        <div class="btn-row" style="margin-bottom: 12px;">
          <button type="button" class="btn btn-primary">Primary</button>
          <button type="button" class="btn btn-secondary">Secondary</button>
          <button type="button" class="btn btn-green">Green</button>
          <button type="button" class="btn btn-yellow">Yellow</button>
          <button type="button" class="btn btn-teal">Teal</button>
          <button type="button" class="btn btn-error">Error</button>
        </div>
        """
        )
        return template.render(Context({}))

    def hovered_buttons(self, **kwargs):
        """
        All button style variants with the `data-hover` attribute applied to
        force the hover appearance without user interaction.

        This is useful for visual regression testing of hover states.
        """
        template = Template(
            """
        <div class="btn-row" style="margin-bottom: 12px;">
          <button type="button" class="btn btn-primary" data-hover>Primary (Hovered)</button>
          <button type="button" class="btn btn-secondary" data-hover>Secondary (Hovered)</button>
          <button type="button" class="btn btn-green" data-hover>Green (Hovered)</button>
          <button type="button" class="btn btn-yellow" data-hover>Yellow (Hovered)</button>
          <button type="button" class="btn btn-teal" data-hover>Teal (Hovered)</button>
          <button type="button" class="btn btn-error" data-hover>Error (Hovered)</button>
        </div>
        """
        )
        return template.render(Context({}))

    def hero_buttons(self, **kwargs):
        """
        Hero buttons — larger buttons intended for hero / landing sections.
        Shows default and hovered states for both primary and secondary.

        Template: `v3/includes/_button_hero.html`

        | Variable | Required | Description |
        |---|---|---|
        | `label` | Yes | Button text |
        | `url` | No | If set, renders as `<a>` |
        | `icon_name` | No | Icon name. Default: "arrow-right" |
        | `style` | No | "primary" or "secondary". Default: "primary" |
        | `type` | No | Button type attribute |
        | `extra_classes` | No | Additional CSS classes |
        """
        template = Template(
            """
        {% load static %}
        <div style="display: flex; flex-direction: column; gap: 16px; align-items: flex-start;">
          <button type="button" class="btn btn-hero btn-primary">
            <span class="btn-icon" aria-hidden>{% include "includes/icon.html" with icon_name="arrow-right" icon_size=16 %}</span>
            Primary Hero
          </button>
          <button type="button" class="btn btn-hero btn-primary" data-hover>
            <span class="btn-icon" aria-hidden>{% include "includes/icon.html" with icon_name="arrow-right" icon_size=16 %}</span>
            Primary Hero (Hovered)
          </button>
          <button type="button" class="btn btn-hero btn-secondary">
            <span class="btn-icon" aria-hidden>{% include "includes/icon.html" with icon_name="arrow-right" icon_size=16 %}</span>
            Secondary Hero
          </button>
          <button type="button" class="btn btn-hero btn-secondary" data-hover>
            <span class="btn-icon" aria-hidden>{% include "includes/icon.html" with icon_name="arrow-right" icon_size=16 %}</span>
            Secondary Hero (Hovered)
          </button>
        </div>
        """
        )
        return template.render(Context({}))
