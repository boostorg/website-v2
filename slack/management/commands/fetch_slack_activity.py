import logging

from slack_sdk import WebClient
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler
import djclick as click
from django.db import transaction
from django.conf import settings

from slack.models import (
    SlackUser,
    SlackActivityBucket,
    Channel,
    Thread,
    parse_ts,
)


client = WebClient(token=settings.SLACK_BOT_TOKEN)
client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=10))

logger = logging.getLogger(__name__)


def get_my_channels():
    for page in client.conversations_list():
        for channel in page["channels"]:
            if channel["is_member"]:
                yield channel


def channel_messages_newer(channel, oldest):
    """
    All messages in a channel newer than oldest (not inclusive so we
    don't double count)
    """
    pages = client.conversations_history(
        channel=channel, oldest=oldest, inclusive=False
    )
    for page in pages:
        yield from page["messages"]


def thread_messages_newer(channel, thread_ts, oldest):
    """
    All messages in a thread newer than oldest (not inclusive so we
    don't double count)
    """
    pages = client.conversations_replies(
        channel=channel,
        ts=thread_ts,
        oldest=oldest,
        inclusive=False,
    )
    for page in pages:
        yield from page["messages"]


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
            },
        )
        USERS_CACHE[user_id] = obj
        return obj


@transaction.atomic
def do_channel(channel_data):
    channel, _ = Channel.objects.update_or_create(
        id=channel_data["id"],
        defaults={
            "name": channel_data["name"],
            "topic": channel_data["topic"]["value"],
            "purpose": channel_data["purpose"]["value"],
        },
    )
    logger.info(
        "Fetching channel history for %r (%r) since %s",
        channel_data["name"],
        channel_data["id"],
        channel.last_update_ts and parse_ts(channel.last_update_ts),
    )
    messages = channel_messages_newer(
        channel=channel_data["id"], oldest=channel.last_update_ts
    )
    for index, message in enumerate(messages):
        if index == 0:
            # This is the most recent message in the channel
            channel.last_update_ts = message["ts"]
            channel.save()

        if index % 1000 == 0:
            logger.info(
                "Channel %r retrieved up to %s",
                channel_data["name"],
                parse_ts(message["ts"]),
            )

        if message.get("subtype") not in {None, "me_message"} or "bot_id" in message:
            # These are not regular messages
            # https://api.slack.com/events/message#subtypes
            continue

        if "user" in message:
            user = get_or_create_user(message["user"])
            SlackActivityBucket.track_activity(channel, user, message["ts"])

        if message.get("thread_ts"):
            # Track this thread in the db to be able to check for
            # updates later.
            Thread.objects.create(
                channel=channel,
                thread_ts=message["thread_ts"],
                # We just recorded activity of the thread-starting message.
                last_update_ts=message["thread_ts"],
            )


@transaction.atomic
def do_thread(thread):
    messages = thread_messages_newer(
        thread.channel_id, thread.thread_ts, thread.last_update_ts
    )
    last = None
    for message in messages:
        last = message
        if "bot_id" in message:
            continue
        if message["thread_ts"] == message["ts"]:
            # This is the parent message, it was already counted as a
            # channel message.
            continue

        user = get_or_create_user(message["user"])
        SlackActivityBucket.track_activity(thread.channel, user, message["ts"])
    # conversations_replies api returns oldest messages first unlike
    # conversations_history.
    if last is not None:
        thread.last_update_ts = last["ts"]
        thread.save()


@click.command()
@click.argument("channels", nargs=-1)
def command(channels):
    """
    Download slack activity from channels the bot is a member of.

    CHANNELS is an optional list of channel names (without the #) to limit to.
    If not provided, all channels the bot is a member of will be fetched.
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
                "Could not find channels %r (maybe the bot isn't a member?)" % channels
            )
    else:
        # materialize this generator so we can iterate multiple times
        selected_channels.extend(get_my_channels())

    for channel_data in selected_channels:
        do_channel(channel_data)
    # We have to track threads we've seen and update independently,
    # replies don't show up in main channel history.
    logger.info("Fetching threads")
    threads = Thread.objects.filter(channel_id__in={c["id"] for c in selected_channels})
    for thread in threads:
        do_thread(thread)
