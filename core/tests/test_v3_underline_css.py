"""Guards the cross-browser underline invariant from #2297.

Firefox derives underline thickness and position from the font's own metrics
whenever those properties are left to the browser. For Mona Sans that seats the
line inside the descenders, and `text-decoration-skip-ink` then carves a gap
around every g/p/y, so the underline renders as disconnected fragments and
heavier than in Chromium.

`static/css/v3/foundations.css` pins the three properties once for every v3
anchor. These tests fail if a component rule takes that decision back, which is
the only way the bug can return. They read the stylesheets as text rather than
rendering anything, so they cost nothing and run in CI with everything else.
"""

import re
from pathlib import Path

import pytest

V3_CSS = Path(__file__).resolve().parents[2] / "static" / "css" / "v3"

# Vendored from the boostlook repo and updated wholesale, so it is not ours to
# hold to this rule.
EXCLUDED = {"boostlook-v3.css"}

# The declarations that hand the decision back to the browser. A percentage is
# included because Figma exports these as percentages of the font size, which
# land on fractional pixels (7.5% of 14px = 1.05px) and round per engine.
HANDS_BACK_CONTROL = re.compile(
    r"""
    (?:text-decoration-thickness|text-underline-offset)\s*:\s*
        (?:auto|[\d.]+%)
    | text-underline-position\s*:\s*from-font
    | text-decoration-skip-ink\s*:\s*auto
    """,
    re.VERBOSE,
)

# `text-decoration` is a shorthand and resets text-decoration-thickness to
# `auto`. In a :hover or :focus rule it outranks the shared rule, so the bug
# comes back on hover only, which is the hardest variant to notice. The -line
# longhand carries the same intent without the reset.
UNDERLINE_SHORTHAND = re.compile(r"(?<!-)\btext-decoration\s*:\s*[^;]*underline")
STATE_SELECTOR = re.compile(r":(?:hover|focus|focus-visible|active|visited)")

# The shared rule's three declarations, and the selector that has to carry them.
SHARED_RULE_SELECTOR = "body.v3 a"
SHARED_RULE_DECLARATIONS = (
    ("text-decoration-skip-ink", "none"),
    ("text-decoration-thickness", "1px"),
    ("text-underline-offset", "2px"),
)


def _without_comments(text):
    """Blank out /* ... */ comments, preserving newlines so line numbers hold.

    Needed because foundations.css's own warning comment names the very values
    these tests ban, and would otherwise match.
    """
    return re.sub(
        r"/\*.*?\*/",
        lambda m: re.sub(r"[^\n]", " ", m.group(0)),
        text,
        flags=re.DOTALL,
    )


def _stylesheets():
    return sorted(p for p in V3_CSS.glob("*.css") if p.name not in EXCLUDED)


def _rules(path):
    """Yield (selector, body) for each rule in a stylesheet.

    Deliberately naive: a regex, not a parser. It is enough for flat component
    stylesheets and keeps the test dependency-free. The selector keeps its whole
    comma-separated list on one line, because dropping any part of it would hide
    a `:hover` that appears in a lead selector rather than the last one.
    """
    source = _without_comments(path.read_text())
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", source):
        yield " ".join(match.group(1).split()), match.group(2)


def test_stylesheets_are_discoverable():
    """A silent glob miss would make every test below pass for the wrong reason."""
    sheets = _stylesheets()
    assert len(sheets) > 20, f"only found {len(sheets)} v3 stylesheets in {V3_CSS}"
    assert (V3_CSS / "foundations.css") in sheets


def test_shared_underline_rule_is_present():
    """The other tests only make sense if the rule they defer to still exists.

    All three declarations have to sit in one rule that reaches v3 anchors.
    Finding them scattered across the file would not pin anything, so this walks
    the rule bodies rather than searching the stylesheet as a whole.
    """
    candidates = []
    for selector, body in _rules(V3_CSS / "foundations.css"):
        if SHARED_RULE_SELECTOR not in selector:
            continue
        missing = [
            f"{prop}: {value}"
            for prop, value in SHARED_RULE_DECLARATIONS
            if not re.search(rf"{prop}\s*:\s*{value}\b", body)
        ]
        if not missing:
            return
        candidates.append((selector, missing))

    detail = (
        "\n".join(
            f"  `{selector}` is missing {', '.join(missing)}"
            for selector, missing in candidates
        )
        or f"  no rule in foundations.css selects `{SHARED_RULE_SELECTOR}`"
    )
    raise AssertionError(
        "foundations.css no longer pins the underline geometry in a single rule "
        f"for `{SHARED_RULE_SELECTOR}`:\n" + detail + "\n\nIf the shared rule "
        "moved, point these tests at its new home rather than deleting them."
    )


@pytest.mark.parametrize("path", _stylesheets(), ids=lambda p: p.name)
def test_no_rule_hands_underline_geometry_back_to_the_browser(path):
    """No v3 rule may set these to `auto`, a percentage, or `from-font`.

    Any of them reopens #2297 for that component alone, which is why this is
    worth a test rather than a comment. The whole stylesheet is scanned in one
    pass, not line by line, so a declaration wrapped after its colon cannot slip
    through.
    """
    source = _without_comments(path.read_text())
    offenders = [
        (source.count("\n", 0, m.start()) + 1, " ".join(m.group(0).split()))
        for m in HANDS_BACK_CONTROL.finditer(source)
    ]
    assert not offenders, (
        f"{path.name} hands underline geometry back to the browser:\n"
        + "\n".join(f"  line {i}: {text}" for i, text in offenders)
        + "\n\nLeave these three properties to the shared rule in foundations.css."
    )


@pytest.mark.parametrize("path", _stylesheets(), ids=lambda p: p.name)
def test_state_rules_do_not_reset_thickness_via_the_shorthand(path):
    """A :hover rule using the `text-decoration` shorthand resets thickness.

    It outranks the shared rule, so the underline goes heavy on hover only. Use
    `text-decoration-line` instead, or pin the thickness in the same rule.
    """
    offenders = [
        selector
        for selector, body in _rules(path)
        if STATE_SELECTOR.search(selector)
        and UNDERLINE_SHORTHAND.search(body)
        and "text-decoration-thickness" not in body
    ]
    assert not offenders, (
        f"{path.name} resets text-decoration-thickness on a state rule:\n"
        + "\n".join(f"  {s}" for s in offenders)
        + "\n\nUse `text-decoration-line: underline`, which does not reset it."
    )
