from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from core.models import RenderedContent
from versions.tasks import generate_whats_new, save_whats_new
from versions.models import Version


SAMPLE_OUTPUT = (
    "- 🆕 **New libraries** — Three new libraries broaden coverage of "
    "scientific computing and modern C++ patterns.\n"
    "- ⚡ **Performance improvements** — Compile-time and runtime gains "
    "are reported across multiple core components.\n"
    "- 🔒 **Security & reliability** — Several stability and correctness "
    "fixes land in this release.\n"
)


def _mock_openai_response(content: str):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


@pytest.mark.django_db
def test_generate_whats_new_populates_field(version):
    baker.make(
        RenderedContent,
        cache_key=version.release_notes_cache_key,
        content_type="text/asciidoc",
        content_original="Big release with new libraries and perf fixes.",
        content_html="<p>Big release with new libraries and perf fixes.</p>",
    )

    with patch("versions.tasks.OpenAI") as mock_openai:
        client = mock_openai.return_value
        client.chat.completions.create.return_value = _mock_openai_response(
            SAMPLE_OUTPUT
        )
        result = generate_whats_new.run(version.pk)

    assert result == SAMPLE_OUTPUT
    save_whats_new.run(result, version.pk)

    version.refresh_from_db()
    assert version.whats_new == SAMPLE_OUTPUT
    assert "<ul>" in version.whats_new_html
    assert version.whats_new_generated_at is not None
    # Drafts must not auto-publish.
    assert version.whats_new_approved is False


@pytest.mark.django_db
def test_generate_whats_new_no_release_notes_returns_none(version):
    # No RenderedContent row for this version's cache key.
    with patch("versions.tasks.OpenAI") as mock_openai:
        result = generate_whats_new.run(version.pk)

    assert result is None
    mock_openai.assert_not_called()


@pytest.mark.django_db
def test_generate_whats_new_version_not_found_returns_none():
    with patch("versions.tasks.OpenAI") as mock_openai:
        result = generate_whats_new.run(999999)

    assert result is None
    mock_openai.assert_not_called()


@pytest.mark.django_db
def test_save_whats_new_skips_empty(version):
    save_whats_new.run(None, version.pk)
    save_whats_new.run("", version.pk)

    version.refresh_from_db()
    assert version.whats_new == ""
    assert version.whats_new_html == ""
    assert version.whats_new_generated_at is None


@pytest.mark.django_db
def test_save_whats_new_sanitizes_html(version):
    save_whats_new.run(
        "- ok bullet\n- <script>alert(1)</script> sneaky\n",
        version.pk,
    )

    version.refresh_from_db()
    assert "<script>" not in version.whats_new_html
    assert "alert(1)" in version.whats_new_html  # text survives, tag does not


@pytest.mark.django_db
def test_save_whats_new_does_not_change_approval(version):
    Version.objects.filter(pk=version.pk).update(whats_new_approved=True)
    save_whats_new.run(SAMPLE_OUTPUT, version.pk)

    version.refresh_from_db()
    assert version.whats_new_approved is True


@pytest.mark.django_db
def test_whats_new_items_parses_bullets(version):
    Version.objects.filter(pk=version.pk).update(whats_new=SAMPLE_OUTPUT)
    version.refresh_from_db()

    items = version.whats_new_items
    assert len(items) == 3
    assert items[0]["title"].startswith("🆕")
    assert "New libraries" in items[0]["title"]
    assert items[0]["description"].startswith("Three new libraries")
    assert items[1]["title"].startswith("⚡")
    assert items[2]["title"].startswith("🔒")


@pytest.mark.django_db
def test_whats_new_items_empty_when_unset(version):
    assert version.whats_new == ""
    assert version.whats_new_items == []


@pytest.mark.django_db
def test_whats_new_items_ignores_non_bullet_lines(version):
    Version.objects.filter(pk=version.pk).update(
        whats_new=(
            "Some preamble that should be ignored.\n"
            "- 🆕 **New libraries** — One library added.\n"
            "Trailing line without bullet.\n"
        )
    )
    version.refresh_from_db()
    items = version.whats_new_items
    assert len(items) == 1
    assert items[0]["title"] == "🆕 New libraries"


@pytest.mark.django_db
def test_whats_new_items_parses_dashless_colon_format(version):
    """Real LLM output sometimes omits the bullet marker and puts the colon
    inside the bold label — the parser must accept that."""
    Version.objects.filter(pk=version.pk).update(
        whats_new=(
            "📦 **New libraries:** One new library introduces open-method support.\n"
            "⚡ **Performance improvements:** Container redesigns deliver speed gains.\n"
        )
    )
    version.refresh_from_db()
    items = version.whats_new_items
    assert len(items) == 2
    assert items[0]["title"] == "📦 New libraries"
    assert items[0]["description"].startswith("One new library")
    assert items[1]["title"] == "⚡ Performance improvements"
