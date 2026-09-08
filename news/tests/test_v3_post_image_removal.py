"""Removing — not just replacing — the image on a v3 post (issue #2668).

`set_page_attrs` only ever assigned `page.image` when a file was uploaded, so
there was no submission that could clear it. The create/edit template now posts
`remove_image=1` from the "Remove Image" button beside the preview.
"""

from io import BytesIO

import pytest
import waffle.testutils
from django.contrib.auth.models import Group
from django.core.files.images import ImageFile
from django.utils.timezone import now
from PIL import Image as PILImage
from wagtail.images.models import Image
from wagtail.models import GroupApprovalTask, Workflow, WorkflowPage, WorkflowTask

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def v3_flag():
    with waffle.testutils.override_flag("v3", active=True):
        yield


@pytest.fixture(autouse=True)
def site(wagtail_site):
    """The view redirects to the index page's URL, which is None without a site."""


@pytest.fixture(autouse=True)
def post_workflow(post_index_page):
    """The moderation workflow that submitting an edit starts.

    Wagtail ships its default workflow as migration data, which --no-migrations
    skips, and the view calls `get_workflow().start()` unconditionally.
    """
    workflow = Workflow.objects.create(name="Moderators approval")
    task = GroupApprovalTask.objects.create(name="Moderators approval")
    task.groups.set([Group.objects.create(name="Moderators")])
    WorkflowTask.objects.create(workflow=workflow, task=task, sort_order=0)
    WorkflowPage.objects.create(workflow=workflow, page=post_index_page)
    return workflow


def png_file(name):
    """A real PNG, so Wagtail can generate a rendition for the preview."""
    buffer = BytesIO()
    PILImage.new("RGB", (100, 100), color=(155, 0, 0)).save(buffer, "png")
    buffer.seek(0)
    buffer.name = name
    return buffer


@pytest.fixture
def wagtail_image():
    file = png_file("original.png")
    return Image.objects.create(
        title="original.png",
        file=ImageFile(file, name=file.name),
        width=100,
        height=100,
    )


@pytest.fixture
def post(make_post_page, user, wagtail_image):
    """A post owned by `user`, with an image and an open edit window."""
    page = make_post_page(owner=user, image=wagtail_image)
    page.save_revision()
    return page


def submit(tp, page, **overrides):
    """POST the edit form for `page`, echoing back its current values."""
    data = {
        "post_type": page.post_content_type.lower(),
        "title": page.title,
        "content": page.content[0].value,
        "description": page.summary,
        "publish_at": now().strftime("%Y-%m-%dT%H:%M"),
    }
    data.update(overrides)
    return tp.post("v3-news-edit", slug=page.slug, data=data)


def latest_image(page):
    # `latest_revision` is an FK cached on the instance, so the revision the
    # POST just created is only visible after a refetch.
    page.refresh_from_db()
    return page.get_latest_revision_as_object().image


class TestRemoveImage:
    def test_the_flag_clears_the_image(self, tp, post, user):
        with tp.login(user):
            submit(tp, post, remove_image="1")

        assert latest_image(post) is None

    def test_without_the_flag_the_image_is_kept(self, tp, post, user, wagtail_image):
        """The original behaviour: an edit that touches nothing else keeps it."""
        with tp.login(user):
            submit(tp, post)

        assert latest_image(post) == wagtail_image

    def test_an_empty_flag_is_not_a_removal(self, tp, post, user, wagtail_image):
        """What the hidden input posts while the button has not been pressed."""
        with tp.login(user):
            submit(tp, post, remove_image="")

        assert latest_image(post) == wagtail_image

    def test_a_new_upload_wins_over_the_flag(self, tp, post, user, wagtail_image):
        """A stale flag must not discard the file the author just chose."""
        with tp.login(user):
            submit(tp, post, remove_image="1", image=png_file("replacement.png"))

        replacement = latest_image(post)
        assert replacement is not None
        assert replacement != wagtail_image

    def test_the_flag_is_harmless_with_no_image(self, tp, make_post_page, user):
        page = make_post_page(owner=user)
        page.save_revision()

        with tp.login(user):
            submit(tp, page, remove_image="1")

        assert latest_image(page) is None

    def test_the_edit_page_offers_the_controls(self, tp, post, user):
        with tp.login(user):
            response = tp.get("v3-news-edit", slug=post.slug)

        content = response.content.decode()
        assert 'aria-label="Replace image"' in content
        assert 'aria-label="Remove image"' in content
        assert 'name="remove_image"' in content
        # The preview hands its click target to the Replace control.
        assert 'aria-label="Change file"' not in content
