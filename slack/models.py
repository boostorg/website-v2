import datetime

from django.db import models, connection


def parse_ts(ts):
    seconds = float(ts)
    return datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)


class SlackUser(models.Model):
    id = models.CharField(max_length=16, primary_key=True)
    name = models.TextField()
    real_name = models.TextField()
    email = models.TextField()


class Channel(models.Model):
    id = models.CharField(max_length=16, primary_key=True)
    name = models.TextField()
    topic = models.TextField()
    purpose = models.TextField()
    last_update_ts = models.CharField(max_length=32, null=True)


class Thread(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    thread_ts = models.CharField(max_length=32)
    last_update_ts = models.CharField(max_length=32)

    class Meta:
        unique_together = [("channel", "thread_ts")]


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
            # BBB django 5.0 can do this with update_or_create(create_defaults)
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
