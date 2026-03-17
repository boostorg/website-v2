from django_lookbook.preview import LookbookPreview
from django.template import Context, Template
from django.template.loader import render_to_string


class ContentDetailCardPreview(LookbookPreview):

    def with_icon_and_link(self, **kwargs):
        """
        Content detail card with an icon and a linked title.

        Template: `v3/includes/_content_detail_card_item.html`

        | Variable | Required | Description |
        |---|---|---|
        | `title` | Yes | Card heading |
        | `description` | Yes | Card body text |
        | `icon_name` | No | Icon name (e.g. "bullseye-arrow"). If omitted, no icon is rendered |
        | `title_url` | No | If set, title becomes a link |
        | `cta_label` | No | CTA link text (used with `cta_href`) |
        | `cta_href` | No | CTA link URL |
        """
        template = Template(
            '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px;">'
            "<div>"
            '{% include "v3/includes/_content_detail_card_item.html" with title="Get help" description="Tap into quick answers, networking, and chat with 24,000+ members." icon_name="get-help" title_url="/help" %}'
            "</div>"
            "<div>"
            '{% include "v3/includes/_content_detail_card_item.html" with title="Another card" description="With a different icon. Icon is optional and dynamic." icon_name="device-tv" %}'
            "</div>"
            "</div>"
        )
        return template.render(Context({}))

    def with_cta(self, **kwargs):
        """
        Content detail card with icon and a CTA link below the description.
        """
        return render_to_string(
            "v3/includes/_content_detail_card_item.html",
            {
                "title": "Get help",
                "description": "Tap into quick answers, networking, and chat with 24,000+ members.",
                "icon_name": "info-box",
                "cta_label": "Start here",
                "cta_href": "#",
            },
        )

    def without_icon(self, **kwargs):
        """
        Content detail card without an icon — renders without the `--has-icon` modifier.
        """
        return render_to_string(
            "v3/includes/_content_detail_card_item.html",
            {
                "title": "Plain card",
                "description": "This variant has no icon. Useful for simpler layouts.",
            },
        )


class ContentEventCardPreview(LookbookPreview):

    def as_list_items(self, **kwargs):
        """
        Content event cards rendered as a list (no card wrapper).

        Template: `v3/includes/_content_event_card_item.html`

        | Variable | Required | Description |
        |---|---|---|
        | `title` | Yes | Event title |
        | `description` | Yes | Event description |
        | `date` | Yes | Human-readable date |
        | `datetime` | No | Value for `<time datetime>` |
        | `card_url` | No | If set, card is wrapped in a link |
        | `card_aria_label` | No | Aria-label for the link |
        | `event_card_wrapper` | No | If True, wraps in `<div class="event-card">` |
        | `contained` | No | If True, adds contained variant styling |
        """
        template = Template(
            """
        <section class="post-cards post-cards--content post-cards--neutral post-cards--content-list">
          <h2 class="post-cards__heading">
            <a href="#" class="post-cards__heading-link">Releases</a>
          </h2>
          <ul class="post-cards__list">
            <li class="post-cards__item">
              {% include "v3/includes/_content_event_card_item.html" with title="Boost 1.90.0 closed for major changes" description="Release closed for major code changes. Still open for serious problem fixes and docs changes without release manager review." date="29/10/25" datetime="29/10/25" card_url="#event-0" card_aria_label="Boost 1.90.0 closed for major changes" event_card_wrapper=False %}
            </li>
            <li class="post-cards__item">
              {% include "v3/includes/_content_event_card_item.html" with title="C++ Now 2025 call for submissions" description="C++ Now conference is accepting talk proposals until March 15. Topics include modern C++, Boost libraries, and tooling." date="12/02/25" datetime="12/02/25" card_url="#event-1" card_aria_label="C++ Now 2025 call for submissions" event_card_wrapper=False %}
            </li>
            <li class="post-cards__item">
              {% include "v3/includes/_content_event_card_item.html" with title="Boost 1.89.0 released" description="Boost 1.89.0 is available with updates to Asio, Beast, and several other libraries. See release notes for details." date="15/01/25" datetime="15/01/25" card_url="#event-2" card_aria_label="Boost 1.89.0 released" event_card_wrapper=False %}
            </li>
          </ul>
          <div class="card__cta_section">{% include "v3/includes/_button.html" with label="View all" url="#" %}</div>
        </section>
        """
        )
        return template.render(Context({}))

    def as_cards(self, **kwargs):
        """
        Content event cards with the card wrapper enabled (clickable cards).
        """
        template = Template(
            """
        <section class="post-cards post-cards--content post-cards--neutral post-cards--content-card">
          <h2 class="post-cards__heading">
            <a href="#" class="post-cards__heading-link">Releases</a>
          </h2>
          <ul class="post-cards__list">
            <li class="post-cards__item">
              {% include "v3/includes/_content_event_card_item.html" with title="Boost 1.90.0 closed for major changes" description="Release closed for major code changes. Still open for serious problem fixes and docs changes without release manager review." date="29/10/25" datetime="29/10/25" card_url="#event-0" card_aria_label="Boost 1.90.0 closed for major changes" event_card_wrapper=True %}
            </li>
            <li class="post-cards__item">
              {% include "v3/includes/_content_event_card_item.html" with title="C++ Now 2025 call for submissions" description="C++ Now conference is accepting talk proposals until March 15. Topics include modern C++, Boost libraries, and tooling." date="12/02/25" datetime="12/02/25" card_url="#event-1" card_aria_label="C++ Now 2025 call for submissions" event_card_wrapper=True %}
            </li>
            <li class="post-cards__item">
              {% include "v3/includes/_content_event_card_item.html" with title="Boost 1.89.0 released" description="Boost 1.89.0 is available with updates to Asio, Beast, and several other libraries. See release notes for details." date="15/01/25" datetime="15/01/25" card_url="#event-2" card_aria_label="Boost 1.89.0 released" event_card_wrapper=True %}
            </li>
          </ul>
          <div class="card__cta_section">{% include "v3/includes/_button.html" with label="View all" url="#" %}</div>
        </section>
        """
        )
        return template.render(Context({}))


