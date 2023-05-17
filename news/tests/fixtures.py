import datetime

import pytest
from django.utils.timezone import now
from model_bakery import baker


@pytest.fixture
def make_entry(db):
    def _make_it(approved=True, published=True, **kwargs):
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
        return baker.make("Entry", **kwargs)

    return _make_it
