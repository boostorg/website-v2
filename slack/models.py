import datetime

from django.db import models, connection
from django.db.models.expressions import Func
from django.db.models.functions import Cast

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
    # We only need to check for new messages strictly newer than this.
    last_update_ts = models.CharField(max_length=32, null=True)


class ChannelUpdateGap(models.Model):
    """
    Stores a (potentially unbounded) period of time where we haven't counted
    messages for a channel. Used to store progress and allow resumption.
    """

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    # There may be more messages to fetch that are strictly newer than
    # oldest_message_ts (null meaning no limit)
    oldest_message_ts = models.CharField(max_length=32, null=True)
    # but strictly older than newest_message_ts (null meaning no limit)
    newest_message_ts = models.CharField(max_length=32, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.lookups.GreaterThan(
                    models.functions.Cast(
                        "newest_message_ts", output_field=models.FloatField()
                    ),
                    models.functions.Cast(
                        "oldest_message_ts", output_field=models.FloatField()
                    ),
                ),
                name="newest_newer_than_oldest",
            )
        ]

    def __str__(self):
        return f"({self.oldest_message_ts}, {self.newest_message_ts})"

    def __repr__(self):
        return f"<ChannelUpdateGap: {self} ({self.id})>"


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
    thread = models.ForeignKey("Thread", on_delete=models.CASCADE, null=True)
    db_created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("channel", "ts")]


class Thread(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    thread_ts = models.CharField(max_length=32)
    last_update_ts = models.CharField(max_length=32, null=True)
    db_created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("channel", "thread_ts")]
        constraints = [
            models.CheckConstraint(
                condition=models.lookups.GreaterThanOrEqual(
                    models.functions.Cast(
                        "last_update_ts", output_field=models.FloatField()
                    ),
                    models.functions.Cast(
                        "thread_ts", output_field=models.FloatField()
                    ),
                ),
                name="update_newer_than_created",
            )
        ]
        indexes = [
            models.Index(
                ToTimestamp(Cast("last_update_ts", output_field=models.FloatField())),
                name="last_update_as_datetime",
            )
        ]


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

    @classmethod
    def track_activity(self, channel, user, ts):
        day = parse_ts(ts).date()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO slack_slackactivitybucket (day, user_id, channel_id, count)
                VALUES (%(day)s, %(user_id)s, %(channel_id)s, 1)
                ON CONFLICT (day, user_id, channel_id)
                DO UPDATE SET count = slack_slackactivitybucket.count + 1
                """,
                {
                    "user_id": user.id,
                    "channel_id": channel.id,
                    "day": day,
                },
            )
