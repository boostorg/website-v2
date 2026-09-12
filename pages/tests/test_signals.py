"""Notifying a PostPage's author and lighting the nav dot once it goes live."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from wagtail.signals import page_published, workflow_approved

from pages import signals
from pages.notifications import latest_notified_post_id


class _FakeWorkflowState:
    """Just enough of a `WorkflowState` for `flag_post_as_just_approved`."""

    def __init__(self, content_object):
        self.content_object = content_object


@pytest.fixture(autouse=True)
def _reset_workflow_approval_flag():
    """`pages.signals._local` is a thread-local, so it outlives any one test.

    Test DB rollback can reuse a page pk across tests, so a flag left behind
    by one test could wrongly suppress an unrelated later test's email.
    """
    signals._local.__dict__.clear()
    yield
    signals._local.__dict__.clear()


@pytest.mark.django_db
def test_first_publish_emails_the_author_and_lights_the_dot(
    user, wagtail_site, make_post_page, django_capture_on_commit_callbacks
):
    page = make_post_page(owner=user)
    page.last_published_at = page.first_published_at  # a true first publish

    with patch("pages.signals.send_post_published_email.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            page_published.send(sender=type(page), instance=page)

    delay.assert_called_once_with(page.pk)
    assert latest_notified_post_id() == page.pk


@pytest.mark.django_db
def test_republish_does_not_email_again(
    wagtail_site, make_post_page, django_capture_on_commit_callbacks
):
    page = make_post_page()
    page.last_published_at = page.first_published_at + timedelta(days=1)

    with patch("pages.signals.send_post_published_email.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            page_published.send(sender=type(page), instance=page)

    delay.assert_not_called()


@pytest.mark.django_db
def test_not_yet_live_does_not_email(
    wagtail_site, make_post_page, django_capture_on_commit_callbacks
):
    page = make_post_page(live=False)

    with patch("pages.signals.send_post_published_email.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            page_published.send(sender=type(page), instance=page)

    delay.assert_not_called()


@pytest.mark.django_db
def test_skips_author_with_no_email(
    user, wagtail_site, make_post_page, django_capture_on_commit_callbacks
):
    page = make_post_page(owner=user)
    page.last_published_at = page.first_published_at  # a true first publish
    page.author.email = ""
    page.author.save()

    with patch("pages.signals.send_post_published_email.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            page_published.send(sender=type(page), instance=page)

    delay.assert_not_called()


@pytest.mark.django_db
def test_auto_publish_on_approval_only_sends_wagtails_own_notice(
    user, wagtail_site, make_post_page, django_capture_on_commit_callbacks
):
    """A single-task workflow auto-publishes on approval: `page_published`
    fires, then `workflow_approved` fires for the same click. The author
    already gets Wagtail's own branded "your post is approved" notice for that
    approval, so the "you're live" email here should not double up on it.
    """
    page = make_post_page(owner=user)
    page.last_published_at = page.first_published_at  # a true first publish

    with patch("pages.signals.send_post_published_email.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            page_published.send(sender=type(page), instance=page)
            workflow_approved.send(
                sender=None, instance=_FakeWorkflowState(page), user=user
            )

    delay.assert_not_called()


@pytest.mark.django_db
def test_publish_without_a_concurrent_approval_still_emails(
    user, wagtail_site, make_post_page, django_capture_on_commit_callbacks
):
    """A page published on its own -- no workflow finishing in the same
    action -- still gets the "you're live" email, e.g. a later scheduled
    go-live after moderation cleared some other time.
    """
    page = make_post_page(owner=user)
    page.last_published_at = page.first_published_at  # a true first publish

    with patch("pages.signals.send_post_published_email.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            page_published.send(sender=type(page), instance=page)

    delay.assert_called_once_with(page.pk)


@pytest.mark.django_db
def test_approval_with_a_future_go_live_does_not_suppress_the_later_real_publish(
    user, wagtail_site, make_post_page, django_capture_on_commit_callbacks
):
    """Approving a workflow is not the same as the page going live.

    A `PostPage` with a future `go_live_at` still gets `workflow_approved` on
    approval, but `page_published` (which Wagtail fires unconditionally) sees
    `instance.live` still `False` and returns before registering a send -- so
    nothing in that transaction consumes the flag the approval just set. When
    the scheduled go-live actually publishes the page later, in its own
    separate transaction, that stale flag must not silently eat the real
    "you're live" email.
    """
    page = make_post_page(owner=user)

    with django_capture_on_commit_callbacks(execute=True):
        workflow_approved.send(
            sender=None, instance=_FakeWorkflowState(page), user=user
        )

    page.last_published_at = page.first_published_at  # the real, later publish
    with patch("pages.signals.send_post_published_email.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            page_published.send(sender=type(page), instance=page)

    delay.assert_called_once_with(page.pk)


@pytest.mark.django_db
def test_workflow_approved_for_a_different_page_does_not_suppress_this_one(
    user, wagtail_site, make_post_page, django_capture_on_commit_callbacks
):
    page = make_post_page(owner=user, title="A Post")
    page.last_published_at = page.first_published_at  # a true first publish
    other_page = make_post_page(title="A Different Post")

    with patch("pages.signals.send_post_published_email.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            workflow_approved.send(
                sender=None, instance=_FakeWorkflowState(other_page), user=user
            )
            page_published.send(sender=type(page), instance=page)

    delay.assert_called_once_with(page.pk)
