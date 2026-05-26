from versions.templatetags.whats_new_extras import inline_markdown


def test_inline_markdown_wraps_backticks():
    assert inline_markdown("use `foo` here") == "use <code>foo</code> here"


def test_inline_markdown_handles_multiple_backtick_spans():
    assert inline_markdown("`a` then `b`") == "<code>a</code> then <code>b</code>"


def test_inline_markdown_wraps_bold():
    assert (
        inline_markdown("ship **major** changes")
        == "ship <strong>major</strong> changes"
    )


def test_inline_markdown_handles_multiple_bold_spans():
    assert (
        inline_markdown("**a** plus **b**")
        == "<strong>a</strong> plus <strong>b</strong>"
    )


def test_inline_markdown_handles_bold_and_code_together():
    assert (
        inline_markdown("**fix** in `Foo::bar`")
        == "<strong>fix</strong> in <code>Foo::bar</code>"
    )


def test_inline_markdown_escapes_html_outside_markdown():
    assert (
        inline_markdown("<script>x</script> `safe`")
        == "&lt;script&gt;x&lt;/script&gt; <code>safe</code>"
    )


def test_inline_markdown_escapes_html_inside_backticks():
    assert inline_markdown("`<b>`") == "<code>&lt;b&gt;</code>"


def test_inline_markdown_escapes_html_inside_bold():
    assert inline_markdown("**<i>x</i>**") == "<strong>&lt;i&gt;x&lt;/i&gt;</strong>"


def test_inline_markdown_empty_returns_empty_string():
    assert inline_markdown("") == ""
    assert inline_markdown(None) == ""


def test_inline_markdown_no_markup_still_escapes():
    assert inline_markdown("<i>plain</i>") == "&lt;i&gt;plain&lt;/i&gt;"


def test_inline_markdown_single_asterisks_left_alone():
    """Italic-style single asterisks are not in scope — pass through literally."""
    assert inline_markdown("*italic*") == "*italic*"


def test_inline_markdown_does_not_bold_inside_code_span():
    """`**` inside a code span stays literal — a code span wins over bold."""
    assert inline_markdown("`a**b**c`") == "<code>a**b**c</code>"
