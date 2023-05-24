import datetime

import pytest
from django.contrib.auth.models import Permission
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
        entry = baker.make(model_class, **kwargs)
        entry.author.set_password("password")
        entry.author.save()
        return entry

    return _make_it


@pytest.fixture
def moderator_user(db):
    # we could use `tp.make_user` but we need this fix to be released
    # https://github.com/revsys/django-test-plus/issues/199
    user = baker.make("users.User")
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="news", content_type__model="entry"
        )
    )
    user.set_password("password")
    user.save()
    return user


@pytest.fixture
def regular_user(db):
    user = baker.make("users.User")
    user.set_password("password")
    user.save()
    return user
