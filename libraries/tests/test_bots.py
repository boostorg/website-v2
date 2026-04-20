from unittest.mock import MagicMock

import pytest
from model_bakery import baker

from libraries.bots import is_bot_name
from libraries.github import LibraryUpdater
from libraries.mixins import ContributorMixin
from libraries.models import CommitAuthor


@pytest.mark.parametrize(
    "name, expected",
    [
        ("copilot-swe-agent[bot]", True),
        ("Copilot-SWE-Agent[Bot]", True),
        ("dependabot[bot]", True),
        ("Renovate [Bot]", True),
        ("", False),
        (None, False),
        ("Jane Doe", False),
        ("not-a-bot", False),
    ],
)
def test_is_bot_name(name, expected):
    assert is_bot_name(name) is expected


@pytest.mark.django_db
def test_commit_author_is_bot_default_false():
    author = baker.make(CommitAuthor, name="Jane Doe")
    assert author.is_bot is False


@pytest.mark.django_db
def test_save_auto_flags_bot_on_create():
    author = CommitAuthor.objects.create(name="some-tool[bot]")
    assert author.is_bot is True


@pytest.mark.django_db
def test_save_preserves_admin_override_on_update():
    author = CommitAuthor.objects.create(name="some-tool[bot]")
    author.is_bot = False
    author.save()
    author.refresh_from_db()
    assert author.is_bot is False


@pytest.mark.django_db
def test_bulk_create_auto_flags_bot():
    created = CommitAuthor.objects.bulk_create(
        [
            CommitAuthor(name="Jane Doe"),
            CommitAuthor(name="renovate[bot]"),
            CommitAuthor(name="Jenkins nedprod CI"),
        ]
    )
    by_name = {a.name: a for a in created}
    assert by_name["Jane Doe"].is_bot is False
    assert by_name["renovate[bot]"].is_bot is True
    assert by_name["Jenkins nedprod CI"].is_bot is True


@pytest.mark.django_db
def test_humans_manager_excludes_bots():
    human = baker.make(CommitAuthor, name="Jane Doe", is_bot=False)
    bot = baker.make(CommitAuthor, name="some-tool[bot]", is_bot=True)

    assert human in CommitAuthor.humans.all()
    assert bot not in CommitAuthor.humans.all()
    assert {human, bot}.issubset(set(CommitAuthor.objects.all()))


@pytest.mark.django_db
def test_github_sync_flips_is_bot_when_type_is_bot(library, version):
    lv = baker.make("libraries.LibraryVersion", library=library, version=version)
    author = baker.make(CommitAuthor, name="dependabot[bot]", avatar_url=None)
    baker.make(
        "libraries.Commit",
        author=author,
        library_version=lv,
        sha="abc123",
    )

    updater = LibraryUpdater()
    updater.client = MagicMock()
    updater.client.get_repo_ref.return_value = {
        "author": {
            "type": "Bot",
            "avatar_url": "https://example.com/a.png",
            "html_url": "https://github.com/dependabot",
        }
    }

    updater.update_commit_author_github_data(obj=library)

    author.refresh_from_db()
    assert author.is_bot is True


@pytest.mark.django_db
def test_github_sync_does_not_flip_is_bot_back_to_false(library, version):
    lv = baker.make("libraries.LibraryVersion", library=library, version=version)
    author = baker.make(
        CommitAuthor, name="ambiguous-user", avatar_url=None, is_bot=True
    )
    baker.make(
        "libraries.Commit",
        author=author,
        library_version=lv,
        sha="abc123",
    )

    updater = LibraryUpdater()
    updater.client = MagicMock()
    updater.client.get_repo_ref.return_value = {
        "author": {
            "type": "User",
            "avatar_url": "https://example.com/a.png",
            "html_url": "https://github.com/ambiguous-user",
        }
    }

    updater.update_commit_author_github_data(obj=library)

    author.refresh_from_db()
    assert author.is_bot is True


@pytest.mark.django_db
def test_get_top_contributors_excludes_bots(library_version):
    human = baker.make(CommitAuthor, name="Jane Doe", is_bot=False)
    bot = baker.make(CommitAuthor, name="copilot-swe-agent", is_bot=True)
    baker.make("libraries.Commit", author=human, library_version=library_version)
    baker.make("libraries.Commit", author=bot, library_version=library_version)

    result = ContributorMixin().get_top_contributors(library_version=library_version)
    ids = set(result.values_list("id", flat=True))

    assert human.id in ids
    assert bot.id not in ids


@pytest.mark.django_db
def test_get_previous_contributors_excludes_bots(library, version):
    older = baker.make(
        "versions.Version",
        name="boost-1.70.0",
        fully_imported=True,
    )
    prior_lv = baker.make("libraries.LibraryVersion", library=library, version=older)
    current_lv = baker.make(
        "libraries.LibraryVersion", library=library, version=version
    )

    human = baker.make(CommitAuthor, name="Jane Doe", is_bot=False)
    bot = baker.make(CommitAuthor, name="copilot-swe-agent", is_bot=True)
    baker.make("libraries.Commit", author=human, library_version=prior_lv)
    baker.make("libraries.Commit", author=bot, library_version=prior_lv)

    result = ContributorMixin().get_previous_contributors(library_version=current_lv)
    ids = set(result.values_list("id", flat=True))

    assert human.id in ids
    assert bot.id not in ids
