from datetime import timedelta
import pytest
from django.template.loader import render_to_string
from django.utils import timezone
from model_bakery import baker
from ..models import Version
from ..views import VersionDetail


def test_version_most_recent_detail(version, tp):
    """
    GET /releases/
    """
    now = timezone.now()

    ten_years_ago = now - timedelta(days=365 * 10)
    baker.make("versions.Version", name="boost-0.0.0", release_date=ten_years_ago)
    res = tp.get_check_200("releases-most-recent", follow=True)
    assert "versions" in res.context
    assert res.context["version"] == version


def test_version_detail_no_data(tp):
    """
    GET /releases/
    """
    Version.objects.all().delete()
    tp.get_check_200("releases-most-recent", follow=True)


def test_version_detail(version, tp):
    """
    GET /releases/{version_slug}/
    """
    res = tp.get("release-detail", version_slug=version.slug)
    tp.response_200(res)


@pytest.mark.django_db
def test_get_v3_context_data_current_release(version):
    view = VersionDetail()
    view.object = version
    view.extra_context = {"current_version": version}

    ctx = view.get_v3_context_data()

    assert ctx["hero_title"] == f"Latest Release ({version.display_name})"
    assert ctx["whats_new_heading"] == f"What's new in {version.display_name}"
    assert ctx["whats_new_approved"] == version.whats_new_approved
    assert ctx["whats_new_items"] == version.whats_new_items
    assert ctx["contributors_guide_url"]
    assert ctx["release_process_url"]


@pytest.mark.django_db
def test_get_v3_context_data_uses_extra_context_current_version(version):
    """Heading derives from extra_context['current_version'], not a fresh query."""
    other_current = baker.make("versions.Version", name="boost-1.90.0")
    view = VersionDetail()
    view.object = version
    view.extra_context = {"current_version": other_current}

    ctx = view.get_v3_context_data()

    assert ctx["hero_title"] == f"Prior Release ({version.display_name})"


@pytest.mark.django_db
def test_get_v3_context_data_hides_whats_new_until_approved(version):
    """Parsed items are only exposed once whats_new_approved is True, so
    unreviewed AI drafts never reach the public release page."""
    version.whats_new = "- **New libraries** — Adds three new libraries."
    view = VersionDetail()
    view.object = version
    view.extra_context = {"current_version": version}

    version.whats_new_approved = False
    assert view.get_v3_context_data()["whats_new_items"] == []

    version.whats_new_approved = True
    assert view.get_v3_context_data()["whats_new_items"] == [
        {"title": "New libraries", "description": "Adds three new libraries."}
    ]


@pytest.mark.django_db
def test_get_v3_context_data_sets_downloads_hero_images(version):
    """The downloads hero needs all three URLs. The template threads them into
    `_hero_library.html` through an `only` include, so a missing one degrades
    silently: no background, or a foreground that falls back to the desktop crop
    on phones."""
    view = VersionDetail()
    view.object = version
    view.extra_context = {"current_version": version}

    ctx = view.get_v3_context_data()

    assert "releases-page/release-foreground.png" in ctx["hero_image_url"]
    assert "releases-page/release-foreground-mobile.png" in ctx["hero_image_url_mobile"]
    assert "releases-page/release-background.png" in ctx["hero_background_image_url"]


def _hero_html(**extra):
    context = {
        "title": "Boost 1.70.0",
        "selected_version": Version(slug="boost-1-70-0"),
    }
    context.update(extra)
    return render_to_string("v3/includes/_hero_library.html", context)


def _slot_html(**extra):
    context = {"selected_version": Version(slug="boost-1-70-0")}
    context.update(extra)
    return render_to_string("v3/includes/_messages.html", context)


def test_slot_renders_version_alert_message():
    """The slot must receive version_alert_message or the banner renders empty
    (regressed once when the message moved from the template into
    VersionAlertMixin)."""
    html = _slot_html(
        version_alert=True,
        version_alert_message="This is an older version of Boost.",
    )
    assert "This is an older version of Boost." in html
    assert "banner__message" in html


def test_slot_omits_banner_without_message():
    assert "banner__message" not in _slot_html(version_alert=True)


def test_hero_no_longer_renders_the_version_alert():
    """The alert belongs to base.html's notification slot now, so it stacks with
    flash messages instead of overlapping them."""
    html = _hero_html(
        version_alert=True,
        version_alert_message="This is an older version of Boost.",
    )
    assert "banner__message" not in html


def test_hero_uses_fullbleed_frame_for_the_release_scene():
    """The release art is a full-scene illustration composed to the block, so it
    needs the shared `.hero-fg` frame rather than the small-box `.hero__image`.
    Dropping `fullbleed_fg` renders it in a 488x416 box instead."""
    html = _hero_html(hero_image_url="/x/release-foreground.png", fullbleed_fg=True)
    assert "hero-fg__img" in html
    assert "hero__img" not in html


def test_hero_emits_the_mobile_source_when_a_mobile_crop_is_given():
    """Guards the <picture> art-direction: without the <source> the desktop crop
    is used at every width, which is what blanks the scene on phones."""
    html = _hero_html(
        hero_image_url="/x/release-foreground.png",
        hero_image_url_mobile="/x/release-foreground-mobile.png",
        fullbleed_fg=True,
    )
    assert 'media="(max-width: 767px)"' in html
    assert "release-foreground-mobile.png" in html


def test_hero_omits_the_mobile_source_without_a_mobile_crop():
    html = _hero_html(hero_image_url="/x/release-foreground.png", fullbleed_fg=True)
    assert "<source" not in html
