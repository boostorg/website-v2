from django_lookbook.preview import LookbookPreview
from django.template import Context, Template


class AvatarsPreview(LookbookPreview):

    def variants(self, **kwargs):
        """
        Avatar component — all visual variants.

        Template: `v3/includes/_avatar_v3.html`

        | Variable | Required | Description |
        |---|---|---|
        | `src` | No | Image URL. If set, renders an image avatar |
        | `name` | No | Person's name. If set (and no `src`), renders initials |
        | `variant` | No | Color variant for initials: `yellow`, `green`, `teal`. Default: `yellow` |
        | `size` | No | Size: `sm`, `md`, `lg`, `xl`. Default: `md` |

        Priority: `src` > `name` (initials) > placeholder (`?`).
        """
        template = Template(
            """
        {% load avatar_tags %}
        <div style="display: flex; gap: 24px; align-items: center; flex-wrap: wrap;">
          <div style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
            {% include "v3/includes/_avatar_v3.html" with src="https://ui-avatars.com/api/?name=Jane+Doe&size=80" size="md" %}
            <span style="font-size: 12px;">Image</span>
          </div>
          <div style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
            {% include "v3/includes/_avatar_v3.html" with name="Jane Doe" variant="yellow" %}
            <span style="font-size: 12px;">Yellow</span>
          </div>
          <div style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
            {% include "v3/includes/_avatar_v3.html" with name="Jane Doe" variant="green" %}
            <span style="font-size: 12px;">Green</span>
          </div>
          <div style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
            {% include "v3/includes/_avatar_v3.html" with name="Jane Doe" variant="teal" %}
            <span style="font-size: 12px;">Teal</span>
          </div>
          <div style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
            {% include "v3/includes/_avatar_v3.html" %}
            <span style="font-size: 12px;">Placeholder</span>
          </div>
        </div>
        """
        )
        return template.render(Context({}))

    def sizes(self, **kwargs):
        """
        Avatar component at each available size: `sm` (32px), `md` (40px), `lg` (44px), `xl` (48px).
        """
        template = Template(
            """
        {% load avatar_tags %}
        <div style="display: flex; gap: 24px; align-items: end; flex-wrap: wrap;">
          <div style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
            {% include "v3/includes/_avatar_v3.html" with name="JD" variant="yellow" size="sm" %}
            <span style="font-size: 12px;">sm</span>
          </div>
          <div style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
            {% include "v3/includes/_avatar_v3.html" with name="JD" variant="yellow" size="md" %}
            <span style="font-size: 12px;">md</span>
          </div>
          <div style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
            {% include "v3/includes/_avatar_v3.html" with name="JD" variant="yellow" size="lg" %}
            <span style="font-size: 12px;">lg</span>
          </div>
          <div style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
            {% include "v3/includes/_avatar_v3.html" with name="JD" variant="yellow" size="xl" %}
            <span style="font-size: 12px;">xl</span>
          </div>
        </div>
        """
        )
        return template.render(Context({}))
