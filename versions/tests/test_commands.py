from unittest.mock import patch

import pytest
from django.core.management import call_command
from model_bakery import baker

from core.models import RenderedContent


@pytest.fixture
def version_with_notes(db):
    v = baker.make(
        "versions.Version",
        name="boost-1.84.0",
        active=True,
        fully_imported=True,
    )
    baker.make(
        RenderedContent,
        cache_key=v.release_notes_cache_key,
        content_html="<p>notes</p>",
    )
    return v


@pytest.fixture
def version_with_notes_and_summary(db):
    v = baker.make(
        "versions.Version",
        name="boost-1.85.0",
        active=True,
        fully_imported=True,
        whats_new="- **New libraries** — already populated.",
    )
    baker.make(
        RenderedContent,
        cache_key=v.release_notes_cache_key,
        content_html="<p>notes</p>",
    )
    return v


@pytest.mark.django_db
def test_generate_whats_new_dry_run_does_not_dispatch(version_with_notes):
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command("generate_whats_new", "--all-missing", "--dry-run")

    mock_dispatch.assert_not_called()


@pytest.mark.django_db
def test_generate_whats_new_all_missing_skips_populated(
    version_with_notes, version_with_notes_and_summary
):
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command("generate_whats_new", "--all-missing")

    mock_dispatch.assert_called_once_with(version_with_notes.pk)


@pytest.mark.django_db
def test_generate_whats_new_force_includes_populated(
    version_with_notes, version_with_notes_and_summary
):
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command("generate_whats_new", "--all-missing", "--force")

    queued_pks = {call.args[0] for call in mock_dispatch.call_args_list}
    assert queued_pks == {version_with_notes.pk, version_with_notes_and_summary.pk}

    # --force only controls which versions are queued; the existing summary
    # is left intact until the chained save task lands its replacement.
    version_with_notes_and_summary.refresh_from_db()
    assert version_with_notes_and_summary.whats_new != ""


@pytest.mark.django_db
def test_generate_whats_new_version_skips_populated_without_force(
    version_with_notes_and_summary,
):
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command(
            "generate_whats_new", "--version", version_with_notes_and_summary.slug
        )

    mock_dispatch.assert_not_called()


@pytest.mark.django_db
def test_generate_whats_new_version_with_force_overrides_populated(
    version_with_notes_and_summary,
):
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command(
            "generate_whats_new",
            "--version",
            version_with_notes_and_summary.slug,
            "--force",
        )

    mock_dispatch.assert_called_once_with(version_with_notes_and_summary.pk)


@pytest.mark.django_db
def test_generate_whats_new_skips_versions_without_release_notes(db):
    baker.make(
        "versions.Version",
        name="boost-1.86.0",
        active=True,
        fully_imported=True,
    )
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command("generate_whats_new", "--all-missing")

    mock_dispatch.assert_not_called()


@pytest.mark.django_db
def test_generate_whats_new_single_version(version_with_notes):
    with patch(
        "versions.management.commands.generate_whats_new.dispatch_whats_new"
    ) as mock_dispatch:
        call_command("generate_whats_new", "--version", version_with_notes.slug)

    mock_dispatch.assert_called_once_with(version_with_notes.pk)


@pytest.mark.django_db
def test_generate_whats_new_requires_an_action():
    with pytest.raises(Exception):
        # djclick raises UsageError; pytest treats it as failure.
        call_command("generate_whats_new")
