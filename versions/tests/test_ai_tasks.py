from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker
from openai import APIError

from core.models import RenderedContent
from versions.tasks import (
    WHATS_NEW_MAX_INPUT_CHARS,
    generate_whats_new,
    save_whats_new,
)
from versions.models import Version

SAMPLE_OUTPUT = (
    "- **New libraries** — Three new libraries broaden coverage of "
    "scientific computing and modern C++ patterns.\n"
    "- **Performance improvements** — Compile-time and runtime gains "
    "are reported across multiple core components.\n"
    "- **Security & reliability** — Several stability and correctness "
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
    assert len(version.whats_new_items) == 3
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
    assert version.whats_new_generated_at is None


@pytest.mark.django_db
def test_save_whats_new_resets_approval(version):
    Version.objects.filter(pk=version.pk).update(whats_new_approved=True)
    save_whats_new.run(SAMPLE_OUTPUT, version.pk)

    version.refresh_from_db()
    assert version.whats_new_approved is False


@pytest.mark.django_db
def test_generate_whats_new_truncates_long_input(version):
    long_text = "x" * (WHATS_NEW_MAX_INPUT_CHARS + 50_000)
    baker.make(
        RenderedContent,
        cache_key=version.release_notes_cache_key,
        content_type="text/asciidoc",
        content_original=long_text,
    )

    with patch("versions.tasks.OpenAI") as mock_openai:
        client = mock_openai.return_value
        client.chat.completions.create.return_value = _mock_openai_response(
            SAMPLE_OUTPUT
        )
        generate_whats_new.run(version.pk)

    sent_messages = client.chat.completions.create.call_args.kwargs["messages"]
    user_content = next(m["content"] for m in sent_messages if m["role"] == "user")
    assert len(user_content) == WHATS_NEW_MAX_INPUT_CHARS


@pytest.mark.django_db
def test_generate_whats_new_propagates_openai_error(version):
    baker.make(
        RenderedContent,
        cache_key=version.release_notes_cache_key,
        content_type="text/asciidoc",
        content_original="release notes",
    )

    with patch("versions.tasks.OpenAI") as mock_openai:
        client = mock_openai.return_value
        # APIError is a concrete OpenAIError subclass.
        client.chat.completions.create.side_effect = APIError(
            message="boom", request=MagicMock(), body=None
        )
        with pytest.raises(APIError):
            generate_whats_new.run(version.pk)


@pytest.mark.django_db
def test_whats_new_items_parses_bullets(version):
    Version.objects.filter(pk=version.pk).update(whats_new=SAMPLE_OUTPUT)
    version.refresh_from_db()

    items = version.whats_new_items
    assert len(items) == 3
    assert items[0]["title"] == "New libraries"
    assert items[0]["description"].startswith("Three new libraries")
    assert items[1]["title"] == "Performance improvements"
    assert items[2]["title"] == "Security & reliability"


@pytest.mark.django_db
def test_whats_new_items_empty_when_unset(version):
    assert version.whats_new == ""
    assert version.whats_new_items == []


@pytest.mark.django_db
def test_whats_new_items_ignores_non_bullet_lines(version):
    Version.objects.filter(pk=version.pk).update(
        whats_new=(
            "Some preamble that should be ignored.\n"
            "- **New libraries** — One library added.\n"
            "Trailing line without bullet.\n"
        )
    )
    version.refresh_from_db()
    items = version.whats_new_items
    assert len(items) == 1
    assert items[0]["title"] == "New libraries"


@pytest.mark.django_db
def test_whats_new_items_parses_colon_in_label(version):
    """A colon inside the bold label is stripped; the bullet marker is
    still required."""
    Version.objects.filter(pk=version.pk).update(
        whats_new=(
            "- **New libraries:** One new library introduces open-method support.\n"
            "* **Performance improvements:** Container redesigns deliver speed gains.\n"
        )
    )
    version.refresh_from_db()
    items = version.whats_new_items
    assert len(items) == 2
    assert items[0]["title"] == "New libraries"
    assert items[0]["description"].startswith("One new library")
    assert items[1]["title"] == "Performance improvements"


@pytest.mark.django_db
def test_whats_new_items_ignores_dashless_lines(version):
    """Lines without a leading bullet marker are not list items and are
    skipped."""
    Version.objects.filter(pk=version.pk).update(
        whats_new=(
            "**New libraries:** This line has no bullet marker.\n"
            "- **Performance improvements** — This one does.\n"
        )
    )
    version.refresh_from_db()
    items = version.whats_new_items
    assert len(items) == 1
    assert items[0]["title"] == "Performance improvements"
