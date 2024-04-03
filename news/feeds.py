from datetime import datetime
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed
from django.utils.timezone import make_aware, utc
from django.utils.html import urlize, linebreaks

from .models import Entry


class RSSNewsFeed(Feed):
    """An RSS feed for Entry ("News" in the UI) items"""

    title = "News"
    link = "/news/"
    description = "Recent news for Boost C++ Libraries."

    def items(self):
        return Entry.objects.filter(published=True).order_by("publish_at")[:100]

    def item_pubdate(self, item):
        """Returns the publish date as a timezone-aware datetime object"""
        publish_date = item.publish_at
        if publish_date:
            datetime_obj = datetime.combine(publish_date, datetime.min.time())
            aware_datetime_obj = make_aware(datetime_obj, timezone=utc)
            return aware_datetime_obj

    def item_description(self, item):
        """Return the Entry content in the description field.

        If the Entry has an external URL (and no content), return a link to that URL
        instead.
        """

        if item.external_url and not item.content:
            return (
                f"External link to <a href='{ item.external_url }'>"
                f"{ item.external_url }</a>."
            )
        return linebreaks(urlize(item.content))

    def item_title(self, item):
        return item.title


class AtomNewsFeed(RSSNewsFeed):
    """The Atom feed version of the main Entry/News feed, which enables
    the extra fields like `pubdate`
    """

    feed_type = Atom1Feed