class EventCardsPreview(LookbookPreview):

    def all_variants_gallery(self, **kwargs):
        """
        Event cards gallery showing all theme variants (white, grey, yellow, green, teal)
        plus clickable card variant.

        Template: `v3/includes/_event_cards.html`

        When called without `event_list` and `variant`, the template renders
        the full gallery of all variants with sample content.

        | Variable | Required | Description |
        |---|---|---|
        | `event_list` | No | List of event dicts (title, description, date, datetime) |
        | `variant` | No | "white", "grey", "yellow", "green", or "teal" |
        | `section_heading` | No | Default: "Upcoming Events" |
        | `primary_btn_text` | No | Primary button text |
        | `primary_btn_url` | No | Primary button URL |
        | `secondary_btn_text` | No | Secondary button text |
        | `secondary_btn_url` | No | Secondary button URL |
        """
        return render_to_string("v3/includes/_event_cards.html")


class WhyBoostCardsPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Why Boost section — a grid of icon + title + description cards.

        Uses the same inline markup as the demo page with all 11 cards.

        Template: `v3/includes/_content_detail_card_item.html` (wrapped in why-boost-cards section)

        | Variable | Required | Description |
        |---|---|---|
        | `title` | Yes | Card heading |
        | `description` | Yes | Card body text |
        | `icon_name` | No | Icon name |
        """
        template = Template(
            """
        <section class="why-boost-cards" aria-labelledby="why-boost-heading">
          <h2 id="why-boost-heading" class="why-boost-cards__heading">Why Boost?</h2>
          <div class="why-boost-cards__grid">
            {% include "v3/includes/_content_detail_card_item.html" with title="Get help" description="Tap into quick answers, networking, and chat with 24,000+ members." icon_name="bullseye-arrow" %}
            {% include "v3/includes/_content_detail_card_item.html" with title="Documentation" description="Browse library docs, examples, and release notes in one place." icon_name="link" %}
            {% include "v3/includes/_content_detail_card_item.html" with title="Community" description="Mailing lists, GitHub, and community guidelines for contributors." icon_name="human" %}
            {% include "v3/includes/_content_detail_card_item.html" with title="Releases" description="Latest releases, download links, and release notes." icon_name="info-box" %}
            {% include "v3/includes/_content_detail_card_item.html" with title="Learn" description="Access documentation, books, and courses to level up your C++." icon_name="bullseye-arrow" %}
            {% include "v3/includes/_content_detail_card_item.html" with title="Contribute" description="Report issues, submit patches, and join the community." icon_name="bullseye-arrow" %}
            {% include "v3/includes/_content_detail_card_item.html" with title="Stay updated" description="Releases, news, and announcements from the Boost community." icon_name="bullseye-arrow" %}
            {% include "v3/includes/_content_detail_card_item.html" with title="Libraries" description="Portable, peer-reviewed libraries for a wide range of use cases." icon_name="bullseye-arrow" %}
            {% include "v3/includes/_content_detail_card_item.html" with title="Standards" description="Many Boost libraries have been adopted into the C++ standard." icon_name="bullseye-arrow" %}
            {% include "v3/includes/_content_detail_card_item.html" with title="Quality" description="Peer-reviewed code and documentation maintained by the community." icon_name="bullseye-arrow" %}
            {% include "v3/includes/_content_detail_card_item.html" with title="Cross-platform" description="Libraries designed to work across compilers and platforms." icon_name="bullseye-arrow" %}
          </div>
        </section>
        """
        )
        return template.render(Context({}))


class CategoryTagsPreview(LookbookPreview):

    def all_variants(self, **kwargs):
        """
        Category tags — all size and colour variants with default and hover states.

        Template: `v3/includes/_category_cards.html`

        When called without `category_tags`, shows the full variant gallery.

        | Variable | Required | Description |
        |---|---|---|
        | `category_tags` | No | List of dicts (tag_label, url, variant, size, aria_label) |
        | `section_heading` | No | Default: "Category tags" |
        | `show_version_tags` | No | If truthy, shows version tags block |
        """
        return render_to_string(
            "v3/includes/_category_cards.html",
            {
                "show_version_tags": True,
            },
        )
