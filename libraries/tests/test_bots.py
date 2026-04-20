import pytest
from model_bakery import baker

from libraries.bots import is_bot_name
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
