"""Parse a library's optional ``meta/website.adoc`` into structured data.

The file is a maintainer-authored AsciiDoc file whose contract is defined in
``libraries/website_adoc_template.adoc`` — the website keys off stable section
IDs (``[#about]`` …) and attribute names (``:library-key:`` …), not the prose.
Every section is optional; an absent or empty file parses to ``None``.

``parse_website_adoc`` is pure (no external process). ``build_website_adoc``
additionally renders the free-form section to HTML via the asciidoctor gem and
is what the ingestion pipeline stores on ``LibraryVersion.website_adoc``.
"""

import re

import structlog

from core.asciidoc import convert_adoc_to_html

logger = structlog.get_logger()

# Top-level section IDs that anchor a block. Nested benchmark anchors
# (``[#benchmarks-*]``) are parsed within the benchmarks section, not here.
SECTION_IDS = frozenset(
    [
        "about",
        "playground",
        "designed-for",
        "links",
        "install",
        "benchmarks",
        "freeform",
    ]
)

_ANCHOR_RE = re.compile(r"^\[#([a-z0-9-]+)\]\s*$")
_ATTR_RE = re.compile(r"^:([a-z0-9-]+):\s*(.*)$")
_SOURCE_RE = re.compile(r"^\[source(?:%[^\],]*)?(?:,\s*([a-z0-9+#-]+))?.*\]\s*$")
_HEADING_RE = re.compile(r"^=+\s+(.*\S)\s*$")


def _is_placeholder(value):
    """A copied-but-unfilled template value, e.g. ``<your-key>`` or empty."""
    v = (value or "").strip()
    return not v or (v.startswith("<") and v.endswith(">"))


def _clean(value):
    return None if _is_placeholder(value) else value.strip()


def _first_source_block(lines):
    """Return ``{"language", "code"}`` for the first ``[source]`` block, or None."""
    language = None
    code = []
    in_code = False
    for line in lines:
        stripped = line.strip()
        if not in_code:
            match = _SOURCE_RE.match(stripped)
            if match:
                language = match.group(1)
                continue
            if stripped == "----":
                in_code = True
            continue
        if stripped == "----":
            code_text = "\n".join(code).strip("\n")
            return {"language": language, "code": code_text} if code_text else None
        code.append(line)
    return None


def _blurb(lines):
    """Leading prose of a section (before its first source/listing block)."""
    text = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[source") or stripped == "----":
            break
        if _HEADING_RE.match(stripped) or stripped.startswith("//") or not stripped:
            continue
        text.append(stripped)
    joined = " ".join(text).strip()
    return joined or None


def _subsections(lines):
    """Parse ``=== heading`` + description pairs (used by ``[#designed-for]``)."""
    items = []
    current = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        heading = re.match(r"^===\s+(.*\S)\s*$", stripped)
        if heading:
            if current and current["description"]:
                items.append(current)
            current = {"heading": heading.group(1).strip(), "description": ""}
        elif current is not None and stripped:
            current["description"] = (current["description"] + " " + stripped).strip()
    if current and current["description"]:
        items.append(current)
    return [
        item
        for item in items
        if not _is_placeholder(item["heading"])
        and not _is_placeholder(item["description"])
    ]


def _table_rows(lines):
    """Parse a two-column ``Label | Value`` table body, skipping the header."""
    rows = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|==="):
            if in_table:
                break
            in_table = True
            continue
        if not in_table or not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.split("|")[1:]]
        if len(cells) < 2:
            continue
        rows.append(cells[:2])
    data = []
    for label, value in rows[1:]:  # drop the header row
        if _is_placeholder(label):
            continue
        try:
            data.append({"label": label, "value": float(value.replace(",", ""))})
        except ValueError:
            continue
    return data


def _benchmarks(lines):
    """Split the benchmarks body on ``[#benchmarks-*]`` anchors into charts."""
    charts = []
    current = None
    for line in lines:
        stripped = line.strip()
        anchor = _ANCHOR_RE.match(stripped)
        if anchor and anchor.group(1).startswith("benchmarks-"):
            if current:
                charts.append(current)
            current = {"id": anchor.group(1), "lines": []}
            continue
        if current is not None:
            current["lines"].append(line)
    if current:
        charts.append(current)

    result = []
    for chart in charts:
        body = chart["lines"]
        title = next(
            (m.group(1) for m in map(_HEADING_RE.match, map(str.strip, body)) if m),
            None,
        )
        attrs = {}
        for line in body:
            attr = _ATTR_RE.match(line.strip())
            if attr:
                attrs[attr.group(1)] = attr.group(2)
        data = _table_rows(body)
        if _is_placeholder(title) or not data:
            continue
        result.append(
            {
                "id": chart["id"],
                "title": title,
                "unit": _clean(attrs.get("unit")),
                "caption": _clean(attrs.get("caption")),
                "source": _clean(attrs.get("source")),
                "data": data,
            }
        )
    return result


