"""Wagtail's own workflow-notification emails render the V3 brand (issue #2764).

No custom notifier classes here: Wagtail's stock notifiers
(wagtail.admin.mail.*) stay connected and unmodified. Overriding the template
files at templates/wagtailadmin/notifications/ is enough, since Wagtail
resolves them by path through Django's normal template loader - these tests
exercise the real moderation flow end to end to prove that.
"""

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from model_bakery import baker
from wagtail.models import GroupApprovalTask, Workflow, WorkflowPage, WorkflowTask

pytestmark = pytest.mark.django_db


@pytest.fixture
def reviewer():
    """A user in the Moderators group, with notifications on by default."""
    group = Group.objects.create(name="Moderators")
    # Superuser so approving the only task can also publish the page - this
    # test is about the notification email, not page-publish permissions.
    user = baker.make("users.User", email="reviewer@example.com", is_superuser=True)
    user.groups.add(group)
    return user, group


@pytest.fixture
def moderated_page(wagtail_site, make_post_page, reviewer, user):
    """A post under a single-task moderation workflow, submitted for review."""
    _, group = reviewer
    page = make_post_page(owner=user)
    page.save_revision()

    workflow = Workflow.objects.create(name="Moderators approval")
    task = GroupApprovalTask.objects.create(name="Moderators approval")
    task.groups.set([group])
    WorkflowTask.objects.create(workflow=workflow, task=task, sort_order=0)
    WorkflowPage.objects.create(workflow=workflow, page=page)

    workflow.start(page, user=user)
    return page


def _html_alternative(msg):
    return next(
        content for content, mimetype in msg.alternatives if mimetype == "text/html"
    )


def test_task_submitted_sends_a_branded_html_email(moderated_page, reviewer):
    reviewer_user, _ = reviewer

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.recipients() == [reviewer_user.email]
    assert "needs your review" in msg.subject

    html = _html_alternative(msg)
    assert 'alt="Boost"' in html
    assert "needs your review" in html
    assert moderated_page.title in html
    assert moderated_page.summary in html
    # Wagtail's own default template's fingerprint style, absent once overridden.
    assert "#E6E6E6" not in html
    # Built from Wagtail's base_url_setting tag, not an unresolved context var.
    assert "://" in html
    assert "{{" not in html


def test_workflow_approved_sends_a_branded_html_email(moderated_page, user, reviewer):
    reviewer_user, _ = reviewer
    task_state = moderated_page.current_workflow_task_state
    mail.outbox.clear()

    task_state.approve(user=reviewer_user)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.recipients() == [user.email]
    assert "is approved" in msg.subject

    html = _html_alternative(msg)
    assert 'alt="Boost"' in html
    assert "Your post is approved" in html
    assert moderated_page.full_url in html
    assert moderated_page.title in html
    assert moderated_page.summary in html
    assert "#E6E6E6" not in html


def test_workflow_rejected_sends_a_branded_html_email(moderated_page, user, reviewer):
    reviewer_user, _ = reviewer
    task_state = moderated_page.current_workflow_task_state
    mail.outbox.clear()

    task_state.reject(user=reviewer_user, comment="Needs a source link.")

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.recipients() == [user.email]
    assert "needs changes" in msg.subject

    html = _html_alternative(msg)
    assert 'alt="Boost"' in html
    assert "Your post needs changes" in html
    assert "Needs a source link." in html
    assert moderated_page.title in html
    assert moderated_page.summary in html
    assert "#E6E6E6" not in html
