from urllib.parse import urlparse, urlunparse

from django import template
from django.template.defaultfilters import stringfilter
import re

register = template.Library()


@register.filter(is_safe=True)
@stringfilter
def truncate_middle(value, arg):
    try:
        ln = int(arg)
    except ValueError:
        return value
    if len(value) <= ln:
        return value
    else:
        return f"{value[:ln//2]}....{value[-((ln+1)//2):]}"


@register.filter(is_safe=True)
@stringfilter
def multi_truncate_middle(value, arg):
    def replace_match(match):
        word_or_link = match.group(0)

        link_inner_match = re.search(r"<a\b[^>]*>(.*?)<\/a>", word_or_link)

        if link_inner_match:
            word = re.sub(r"https?://", "", link_inner_match.group(1))

        else:
            word = word_or_link

        if link_inner_match:
            if len(word) > ln + 10:
                start = word[: ((ln + 10) // 2)]
                end = word[-(((ln + 10) + 1) // 2) :]
                truncated_word = f"{start}....{end}"
                return re.sub(
                    r"(<a\b[^>]*>)(.*?)(<\/a>)",
                    r"\1" + truncated_word + r"\3",
                    word_or_link,
                )
        elif len(word) > ln:
            start = word[: (ln // 2)]
            end = word[-((ln + 1) // 2) :]
            truncated_word = f"{start}....{end}"
            return truncated_word
        return word_or_link

    pattern = re.compile(
        r"\b(\w{" + str(arg) + r",})\b|<a\b[^>]*>((.|\n|\r|(\n\r))*?)<\/a>"
    )

    try:
        ln = int(arg)
    except ValueError:
        return value
    if len(value) <= ln:
        return value
    else:
        result = pattern.sub(replace_match, value)
        return result


@register.filter(is_safe=True)
@stringfilter
def url_target_blank(value, arg):
    """
    Use after urlize to add target="_blank" and add classes.
    """
    return value.replace("<a ", f'<a target="_blank" class="{arg}" ')


@register.filter
def strip_query_string(url):
    """Remove query string from URL while preserving the path and other components."""
    if not url:
        return url
    parsed = urlparse(url)
    clean = parsed._replace(query="", fragment="")
    return urlunparse(clean)


# ========== V3 Code block demo (plain text for highlight.js) ==========

CODE_DEMO_BEAST = """int main()
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

CODE_DEMO_HELLO = """#include <iostream>
int main()
{
    std::cout << "Hello, Boost.";
}"""

CODE_DEMO_INSTALL = """brew install openssl

export OPENSSL_ROOT=$(brew --prefix openssl)

# Install bjam tool user config: https://www.bfgroup.xyz/b2/manual/release/index.html
cp ./libs/beast/tools/user-config.jam $HOME"""


@register.simple_tag
def code_demo_beast():
    """Return Beast C++ demo code (plain text with newlines for highlight.js)."""
    return CODE_DEMO_BEAST


@register.simple_tag
def code_demo_hello():
    """Return Hello Boost C++ demo code (plain text with newlines for highlight.js)."""
    return CODE_DEMO_HELLO


@register.simple_tag
def code_demo_install():
    """Return Install bash demo code (plain text with newlines for highlight.js)."""
    return CODE_DEMO_INSTALL
