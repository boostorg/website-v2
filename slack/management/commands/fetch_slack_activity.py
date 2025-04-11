import logging
import datetime
import functools
import time

from slack_sdk import WebClient
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler
import djclick as click
from django.db import transaction, connection
from django.db.models.functions import Now, Cast
from django.db.models import Q, FloatField
from django.conf import settings
from django.core.management import CommandError

from slack.models import (
    SlackUser,
    SlackActivityBucket,
    Channel,
    ChannelUpdateGap,
    Thread,
    parse_ts,
    ToTimestamp,
)


client = WebClient(token=settings.SLACK_BOT_TOKEN)
client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=10))

logger = logging.getLogger(__name__)


def get_my_channels():
    for page in client.conversations_list():
        for channel in page["channels"]:
            if channel["is_member"]:
                yield channel


def channel_messages_in_range(channel, oldest, latest):
    """
    All messages in a channel newer than oldest (not inclusive so we don't
    double count). Returns an iterator over pages, which are iterators over
    messages. Newest messages come first.
    """
    pages = client.conversations_history(
        channel=channel,
        oldest=oldest,
        latest=latest,
        inclusive=False,
    )
    for page in pages:
        yield page["messages"]


def thread_messages_newer(channel, thread_ts, oldest):
    """
    All messages in a thread newer than oldest (not inclusive so we don't
    double count). Returns an iterator over pages. Oldest messages come first.
    """
    pages = client.conversations_replies(
        channel=channel,
        ts=thread_ts,
        oldest=oldest,
        inclusive=False,
    )
    for page in pages:
        yield page["messages"]


# Track users whose profile information has been updated in our DB and
# doesn't need to be checked again.
USERS_CACHE = {}


def get_or_create_user(user_id):
    try:
        return USERS_CACHE[user_id]
    except KeyError:
        # Even if the user exists already in our db, they may have changed
        # their information in slack so we need to check.
        user_data = client.users_info(user=user_id)
        obj, _ = SlackUser.objects.update_or_create(
            id=user_id,
            defaults={
                "name": user_data.data["user"]["name"],
                "real_name": user_data.data["user"].get("real_name", ""),
                "email": user_data.data["user"]["profile"].get("email", ""),
                "image_48": user_data["user"]["profile"].get("image_48", ""),
            },
        )
        USERS_CACHE[user_id] = obj
        return obj


def should_track_message(message):
    # These are not regular messages
    # https://api.slack.com/events/message#subtypes
    return message.get("subtype") in {None, "me_message"} and "bot_id" not in message


def fill_channel_gap(gap: ChannelUpdateGap, debug: bool):
    """
    Download and process channel messages (not including replies to threads) in
    the (possibly unbounded) range specified by `gap`.
    """
    logger.info(
        f"Fetching channel history for {gap.channel.name} ({gap.channel.id}) "
        f"in range ({gap.oldest_message_ts}, {gap.newest_message_ts})"
    )
    pages = channel_messages_in_range(
        channel=gap.channel.id,
        latest=gap.newest_message_ts,
        oldest=gap.oldest_message_ts,
    )
    first = True
    for page in pages:
        # use a separate transaction per page to allow restoring from an
        # interrupted run.
        with transaction.atomic():
            for message in page:
                if first and gap.newest_message_ts is None:
                    gap.channel.last_update_ts = message["ts"]
                    gap.channel.save()
                    first = False
                # Shrink the gap, but no need to save until we've finished this
                # page (transactionally).
                gap.newest_message_ts = message["ts"]

                if not should_track_message(message):
                    continue

                if "user" in message:
                    user = get_or_create_user(message["user"])
                    if debug:
                        gap.channel.seenmessage_set.create(ts=message["ts"])
                    SlackActivityBucket.track_activity(gap.channel, user, message["ts"])

                if message.get("thread_ts"):
                    # Track this thread in the db to be able to check for
                    # updates later.
                    # Thread replies that are broadcast back to the channel have
                    # the same thread_ts as the parent message thread_ts.
                    # get_or_create must be used since the thread may have already been
                    # created.
                    Thread.objects.get_or_create(
                        channel=gap.channel,
                        thread_ts=message["thread_ts"],
                        # None indicates that this thread still must be updated
                        # even if it's old.
                        defaults={"last_update_ts": None},
                    )

            gap.save()
            logger.debug(
                "Channel %r retrieved up to %s (%s)",
                gap.channel.name,
                # for the 'up to current' gap, newest_message_ts will be None
                # and instead oldest_message_ts will be where we stopped.
                gap.newest_message_ts or gap.oldest_message_ts,
                parse_ts(gap.newest_message_ts or gap.oldest_message_ts),
            )
    # If we get here we must have gotten up to gap.oldest_message_ts, the gap
    # is now empty. If we're interrupted before we get here, the gap will stay
    # and be picked up from where we left off on the next run.
    gap.delete()


