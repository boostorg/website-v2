import datetime

from django.db import models
from django.db.models.expressions import Func

"""
`ts` fields from slack are actually IDs that can be interpreted into
timestamps.  We store them in a string as we get them from slack instead
of a DateTimeField to be able to pass them back exactly to slack without
precision or something causing round-tripping errors.
"""


def parse_ts(ts):
    seconds = float(ts)
    return datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)


class ToTimestamp(Func):
    """
    Implements the postgres to_timestamp(double precision) function.

    https://www.postgresql.org/docs/current/functions-datetime.html#FUNCTIONS-DATETIME-TABLE
    """

    function = "to_timestamp"
    output_field = models.DateTimeField()


class SlackUser(models.Model):
    id = models.CharField(max_length=16, primary_key=True)
    name = models.TextField()
    real_name = models.TextField()
    email = models.TextField()
    image_48 = models.URLField()


class Channel(models.Model):
    id = models.CharField(max_length=16, primary_key=True)
    name = models.TextField()
    topic = models.TextField()
    purpose = models.TextField()
    # We only need to check for new messages newer than this.
    last_update_ts = models.CharField(max_length=32, null=True)
    # use as a starting point on fresh data load
    channel_created_ts = models.CharField(max_length=32, null=True)


class SeenMessage(models.Model):
    """
    DEBUG ONLY: Store all seen messages to double-check we don't see them
    twice.

    Invariant:

        SeenMessage.objects.count() == \
            SlackActivityBucket.objects.aggregate(sum=Sum('count'))['sum']
    """

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    ts = models.CharField(max_length=32)
    message_time = models.DateTimeField(blank=True, null=True)
    db_created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(SlackUser, null=True, blank=True, on_delete=models.CASCADE)


class SlackActivityBucket(models.Model):
    """
    Message count per user per channel per UTC day.
    """

    day = models.DateField()
    user = models.ForeignKey(SlackUser, on_delete=models.CASCADE)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    count = models.PositiveIntegerField()

    class Meta:
        unique_together = [("channel", "day", "user")]
