from datetime import datetime
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed
from django.utils.timezone import make_aware, utc

from core.models import RenderedContent
from .models import Version


class RSSVersionFeed(Feed):
    """An RSS feed for Boost releases"""

    title = "Downloads"
    link = "/downloads/"
    description = "Recent downloads for Boost C++ Libraries."

    def items(self):
        return (
            Version.objects.active().filter(full_release=True).order_by("-name")[:100]
        )

    def item_pubdate(self, item):
        """Returns the release date as a timezone-aware datetime object"""
        release_date = item.release_date
        if release_date:
            datetime_obj = datetime.combine(release_date, datetime.min.time())
            aware_datetime_obj = make_aware(datetime_obj, timezone=utc)
            return aware_datetime_obj

    def item_description(self, item):
        """Return the Release Notes in the description field if they are present."""
        release_notes = RenderedContent.objects.filter(
            cache_key=item.release_notes_cache_key
        ).first()
        if release_notes:
            return release_notes.content_html
        return

    def item_title(self, item):
        return f"Version {item.display_name}"


class AtomVersionFeed(RSSVersionFeed):
    """The Atom feed version of the main feed, which enables
    the extra fields like `pubdate`
    """

    feed_type = Atom1Feed
