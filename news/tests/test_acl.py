import pytest
from model_bakery import baker

from ..acl import (
    author_needs_moderation,
    can_approve,
    can_delete,
    can_edit,
    can_view,
    moderators,
)
from ..models import NEWS_MODELS


def test_moderators_empty():
    assert list(moderators().order_by("id")) == []


def test_moderators_superuser(superuser):
    assert list(moderators()) == [superuser]


def test_moderators_user_with_perms(make_user):
    user = make_user(perms=["news.change_entry"])
    p = baker.make(
        "Permission",
        content_type=baker.make("ContentType", app_label="foo"),
        codename="change_entry",
    )
    assert p.content_type.app_label == "foo"
    make_user(perms=[p])  # ignored due to incorrect app_label
    assert list(moderators()) == [user]


def test_moderators_user_with_group(make_user):
    user = make_user(groups={"moderator": ["news.change_entry"]})
    assert list(moderators()) == [user]


def test_moderators_user_inactive(regular_user, moderator_user, superuser):
    moderator_user.is_active = False
    moderator_user.save()
    assert list(moderators()) == [superuser]


def test_moderators_many_users(regular_user, moderator_user, superuser):
    baker.make("users.User", _quantity=3)  # make other users
    assert list(moderators().order_by("id")) == [moderator_user, superuser]


def test_moderators_complex(tp, make_user, moderator_user, superuser):
    p = baker.make(
        "Permission",
        content_type=baker.make("ContentType", app_label="foo"),
        codename="change_entry",
    )
    expected = [
        moderator_user,
        superuser,
        make_user(groups={"moderator": ["news.change_entry"], "other": ["users.*"]}),
        make_user(perms=["news.change_entry"]),
        make_user(perms=["news.*"]),
        # exercise .distinct() by having a user with perms and group
        make_user(groups={"genius": ["news.change_entry"]}, perms=["news.*"]),
    ]
    # not moderators
    make_user(groups={"different": ["users.*"]})
    make_user(perms=[p])
    make_user(perms=[p, "news.delete_entry", "news.view_entry", "news.add_entry"])
    make_user(is_staff=True)
    make_user(perms=["news.change_entry"], is_active=False)

    with tp.assertNumQueriesLessThan(2, verbose=True):
        actual = list(moderators().order_by("id"))

    assert actual == expected


@pytest.mark.parametrize("model_class", NEWS_MODELS)
@pytest.mark.parametrize("approved", [False, True])
def test_entry_permissions_author(make_entry, model_class, approved):
    entry = make_entry(model_class, approved=approved)

    assert can_view(entry.author, entry) is True
    assert can_edit(entry.author, entry) is not approved
    assert can_delete(entry.author, entry) is False
    assert can_approve(entry.author, entry) is False


@pytest.mark.parametrize("model_class", NEWS_MODELS)
@pytest.mark.parametrize("approved", [False, True])
def test_entry_permissions_no_user(make_entry, model_class, approved):
    entry = make_entry(model_class, approved=approved)

    assert can_view(None, entry) is approved
    assert can_edit(None, entry) is False
    assert can_delete(None, entry) is False
    assert can_approve(None, entry) is False


@pytest.mark.parametrize("model_class", NEWS_MODELS)
@pytest.mark.parametrize("approved", [False, True])
def test_entry_permissions_regular_user(
    make_entry, regular_user, model_class, approved
):
    entry = make_entry(model_class, approved=approved)

    assert can_view(regular_user, entry) is approved
    assert can_edit(regular_user, entry) is False
    assert can_delete(regular_user, entry) is False
    assert can_approve(regular_user, entry) is False


@pytest.mark.parametrize("model_class", NEWS_MODELS)
@pytest.mark.parametrize("approved", [False, True])
def test_entry_permissions_superuser(make_entry, superuser, model_class, approved):
    entry = make_entry(model_class, approved=approved)

    assert can_view(superuser, entry) is True
    assert can_edit(superuser, entry) is True
    assert can_delete(superuser, entry) is True
    assert can_approve(superuser, entry) is True


@pytest.mark.parametrize("model_class", NEWS_MODELS)
@pytest.mark.parametrize("approved", [False, True])
def test_entry_permissions_other_users(make_user, make_entry, model_class, approved):
    entry = make_entry(model_class, approved=approved)

    user_with_add_perm = make_user(perms=["news.add_entry"])
    assert can_view(user_with_add_perm, entry) is approved
    assert can_edit(user_with_add_perm, entry) is False
    assert can_delete(user_with_add_perm, entry) is False
    assert can_approve(user_with_add_perm, entry) is False

    user_with_change_perm = make_user(perms=["news.change_entry"])
    assert can_view(user_with_change_perm, entry) is approved
    assert can_edit(user_with_change_perm, entry) is True
    assert can_delete(user_with_change_perm, entry) is False
    assert can_approve(user_with_change_perm, entry) is True

    user_with_delete_perm = make_user(perms=["news.delete_entry"])
    assert can_view(user_with_delete_perm, entry) is approved
    assert can_edit(user_with_delete_perm, entry) is False
    assert can_delete(user_with_delete_perm, entry) is True
    assert can_approve(user_with_delete_perm, entry) is False

    user_with_view_perm = make_user(perms=["news.view_entry"])
    assert can_view(user_with_view_perm, entry) is True
    assert can_edit(user_with_view_perm, entry) is False
    assert can_delete(user_with_view_perm, entry) is False
    assert can_approve(user_with_view_perm, entry) is False


def test_entry_author_needs_moderation_basic(make_entry):
    entry = make_entry()

    assert entry.author_needs_moderation() is True


def test_entry_author_needs_moderation_moderator(make_entry, moderator_user):
    entry = make_entry(author=moderator_user)

    assert author_needs_moderation(entry) is False


def test_entry_author_needs_moderation_allowlist(make_entry, make_user, settings):
    user = make_user()
    entry = make_entry(author=user)

    settings.NEWS_MODERATION_ALLOWLIST = []
    assert author_needs_moderation(entry) is True

    settings.NEWS_MODERATION_ALLOWLIST = [user.email]
    assert author_needs_moderation(entry) is False

    settings.NEWS_MODERATION_ALLOWLIST = [user.pk]
    assert author_needs_moderation(entry) is False
