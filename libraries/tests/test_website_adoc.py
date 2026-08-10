from pathlib import Path

import pytest

from libraries.website_adoc import (
    build_website_adoc,
    parse_website_adoc,
    website_adoc_fields,
    website_adoc_section_statuses,
)

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
    assert chart["data"] == [
        {"label": "Boost.Example", "value": 1200.0},
        {"label": "Other", "value": 800.0},
    ]

    assert parsed["freeform"]["heading"] == "Notes from the maintainer"
    assert "free-form content" in parsed["freeform"]["content"]


def test_freeform_keeps_comments_inside_code_fence():
    """`//` lines inside a `----` block are verbatim; `//` comments outside drop."""
    doc = """\
= Boost.Example — Website Content
:library-key: example

[#freeform]
== Notes from the maintainer

// this AsciiDoc comment is stripped
Example usage:

----
int main() {
    // keep this C++ comment
    return 0;
}
----
"""
    content = parse_website_adoc(doc)["freeform"]["content"]
    assert "// keep this C++ comment" in content
    assert "this AsciiDoc comment is stripped" not in content


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


def test_website_adoc_fields_keeps_raw_source_and_parsed():
    fields = website_adoc_fields(FILLED.encode())
    assert fields["website_adoc_source"] == FILLED  # raw retained as source of truth
    assert fields["website_adoc"]["library_key"] == "example"  # derived parse


def test_website_adoc_fields_none_when_no_source():
    assert website_adoc_fields(None) == {
        "website_adoc_source": None,
        "website_adoc": None,
    }
    assert website_adoc_fields("") == {
        "website_adoc_source": None,
        "website_adoc": None,
    }


def test_omitted_sections_absent():
    parsed = parse_website_adoc(
        "= Title\n:library-key: foo\n\n[#install]\n== Install\n\n"
        "[source,bash]\n----\nmake\n----\n"
    )
    assert set(parsed) == {"library_key", "install"}
    assert parsed["install"]["code"]["code"] == "make"


def test_warns_on_authored_but_empty_section():
    # [#benchmarks] anchor present but its content is all placeholders -> omitted
    # from output AND flagged, while a never-authored section is not flagged.
    parsed = parse_website_adoc(
        "= T\n:library-key: k\n\n"
        "[#install]\n== Install\n\n[source,bash]\n----\nmake\n----\n\n"
        "[#benchmarks]\n== Benchmarks\n\n[#benchmarks-x]\n=== <Chart title>\n"
    )
    assert "benchmarks" not in parsed  # authored but empty -> omitted
    assert parsed["_warnings"] == [
        {"section": "benchmarks", "reason": "empty_or_placeholder"}
    ]
    assert "install" in parsed  # unaffected


def test_section_metadata_derives_from_single_source():
    # SECTION_IDS and the admin status list both come from _SECTION_BUILDERS, so
    # adding/removing a section can't leave them out of sync.
    import libraries.website_adoc as mod

    assert mod.SECTION_IDS == {sid for _, sid, _, _ in mod._SECTION_BUILDERS}
    statuses = website_adoc_section_statuses({})
    assert [s["label"] for s in statuses] == [
        label for _, _, label, _ in mod._SECTION_BUILDERS
    ]


def test_section_statuses_covers_rendered_omitted_and_absent():
    # install rendered; benchmarks authored-but-empty; links never authored.
    parsed = parse_website_adoc(
        "= T\n:library-key: k\n\n"
        "[#install]\n== Install\n\n[source,bash]\n----\nmake\n----\n\n"
        "[#benchmarks]\n== Benchmarks\n\n[#benchmarks-x]\n=== <Chart title>\n"
    )
    by_label = {s["label"]: s for s in website_adoc_section_statuses(parsed)}
    assert len(by_label) == 7  # every known section is represented
    assert by_label["Install"]["status"] == "rendered"
    assert by_label["Benchmarks"] == {
        "label": "Benchmarks",
        "status": "omitted",
        "reason": "empty_or_placeholder",
    }
    assert by_label["Links"]["status"] == "absent"  # missing -> visible, neutral


def test_no_warnings_key_when_all_authored_sections_render():
    parsed = parse_website_adoc(
        "= T\n:library-key: k\n\n[#install]\n== Install\n\n"
        "[source,bash]\n----\nmake\n----\n"
    )
    assert "_warnings" not in parsed


def test_warns_on_parse_error(monkeypatch):
    import libraries.website_adoc as mod

    def boom(_lines):
        raise ValueError("broken")

    monkeypatch.setattr(
        mod,
        "_SECTION_BUILDERS",
        tuple(
            (out, sid, label, boom if sid == "benchmarks" else fn)
            for out, sid, label, fn in mod._SECTION_BUILDERS
        ),
    )
    parsed = parse_website_adoc(FILLED)
    assert {"section": "benchmarks", "reason": "parse_error"} in parsed["_warnings"]


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
            (out, sid, label, boom if sid == "benchmarks" else fn)
            for out, sid, label, fn in mod._SECTION_BUILDERS
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
