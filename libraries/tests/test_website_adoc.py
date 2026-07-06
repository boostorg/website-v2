from pathlib import Path

import pytest

from libraries.website_adoc import build_website_adoc, parse_website_adoc

FILLED = """\
= Boost.Example — Website Content
:library-key: example

[#about]
== About
Boost.Example makes X fast and safe.

[source,cpp]
----
#include <boost/example.hpp>
int main() { return 0; }
----

[#playground]
== Playground

[source,cpp]
----
#include <boost/example.hpp>
int main() { boost::example::run(); }
----

[#designed-for]
== Designed for

=== High throughput
Handles millions of ops per second.

=== Zero allocations
No heap use on the hot path.

[#links]
== Links
:common-use-case-url: https://www.boost.org/doc/libs/1_90_0/libs/example/use.html
:code-example-url: https://www.boost.org/doc/libs/1_90_0/libs/example/ex.html

[#install]
== Install

Header-only — just add Boost to your include path.

[source,bash]
----
./b2 --with-example install
----

[#benchmarks]
== Benchmarks

[#benchmarks-throughput]
=== Throughput
:unit: req/s
:caption: higher is better

[cols="2,1",options="header"]
|===
| Label | Value
| Boost.Example | 1,200
| Other | 800
|===

[#freeform]
== Notes from the maintainer

Some free-form content with a link.
"""


def test_parse_returns_none_for_empty():
    assert parse_website_adoc(None) is None
    assert parse_website_adoc("") is None
    assert parse_website_adoc(b"   ") is None


def test_parse_filled_document():
    parsed = parse_website_adoc(FILLED)

    assert parsed["library_key"] == "example"

    assert "fast and safe" in parsed["about"]["blurb"]
    assert "#include <boost/example.hpp>" in parsed["about"]["code"]["code"]
    assert parsed["about"]["code"]["language"] == "cpp"

    assert "boost::example::run()" in parsed["playground"]["code"]

    assert parsed["designed_for"] == [
        {
            "heading": "High throughput",
            "description": "Handles millions of ops per second.",
        },
        {"heading": "Zero allocations", "description": "No heap use on the hot path."},
    ]

    assert parsed["links"] == {
        "common_use_case_url": "https://www.boost.org/doc/libs/1_90_0/libs/example/use.html",
        "code_example_url": "https://www.boost.org/doc/libs/1_90_0/libs/example/ex.html",
    }

    assert (
        parsed["install"]["blurb"]
        == "Header-only — just add Boost to your include path."
    )
    assert parsed["install"]["code"]["language"] == "bash"
    assert "./b2 --with-example install" in parsed["install"]["code"]["code"]

    [chart] = parsed["benchmarks"]
    assert chart["id"] == "benchmarks-throughput"
    assert chart["title"] == "Throughput"
    assert chart["unit"] == "req/s"
    assert chart["caption"] == "higher is better"
    assert chart["data"] == [
        {"label": "Boost.Example", "value": 1200.0},
        {"label": "Other", "value": 800.0},
    ]

    assert parsed["freeform"]["heading"] == "Notes from the maintainer"
    assert "free-form content" in parsed["freeform"]["content"]


def test_unfilled_template_drops_placeholder_sections():
    """The raw template (angle-bracket placeholders) yields no placeholder data."""
    template = (
        Path(__file__).resolve().parent.parent / "website_adoc_template.adoc"
    ).read_text()
    parsed = parse_website_adoc(template)

    # Placeholder values are never surfaced.
    assert "library_key" not in parsed
    assert "designed_for" not in parsed
    assert "links" not in parsed
    assert "benchmarks" not in parsed
    assert "freeform" not in parsed
    assert parsed.get("about", {}).get("blurb") is None
    assert parsed.get("install", {}).get("blurb") is None


def test_omitted_sections_absent():
    parsed = parse_website_adoc(
        "= Title\n:library-key: foo\n\n[#install]\n== Install\n\n"
        "[source,bash]\n----\nmake\n----\n"
    )
    assert set(parsed) == {"library_key", "install"}
    assert parsed["install"]["code"]["code"] == "make"


def test_broken_section_dropped_others_kept(monkeypatch):
    """A section parser that raises drops only that section, not the document."""
    import libraries.website_adoc as mod

    def boom(_lines):
        raise ValueError("broken benchmark table")

    # Rebuild the builder table with benchmarks forced to raise.
    monkeypatch.setattr(
        mod,
        "_SECTION_BUILDERS",
        tuple(
            (out, sid, boom if sid == "benchmarks" else fn)
            for out, sid, fn in mod._SECTION_BUILDERS
        ),
    )

    parsed = parse_website_adoc(FILLED)
    assert "benchmarks" not in parsed  # the broken section is gone
    assert parsed["about"]["blurb"]  # the rest survived
    assert parsed["install"]["code"]
    assert parsed["library_key"] == "example"


def test_freeform_render_failure_keeps_other_sections(monkeypatch):
    """If the asciidoctor gem errors on freeform, only freeform is dropped."""
    import libraries.website_adoc as mod

    def boom(_content):
        raise RuntimeError("asciidoctor failed")

    monkeypatch.setattr(mod, "convert_adoc_to_html", boom)

    parsed = build_website_adoc(FILLED)
    assert "freeform" not in parsed
    assert "about" in parsed and "install" in parsed


@pytest.mark.asciidoctor
def test_build_renders_freeform_html():
    parsed = build_website_adoc(FILLED)
    assert "<" in parsed["freeform"]["html"]
    assert "free-form content" in parsed["freeform"]["html"]