def _freeform(lines):
    """Return ``{"heading", "content"}`` — the maintainer heading + raw AsciiDoc."""
    heading = None
    body = []
    for line in lines:
        stripped = line.strip()
        if heading is None:
            match = _HEADING_RE.match(stripped)
            if match:
                heading = match.group(1).strip()
                continue
        if stripped.startswith("//"):
            continue
        body.append(line)
    content = "\n".join(body).strip("\n")
    if _is_placeholder(heading) or not content.strip():
        return None
    return {"heading": heading, "content": content}


def _build_blurb_and_code(lines):
    """Return ``{"blurb"?, "code"?}`` — an optional blurb plus one source block.

    Used by both ``[#about]`` and ``[#install]``.
    """
    blurb = _blurb(lines)
    code = _first_source_block(lines)
    section = {}
    if blurb and not _is_placeholder(blurb):
        section["blurb"] = blurb
    if code:
        section["code"] = code
    return section or None


def _build_links(lines):
    """Return ``{"common_use_case_url"?, "code_example_url"?}`` or None."""
    attrs = {}
    for line in lines:
        attr = _ATTR_RE.match(line.strip())
        if attr:
            attrs[attr.group(1)] = attr.group(2)
    links = {}
    if url := _clean(attrs.get("common-use-case-url")):
        links["common_use_case_url"] = url
    if url := _clean(attrs.get("code-example-url")):
        links["code_example_url"] = url
    return links or None


# Output key -> (section ID, builder). Each builder takes the section's body
# lines and returns a truthy value or a falsy/None value when it has nothing
# usable. Builders are run in isolation so one broken section is dropped
# without affecting the others.
_SECTION_BUILDERS = (
    ("about", "about", _build_blurb_and_code),
    ("playground", "playground", _first_source_block),
    ("designed_for", "designed-for", _subsections),
    ("links", "links", _build_links),
    ("install", "install", _build_blurb_and_code),
    ("benchmarks", "benchmarks", _benchmarks),
    ("freeform", "freeform", _freeform),
)


def _segment(content):
    """Split the document into ``{section_id: [body lines]}`` + document attrs.

    Anchors and comments inside ``----`` source blocks are treated as verbatim.
    """
    sections = {}
    doc_attrs = {}
    current_id = None
    body = []
    in_source = False
    in_comment = False
    for line in content.splitlines():
        stripped = line.strip()
        if not in_source and stripped == "////":
            in_comment = not in_comment
            continue
        if in_comment:
            continue
        if stripped == "----":
            in_source = not in_source
            if current_id is not None:
                body.append(line)
            continue
        if not in_source:
            anchor = _ANCHOR_RE.match(stripped)
            if anchor and anchor.group(1) in SECTION_IDS:
                if current_id is not None:
                    sections[current_id] = body
                current_id, body = anchor.group(1), []
                continue
            if stripped.startswith("//"):
                continue
            if current_id is None:
                attr = _ATTR_RE.match(stripped)
                if attr:
                    doc_attrs[attr.group(1)] = attr.group(2)
                    continue
        if current_id is not None:
            body.append(line)
    if current_id is not None:
        sections[current_id] = body
    return sections, doc_attrs


def parse_website_adoc(content):
    """Parse ``meta/website.adoc`` bytes/str into a dict, or ``None`` if empty.

    Returned keys are only present when the corresponding section has usable
    content. The ``freeform`` section carries raw AsciiDoc under ``content``;
    call ``build_website_adoc`` to also render it to HTML.
    """
    if content is None:
        return None
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    if not content.strip():
        return None

    sections, doc_attrs = _segment(content)
    parsed = {}

    if library_key := _clean(doc_attrs.get("library-key")):
        parsed["library_key"] = library_key

    for out_key, section_id, builder in _SECTION_BUILDERS:
        if section_id not in sections:
            continue
        try:
            value = builder(sections[section_id])
        except Exception:
            # A broken section is dropped; the rest of the document is unaffected.
            logger.exception("website_adoc_section_failed", section=section_id)
            continue
        if value:
            parsed[out_key] = value

    return parsed or None


def build_website_adoc(content):
    """Parse and render for storage on ``LibraryVersion.website_adoc``.

    Same as ``parse_website_adoc`` but also renders the free-form section's
    AsciiDoc to HTML (``freeform["html"]``) via the asciidoctor gem.
    """
    parsed = parse_website_adoc(content)
    if parsed and "freeform" in parsed:
        try:
            parsed["freeform"]["html"] = convert_adoc_to_html(
                parsed["freeform"]["content"]
            )
        except Exception:
            # If the gem can't render the free-form AsciiDoc, drop only that
            # section — every other section is still returned.
            logger.exception("website_adoc_freeform_render_failed")
            parsed.pop("freeform", None)
    return parsed or None


def fetch_website_adoc(client, repo_slug, tag):
    """Fetch and parse ``meta/website.adoc`` for a repo/tag.

    Never raises — returns ``None`` on a missing file or any parse/render
    error, so it is safe to call inline in the ingestion pipeline.
    """
    try:
        content = client.get_website_adoc(repo_slug=repo_slug, tag=tag)
        return build_website_adoc(content)
    except Exception:
        logger.exception("website_adoc_parse_failed", repo=repo_slug, tag=tag)
        return None
