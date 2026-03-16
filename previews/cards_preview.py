from django_lookbook.preview import LookbookPreview
from django.template import Context, Template
from django.template.loader import render_to_string


class BasicCardPreview(LookbookPreview):

    def with_two_buttons(self, **kwargs):
        """
        Basic card with both primary and secondary action buttons.

        Template: `v3/includes/_basic_card.html`

        | Variable | Required | Description |
        |---|---|---|
        | `title` | Yes | Bold heading at the top |
        | `text` | Yes | Body text |
        | `primary_button_url` | No | Primary CTA destination |
        | `primary_button_label` | No | Primary CTA text |
        | `secondary_button_url` | No | Secondary CTA destination |
        | `secondary_button_label` | No | Secondary CTA text |
        """
        return render_to_string(
            "v3/includes/_basic_card.html",
            {
                "title": "Found a Bug?",
                "text": "We rely on developers like you to keep Boost solid. Here's how to report issues that help the whole community.",
                "primary_button_url": "#",
                "primary_button_label": "Primary Button",
                "secondary_button_url": "#",
                "secondary_button_label": "Secondary Button",
            },
        )

    def with_one_button(self, **kwargs):
        """
        Basic card with only a primary button.
        """
        return render_to_string(
            "v3/includes/_basic_card.html",
            {
                "title": "Found a Bug?",
                "text": "We rely on developers like you to keep Boost solid. Here's how to report issues that help the whole community.",
                "primary_button_url": "#",
                "primary_button_label": "Primary Button",
            },
        )


class VerticalCardPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Vertical layout card with an image, text, and a button.

        Template: `v3/includes/_vertical_card.html`

        | Variable | Required | Description |
        |---|---|---|
        | `title` | Yes | Bold heading |
        | `text` | No | Body text |
        | `image_url` | No | Image URL |
        | `primary_button_url` | No | Primary CTA destination |
        | `primary_button_label` | No | Primary CTA text |
        | `primary_style` | No | Button style override |
        | `secondary_button_url` | No | Secondary CTA destination |
        | `secondary_button_label` | No | Secondary CTA text |
        """
        return render_to_string(
            "v3/includes/_vertical_card.html",
            {
                "title": "Found a Bug?",
                "text": "We rely on developers like you to keep Boost solid.",
                "primary_button_url": "#",
                "primary_button_label": "Primary Button",
                "image_url": "/static/img/v3/demo_page/Calendar.png",
            },
        )


class SearchCardPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Search prompt card with a text input and popular term tags.

        Template: `v3/includes/_search_card.html`

        | Variable | Required | Description |
        |---|---|---|
        | `heading` | Yes | Card heading text |
        | `placeholder` | No | Input placeholder. Default: "Search libraries, docs, examples" |
        | `action_url` | Yes | Form action URL |
        | `input_name` | No | Input name attribute. Default: "q" |
        | `popular_terms` | No | List of objects with `.label` |
        | `popular_label` | No | Label above tags. Default: "Popular terms:" |
        """
        return render_to_string(
            "v3/includes/_search_card.html",
            {
                "heading": "What are you trying to find?",
                "action_url": "#",
                "popular_terms": [
                    {"label": "Networking"},
                    {"label": "Math"},
                    {"label": "Data processing"},
                    {"label": "Concurrency"},
                    {"label": "File systems"},
                    {"label": "Testing"},
                ],
            },
        )


class CreateAccountCardPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Create Account Card with rich text body and preview image.

        Template: `v3/includes/_create_account_card.html`

        | Variable | Required | Description |
        |---|---|---|
        | `heading` | No | Card title text |
        | `body_html` | No | Rich text HTML content |
        | `preview_image_url` | No | Preview image URL |
        | `preview_image_alt` | No | Preview image alt text |
        | `cta_url` | No | CTA target URL |
        | `cta_label` | No | CTA text |
        """
        return render_to_string(
            "v3/includes/_create_account_card.html",
            {
                "heading": "Contribute to earn badges, track your progress and grow your impact",
                "preview_image_url": "/static/img/checker.png",
                "cta_url": "#",
                "cta_label": "Start contributing",
            },
        )


class LearnCardPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Learn card — introduces a topic with links and a large image.

        Template: `v3/includes/_learn_card.html`

        | Variable | Required | Description |
        |---|---|---|
        | `title` | Yes | Card title |
        | `text` | Yes | Short description |
        | `links` | Yes | List of dicts with `label` and `url` |
        | `label` | Yes | Hero button text |
        | `url` | Yes | Hero button URL |
        | `image_src` | Yes | Image URL |
        """
        return render_to_string(
            "v3/includes/_learn_card.html",
            {
                "title": "I want to learn:",
                "text": "How to install Boost, use its libraries, build projects, and get help when you need it.",
                "links": [
                    {"label": "Explore common use cases", "url": "#"},
                    {"label": "Build with CMake", "url": "#"},
                    {"label": "Visit the FAQ", "url": "#"},
                ],
                "url": "#",
                "label": "Learn more about Boost",
                "image_src": "/static/img/v3/examples/Learn Card Image.png",
            },
        )


class TestimonialCardPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Testimonial card — a carousel of user quotes with author info.

        Template: `v3/includes/_testimonial_card.html`

        | Variable | Required | Description |
        |---|---|---|
        | `heading` | Yes | Card title |
        | `testimonials` | Yes | List of testimonial objects, each with `quote` and `author` (name, avatar_url, role, role_badge) |
        """
        return render_to_string(
            "v3/includes/_testimonial_card.html",
            {
                "heading": "What Engineers are saying",
                "testimonials": [
                    {
                        "quote": "I use Boost daily. I absolutely love it. It's wonderful. I could not do my job w/o it. Much of it is in the new C++11 standard too.",
                        "author": {
                            "name": "Name Surname",
                            "avatar_url": "/static/img/v3/demo_page/Avatar.png",
                            "role": "Contributor",
                            "role_badge": "/static/img/v3/demo_page/Badge.svg",
                        },
                    },
                    {
                        "quote": "I use Boost daily. I absolutely love it. It's wonderful. I could not do my job w/o it. Much of it is in the new C++11 standard too.",
                        "author": {
                            "name": "Name Surname",
                            "avatar_url": "/static/img/v3/demo_page/Avatar.png",
                            "role": "Contributor",
                            "role_badge": "/static/img/v3/demo_page/Badge.svg",
                        },
                    },
                    {
                        "quote": "I use Boost daily. I absolutely love it. It's wonderful. I could not do my job w/o it. Much of it is in the new C++11 standard too.",
                        "author": {
                            "name": "Name Surname",
                            "avatar_url": "/static/img/v3/demo_page/Avatar.png",
                            "role": "Contributor",
                            "role_badge": "/static/img/v3/demo_page/Badge.svg",
                        },
                    },
                    {
                        "quote": "I use Boost daily. I absolutely love it. It's wonderful. I could not do my job w/o it. Much of it is in the new C++11 standard too.",
                        "author": {
                            "name": "Name Surname",
                            "avatar_url": "/static/img/v3/demo_page/Avatar.png",
                            "role": "Contributor",
                            "role_badge": "/static/img/v3/demo_page/Badge.svg",
                        },
                    },
                ],
            },
        )


class PostCardPreview(LookbookPreview):

    def single_post_card(self, **kwargs):
        """
        A single post card with title, meta info, and author.

        Template: `v3/includes/_post_card_v3.html`

        | Variable | Required | Description |
        |---|---|---|
        | `post_title` | No | Post title |
        | `post_url` | No | Link URL |
        | `post_date` | No | Date string |
        | `post_category` | No | Category label |
        | `post_tag` | No | Tag (shown as #tag) |
        | `author_name` | No | Author display name |
        | `author_role` | No | Author role |
        | `author_avatar_url` | No | Author avatar image URL |
        | `author_show_badge` | No | If truthy, shows a badge icon |
        """
        template = Template(
            '{% with post_title="A talk by Richard Thomson at the Utah C++ Programmers Group" '
            'post_url="#" post_date="03/03/2025" post_category="Issues" post_tag="beast" '
            'author_name="Richard Thomson" author_role="Contributor" author_show_badge=True '
            'author_avatar_url="https://ui-avatars.com/api/?name=Richard+Thomson&size=48" %}'
            '{% include "v3/includes/_post_card_v3.html" %}'
            "{% endwith %}"
        )
        return template.render(Context({}))

    def post_cards_list(self, **kwargs):
        """
        A list of post cards inside the standard post-cards section wrapper.
        """
        template = Template(
            """
        <section class="post-cards post-cards--default post-cards--neutral post-cards--vertical">
          <h2 class="post-cards__heading">
            <a href="#" class="post-cards__heading-link">Posts from the Boost community</a>
          </h2>
          <ul class="post-cards__list">
            <li class="post-cards__item">
              {% with post_title="A talk by Richard Thomson at the Utah C++ Programmers Group" post_url="#" post_date="03/03/2025" post_category="Issues" post_tag="beast" author_name="Richard Thomson" author_role="Contributor" author_show_badge=True author_avatar_url="https://ui-avatars.com/api/?name=Richard+Thomson&size=48" %}
                {% include "v3/includes/_post_card_v3.html" %}
              {% endwith %}
            </li>
            <li class="post-cards__item">
              {% with post_title="A talk by Richard Thomson at the Utah C++ Programmers Group" post_url="#" post_date="03/03/2025" post_category="Issues" post_tag="beast" author_name="Peter Dimov" author_role="Maintainer" author_show_badge=True author_avatar_url="https://ui-avatars.com/api/?name=Peter+Dimov&size=48" %}
                {% include "v3/includes/_post_card_v3.html" %}
              {% endwith %}
            </li>
            <li class="post-cards__item">
              {% with post_title="Boost.Bind and modern C++: a quick overview" post_url="#" post_date="15/02/2025" post_category="Releases" post_tag="bind" author_name="Alex Morgan" author_role="Contributor" author_show_badge=False author_avatar_url="https://ui-avatars.com/api/?name=Alex+Morgan&size=48" %}
                {% include "v3/includes/_post_card_v3.html" %}
              {% endwith %}
            </li>
          </ul>
          <div class="card__cta_section">
            {% include "v3/includes/_button.html" with label="View all posts" url="#" %}
          </div>
        </section>
        """
        )
        return template.render(Context({}))


class MailingListCardPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Mailing list sign-up card with email input and subscribe button.

        Template: `v3/includes/_mailing_list_card.html`

        Self-contained component with no required variables.
        """
        return render_to_string("v3/includes/_mailing_list_card.html")


class ThreadArchiveCardPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Thread archive card linking to the Boost mailing list archive.

        Template: `v3/includes/_thread_archive_card.html`

        Self-contained component with no required variables.
        """
        return render_to_string("v3/includes/_thread_archive_card.html")


class LibraryIntroCardPreview(LookbookPreview):

    def default(self, **kwargs):
        """
        Library introduction card with authors and CTA.

        Template: `v3/includes/_library_intro_card.html`

        | Variable | Required | Description |
        |---|---|---|
        | `library_name` | Yes | Library display name |
        | `description` | Yes | Short library description |
        | `authors` | No | List of author objects (name, role, avatar_url, badge, badge_url, bio) |
        | `cta_label` | No | Button text |
        | `cta_url` | No | Button link URL |
        """
        return render_to_string(
            "v3/includes/_library_intro_card.html",
            {
                "library_name": "Beast",
                "description": "HTTP and WebSocket built on Boost.Asio — portable, header-only C++ with a consistent asynchronous model.",
                "authors": [
                    {
                        "name": "Vinnie Falco",
                        "role": "Maintainer",
                        "avatar_url": "https://ui-avatars.com/api/?name=Vinnie+Falco&size=48",
                    },
                    {
                        "name": "Richard Thomson",
                        "role": "Contributor",
                        "avatar_url": "https://ui-avatars.com/api/?name=Richard+Thomson&size=48",
                    },
                ],
                "cta_url": "#",
                "cta_label": "Use Beast",
            },
        )
