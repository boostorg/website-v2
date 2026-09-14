"""Guards the cross-browser underline invariant from #2297.

Firefox derives underline thickness and position from the font's own metrics
whenever those properties are left to the browser. For Mona Sans that seats the
line inside the descenders, and `text-decoration-skip-ink` then carves a gap
around every g/p/y, so the underline renders as disconnected fragments and
heavier than in Chromium.

`static/css/v3/foundations.css` pins the three properties for the whole v3 site.
#2794 widened that from the original per-selector list, which only reached
anchors and so missed every underline drawn by a <label>, <button> or <span>.
These tests fail if a component rule takes the decision back, which is the only
way the bug can return. They read the stylesheets as text rather than rendering
anything, so they cost nothing and run in CI with everything else.
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

# The shared declarations and the selector each one has to sit on. Split in two
# because the properties behave differently: skip-ink and offset inherit, so the
# page root carries them, while thickness does not and has to reach every element
# that might draw a line.
#
# Thickness is `!important` (#2794) because specificity cannot win that one: any
# `text-decoration` shorthand resets it to `auto`, `text-decoration: none`
# included, and the v3 stylesheets have well over a hundred of those. Dropping
# the `!important` reopens the bug wherever such a rule outranks this one.
SHARED_RULES = (
    (
        "body.v3",
        (
            ("text-decoration-skip-ink", "none"),
            ("text-underline-offset", "2px"),
        ),
    ),
    (
        "body.v3 :where(*)",
        (("text-decoration-thickness", "1px !important"),),
    ),
)

# Docs pages load boostlook-v3.css without components.css, so foundations.css
# never reaches them and the sheet has to carry its own copy (#2794).
BOOSTLOOK_RULES = (
    (
        ".boostlook",
        (
            ("text-decoration-skip-ink", "none"),
            ("text-underline-offset", "2px"),
        ),
    ),
    (
        ".boostlook :where(*)",
        (("text-decoration-thickness", "1px !important"),),
    ),
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


def _pattern(value):
    """Turn an expected declaration value into a whitespace-tolerant regex."""
    return re.escape(value).replace(r"\ ", r"\s*").replace(" ", r"\s*")


def _assert_rules_present(path, required):
    """Every (selector, declarations) pair has to be satisfied by one rule.

    Finding the declarations scattered across separate rules would not pin
    anything, so this walks the rule bodies rather than searching the stylesheet
    as a whole, and matches the selector exactly: `body.v3` and
    `body.v3 :where(*)` are different rules doing different jobs.
    """
    failures = []
    for selector, declarations in required:
        candidates = []
        for found, body in _rules(path):
            if selector not in [part.strip() for part in found.split(",")]:
                continue
            missing = [
                f"{prop}: {value}"
                for prop, value in declarations
                if not re.search(rf"{prop}\s*:\s*{_pattern(value)}", body)
            ]
            if not missing:
                break
            candidates.append(missing)
        else:
            if candidates:
                detail = " / ".join(", ".join(m) for m in candidates)
                failures.append(f"  `{selector}` is missing {detail}")
            else:
                failures.append(f"  no rule in {path.name} selects `{selector}`")

    assert not failures, (
        f"{path.name} no longer pins the underline geometry:\n"
        + "\n".join(failures)
        + "\n\nIf the shared rules moved, point these tests at their new home "
        "rather than deleting them."
    )


def test_shared_underline_rules_are_present():
    """The other tests only make sense if the rules they defer to still exist."""
    _assert_rules_present(V3_CSS / "foundations.css", SHARED_RULES)


def test_boostlook_carries_its_own_underline_rules():
    """boostlook-v3.css is excluded from the scans below, but docs pages load it
    on its own, so it is the only thing pinning underlines there."""
    _assert_rules_present(V3_CSS / "boostlook-v3.css", BOOSTLOOK_RULES)


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