def do_thread(thread: Thread, debug: bool):
    """
    Download and process new messages in the specified thread.
    """
    pages = thread_messages_newer(
        channel=thread.channel_id,
        thread_ts=thread.thread_ts,
        oldest=thread.last_update_ts,
    )
    for page in pages:
        with transaction.atomic():
            for message in page:
                if message["thread_ts"] == message["ts"]:
                    # This is the parent message, it was already counted as a
                    # channel message. Slack always returns the first message
                    # even if it's older than the oldest we requested.
                    if thread.last_update_ts is None:
                        # However, still record that this thread was updated.
                        # I think this will only will only matter if all
                        # messages in the thread have been deleted.
                        thread.last_update_ts = message["ts"]
                    continue

                # We never need to look at this message again. Oldest messages
                # come first unlike for channels.
                thread.last_update_ts = message["ts"]

                if message.get("subtype") == "thread_broadcast":
                    # This message was broadcast to the channel, if we count it here
                    # we will be double counting it.
                    continue

                if not should_track_message(message):
                    continue

                if debug:
                    thread.channel.seenmessage_set.create(
                        ts=message["ts"],
                        thread=thread,
                    )
                user = get_or_create_user(message["user"])
                SlackActivityBucket.track_activity(thread.channel, user, message["ts"])
            thread.save()


def locked(lock_id):
    """
    Runs the decorated function while holding a lock to prevent multiple
    concurrent instances.
    """

    def decorator_factory(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            cur = connection.cursor()
            ID = lock_id  # random number to identify this command
            cur.execute("SELECT pg_try_advisory_lock(%s);", [ID])
            (got_lock,) = cur.fetchone()
            if not got_lock:
                raise CommandError(
                    "Could not obtain lock: "
                    "another instance of this command must be running."
                )
            try:
                return fn(*args, **kwargs)
            finally:
                cur.execute("SELECT pg_advisory_unlock(%s);", [ID])

        return inner

    return decorator_factory


@click.command()
@click.argument("channels", nargs=-1)
@click.option(
    "--debug",
    is_flag=True,
    help=(
        "Store all messages seen to be able to "
        "detect bugs (uses lots of database space)."
    ),
)
@locked(1028307)
def command(channels, debug):
    """
    Download slack activity from channels the bot is a member of.

    CHANNELS is an optional list of channel names (without the #) to limit to.
    If not provided, all channels the bot is a member of will be fetched.

    This is resumable -- it can be interrupted and restarted without losing
    progress.

    A thread does not exist until a user replies to an existing message.
    It is therefore, possible that thread messages are missed.
        1. Message "M" is sent.
        2. Import is run.
        3. Reply "R" to "M" is sent. "M" is now the parent of a thread.
        4. "R" will never be imported because the thread was not created
            and there is no way for us to know that it was created, aside
            from looking back at all historical messages.
    Note: If a user replies to a message and selects "also send in channel",
    then this import will find that thread and the thread messages will be
    accounted for.

    Do not run multiple instances of this command in parallel.
    """

    channels = set(channels)
    selected_channels = []
    if channels:
        for channel_data in get_my_channels():
            if channel_data["name"] in channels:
                selected_channels.append(channel_data)
                channels.remove(channel_data["name"])
        if channels:
            raise click.BadParameter(
                f"Could not find channels {channels} (maybe the bot isn't a member?)"
            )
    else:
        # materialize this generator so we can iterate multiple times
        selected_channels.extend(get_my_channels())

    for channel_data in selected_channels:
        with transaction.atomic():
            channel, created = Channel.objects.update_or_create(
                id=channel_data["id"],
                defaults={
                    "name": channel_data["name"],
                    "topic": channel_data["topic"]["value"],
                    "purpose": channel_data["purpose"]["value"],
                },
            )
            if created:
                # we don't have any messages for this channel we just created
                channel.channelupdategap_set.create(
                    oldest_message_ts=None,
                    newest_message_ts=None,
                )
            elif (
                channel.last_update_ts
                and not channel.channelupdategap_set.filter(
                    newest_message_ts=None
                ).exists()
            ):
                # gap from the most recent fetch till now
                channel.channelupdategap_set.create(
                    oldest_message_ts=channel.last_update_ts,
                    newest_message_ts=None,
                )
            else:
                assert (
                    channel.channelupdategap_set.exists()
                ), "We must have SOME gaps, time has passed since the last run!"

    gaps = ChannelUpdateGap.objects.filter(
        channel__id__in={c["id"] for c in selected_channels}
    )
    for gap in gaps:
        fill_channel_gap(gap, debug)

    # We have to track threads we've seen and update independently, replies
    # don't show up in main channel history[1].
    #
    # [1]: <https://github.com/slackapi/python-slack-sdk/issues/1306>
    logger.info("Fetching threads")
    threads = Thread.objects.annotate(
        last_update_as_datetime=ToTimestamp(
            Cast("last_update_ts", output_field=FloatField())
        ),
    ).filter(
        # Assume threads not updated for more than 1 month won't get posted to
        # again. Otherwise it's too much work to check all threads ever.
        # last_update_ts will be null for the threads do_channel just created,
        # indicating they need to be updated at least once.
        Q(last_update_as_datetime=None)
        | Q(last_update_as_datetime__gte=Now() - datetime.timedelta(days=30)),
        channel_id__in={c["id"] for c in selected_channels},
    )
    time.sleep(5)  # cool off overall rate limit before importing threads
    total_threads = threads.count()
    for idx, thread in enumerate(threads, start=1):
        # Throttle - we're only allowed 20 requests per minute
        time.sleep(1.5)
        logger.info(
            f"Importing thread {idx:,} of {total_threads:,} "
            f"({idx/total_threads:.2%}) from #{thread.channel.name}"
        )
        do_thread(thread, debug)
