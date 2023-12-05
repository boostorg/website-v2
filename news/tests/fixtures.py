import datetime

import pytest
from django.db.models import Q
from django.contrib.auth.models import Group, Permission
from django.utils.timezone import now
from model_bakery import baker


@pytest.fixture
def make_entry(db):
    def _make_it(model_class="Entry", approved=True, published=True, **kwargs):
        past = now() - datetime.timedelta(hours=1)
        future = now() + datetime.timedelta(days=1)
        if approved:
            approved_at = past
            moderator = baker.make("users.User")
        else:
            approved_at = None
            moderator = None
        if published:
            publish_at = past
        else:
            publish_at = future
        kwargs.setdefault("approved_at", approved_at)
        kwargs.setdefault("moderator", moderator)
        kwargs.setdefault("publish_at", publish_at)
        kwargs.setdefault("title", "Admin User's Q3 Update")
        entry = baker.make(model_class, **kwargs)
        entry.author.set_password("password")
        entry.author.save()
        return entry

    return _make_it


@pytest.fixture
def make_user(db):
    def _filter_perms(perms):
        result = []

        perms_filter = Q(codename="false")
        for perm in perms:
            if isinstance(perm, Permission):
                result.append(perm)
                continue

            if "." not in perm:
                raise ValueError(
                    "The perms argument should be a list of app_label.codename or "
                    "app_label.* (e.g. accounts.change_user or accounts.*)"
                )
            app_label, codename = perm.split(".")
            if codename == "*":
                perms_filter |= Q(content_type__app_label=app_label)
            else:
                perms_filter |= Q(content_type__app_label=app_label, codename=codename)

        result.extend(Permission.objects.filter(perms_filter))
        assert len(result) >= len(perms)
        return result

    def _make_it(
        perms=None,
        groups=None,
        password="password",
        allow_notification_others_news_posted=None,
        **kwargs,
    ):
        user = baker.make("users.User", **kwargs)
        user.set_password(password)
        user.save()

        if allow_notification_others_news_posted is not None:
            user.preferences.allow_notification_others_news_posted = (
                allow_notification_others_news_posted
            )
            user.preferences.save()

        if perms:
            user.user_permissions.add(*list(_filter_perms(perms)))

        if groups:
            group_instances = []
            for name, perms in groups.items():
                group = Group.objects.create(name=name)
                group.permissions.set(_filter_perms(perms))
                group_instances.append(group)
            user.groups.add(*group_instances)

        return user

    return _make_it


@pytest.fixture
def moderator_user(db, make_user):
    # we could use `tp.make_user` but we need this fix to be released
    # https://github.com/revsys/django-test-plus/issues/199
    user = make_user(email="moderator@example.com", perms=["news.*"])
    user.image = "test.png"
    user.save()
    return user


@pytest.fixture
def regular_user(db, make_user):
    user = make_user(email="regular@example.com")
    user.image = "test.png"
    user.save()
    return user


@pytest.fixture
def superuser(db, make_user):
    return make_user(
        email="superuser@example.com",
        is_superuser=True,
        password="admin",
        groups={},
        perms=[],
    )
