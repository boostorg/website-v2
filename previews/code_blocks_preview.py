from django_lookbook.preview import LookbookPreview
from django.template.loader import render_to_string


CODE_CPP = """int main()
{
    net::io_context ioc;
    tcp::resolver resolver(ioc);
    beast::tcp_stream stream(ioc);

    stream.connect(resolver.resolve("example.com", "80"));

    http::request<http::empty_body> req{http::verb::get, "/", 11};
    req.set(http::field::host, "example.com");

    http::write(stream, req);

    beast::flat_buffer buffer;
    http::response<http::string_body> res;
    http::read(stream, buffer, res);

    std::cout << res << std::endl;
}"""

CODE_HELLO = """#include <iostream>
int main()
{
    std::cout << "Hello, Boost.";
}"""

CODE_INSTALL = """brew install openssl

export OPENSSL_ROOT=$(brew --prefix openssl)

# Install bjam tool user config: https://www.bfgroup.xyz/b2/manual/release/index.html
cp ./libs/beast/tools/user-config.jam $HOME"""


class CodeBlockPreview(LookbookPreview):

    def standalone(self, **kwargs):
        """
        Standalone code block with copy button and syntax highlighting.

        Template: `v3/includes/_code_block.html`

        | Variable | Required | Description |
        |---|---|---|
        | `code` | No | Plain text string (auto-escaped, highlight.js processes it) |
        | `code_html` | No | Pre-rendered HTML with spans. Use `code` or `code_html` |
        | `variant` | No | "standalone", "white-bg", or "grey-bg". Default: "standalone" |
        | `language` | No | Language for highlight.js (e.g. "cpp", "bash"). Default: "cpp" |
        | `cpp_highlight` | No | If truthy with code_html, adds cpp-highlight class |
        """
        return render_to_string(
            "v3/includes/_code_block.html",
            {
                "code": CODE_CPP,
                "variant": "standalone",
                "language": "cpp",
            },
        )

    def white_background(self, **kwargs):
        """
        Code block with white background variant.
        """
        return render_to_string(
            "v3/includes/_code_block.html",
            {
                "code": CODE_CPP,
                "variant": "white-bg",
                "language": "cpp",
            },
        )

    def grey_background(self, **kwargs):
        """
        Code block with grey background variant.
        """
        return render_to_string(
            "v3/includes/_code_block.html",
            {
                "code": CODE_CPP,
                "variant": "grey-bg",
                "language": "cpp",
            },
        )


class CodeBlockCardPreview(LookbookPreview):

    def with_button(self, **kwargs):
        """
        Code block card with heading and a CTA button below the code.

        Template: `v3/includes/_code_block_card.html`

        | Variable | Required | Description |
        |---|---|---|
        | `card_variant` | No | "neutral" or "teal". Default: "neutral" |
        | `heading` | Yes | Card heading |
        | `description` | No | Paragraph below heading |
        | `code` | No | Plain text code string |
        | `code_html` | No | Pre-rendered HTML code |
        | `language` | No | Language for highlight.js |
        | `block_variant` | No | Code block variant. Default: "grey-bg" |
        | `button_text` | No | If set, shows a button |
        | `button_url` | No | Button href. Default: "#" |
        | `button_aria_label` | No | Accessible name for the button |
        """
        return render_to_string(
            "v3/includes/_code_block_card.html",
            {
                "heading": "Get started with our libraries",
                "code": CODE_HELLO,
                "block_variant": "grey-bg",
                "button_text": "Explore examples",
                "language": "cpp",
                "button_aria_label": "Explore examples",
            },
        )

    def neutral_with_description(self, **kwargs):
        """
        Neutral code block card with a description paragraph.
        """
        return render_to_string(
            "v3/includes/_code_block_card.html",
            {
                "card_variant": "neutral",
                "heading": "About Beast",
                "description": "Beast lets you use HTTP and WebSocket to write clients and servers that connect to networks using Boost.Asio.",
                "code": CODE_CPP,
                "block_variant": "grey-bg",
                "language": "cpp",
            },
        )

    def teal_variant(self, **kwargs):
        """
        Teal-themed code block card with bash content.
        """
        return render_to_string(
            "v3/includes/_code_block_card.html",
            {
                "card_variant": "teal",
                "heading": "Install",
                "description": "Get started with header-only libraries.",
                "code": CODE_INSTALL,
                "block_variant": "grey-bg",
                "language": "bash",
            },
        )

    def full_story_layout(self, **kwargs):
        """
        Full two-column code blocks layout with standalone blocks and cards.

        Template: `v3/includes/_code_blocks_story.html`

        | Variable | Required | Description |
        |---|---|---|
        | `code_standalone_1` | Yes | Code for first standalone block |
        | `code_standalone_2` | Yes | Code for second standalone block |
        | `code_card_1` | Yes | Code for first card |
        | `code_card_2` | Yes | Code for second card |
        | `code_card_3` | Yes | Code for third card |
        """
        return render_to_string(
            "v3/includes/_code_blocks_story.html",
            {
                "code_standalone_1": CODE_CPP,
                "code_standalone_2": CODE_CPP,
                "code_card_1": CODE_HELLO,
                "code_card_2": CODE_CPP,
                "code_card_3": CODE_INSTALL,
            },
        )
