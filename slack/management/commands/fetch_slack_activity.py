import logging
import functools
import time
import re
from datetime import date, datetime, time as dt_time, timedelta, timezone
from itertools import chain
from typing import Generator

from slack_sdk import WebClient
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler
import djclick as click
from django.db import transaction, connection
from django.conf import settings
from django.core.management import CommandError

from core.constants import SLACK_URL
from slack.models import SlackUser, SlackActivityBucket, Channel, parse_ts


client = WebClient(token=settings.SLACK_BOT_TOKEN)
client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=10))

logger = logging.getLogger(__name__)

OVERLAP_INTERVAL_DAYS = 4


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
        # rate-limit to prevent 429 responses, max 50 messages per minute
        time.sleep(1.21)
        yield page["messages"]


def thread_messages_newer(channel, thread_ts):
    """
    All messages in a thread. Returns an iterator over pages. Oldest messages come first.
    """
    pages = client.conversations_replies(
        channel=channel,
        ts=thread_ts,
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
    return (
        message.get("subtype") in {None, "me_message"}
        and "bot_id" not in message
        and "user" in message
    )


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


def date_to_midnight_datetime(d: date) -> float:
    return datetime.combine(d, dt_time.min, tzinfo=timezone.utc).timestamp()


def count_channel_messages(
    channel_user_messages: dict,
    channel_id: str,
    update_date: date,
    pages: Generator,
    is_thread: bool,
) -> None:
    """
    @param channel_user_messages - an update by reference record of all slack messages by [day, user] = set(id,...,n)
    @param channel_id - the slack id of the channel
    @param update_date - the date for which to update the channel messages
    @param pages - a Generator with data from conversations_history or conversations_replies to be iterated over
    @param is_thread - whether this is a thread or top-level comment

    @return: None

    Iterates over messages for a day and any threads within that day to update the message count, including saving
    thread messages into future-day records.
    All changes are stored in the passed-in channel_user_messages
    """
    update_date_str = str(update_date)
    channel_user_messages.setdefault(update_date_str, {})

    for msg in chain.from_iterable(pages):
        if not should_track_message(msg):
            continue
        # decided against using setdefault for ease of reading
        if msg["user"] not in channel_user_messages[update_date_str]:
            channel_user_messages[update_date_str][msg["user"]] = set()
        # for some bizarre reason ts is the canonical "id" used for a message. wtf slack?
        channel_user_messages[update_date_str][msg["user"]].add(msg["ts"])

        # iterate over any thread and add messages to data, this will save messages in later days too
        # adding every user message in a thread isn't a problem in terms of dupes, because set
        if not is_thread and "thread_ts" in msg:
            thread_pages = thread_messages_newer(channel_id, msg["thread_ts"])
            count_channel_messages(
                channel_user_messages,
                channel_id,
                update_date,
                thread_pages,
                is_thread=True,
            )


def save_channel_stats(
    channel_user_messages: dict,
    channel: Channel,
    update_date: date,
    end_time: float,
):
    update_date_str = str(update_date)
    # guard rails are around each day worth of data
    with transaction.atomic():
        if day_messages := channel_user_messages[update_date_str]:
            for slack_user in day_messages:
                user = get_or_create_user(slack_user)
                channel_msg_count = len(day_messages[slack_user])
                SlackActivityBucket.objects.update_or_create(
                    day=update_date,
                    user=user,
                    channel=channel,
                    defaults={"count": channel_msg_count},
                )

        # account for channel updates that occur during the overlap (don't use those dates as last updated date)
        if float(channel.last_update_ts) < end_time:
            channel.last_update_ts = str(end_time)
            channel.save()
        # clean up the dict's now processed data
        del channel_user_messages[update_date_str]


def update_channel_message_counts(channel: Channel):
    channel_created = parse_ts(channel.channel_created_ts)
    last_channel_update_db = parse_ts(channel.last_update_ts)  # last processed

    # starting point from which to update the db is the newest of the channel creation date or last update minus 2 weeks
    # we overlap on previous runs in order to catch thread changes
    update_date = (
        max(channel_created, last_channel_update_db)
        - timedelta(days=OVERLAP_INTERVAL_DAYS)
    ).date()

    # only process completed days, stop a day before now() to account for runs mid-day
    processing_end_date = datetime.now().date()
    logger.info(f"Start: {update_date=} - {processing_end_date=}, {channel.name=}")
    channel_user_messages = {}
    while update_date != processing_end_date:
        logger.info(f"Updating data for {channel.name=} on {update_date=}")
        start_time = date_to_midnight_datetime(update_date)
        end_time = date_to_midnight_datetime(update_date + timedelta(days=1)) - 0.001
        day_pages = channel_messages_in_range(channel.id, start_time, end_time)
        # update the channel user messages (relies on pass by reference)
        count_channel_messages(
            channel_user_messages, channel.id, update_date, day_pages, is_thread=False
        )
        save_channel_stats(channel_user_messages, channel, update_date, end_time)

        update_date = update_date + timedelta(days=1)
        logger.info(f"Updated data for {channel.name=}, {update_date=}")

    logger.info(f"End: {update_date=} - {processing_end_date=}, {channel.name=}")


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

    def interpolate_text_usernames(text):
        user_mentions = re.findall(r"<@([A-Z0-9]+)>", text)
        for user_id in user_mentions:
            try:
                slack_user = SlackUser.objects.get(id=user_id)
                profile_url = f"{SLACK_URL}/team/{user_id}"
                text = text.replace(
                    f"<@{user_id}>", f'<a href="{profile_url}">@{slack_user.name}</a>'
                )
            except SlackUser.DoesNotExist:
                logger.warning(f"SlackUser {user_id} not found in database")
                continue

        return text

    def interpolate_text_slack_channels(text):
        # match both <#CHANNELID> and <#CHANNELID|optional_text>
        channel_mentions = re.findall(r"<#([A-Z0-9]+)(?:\|[^>]*)?>", text)
        for channel_id in channel_mentions:
            try:
                channel = Channel.objects.get(id=channel_id)
                channel_name = channel.name
            except Channel.DoesNotExist:
                try:
                    # fetch channel info from Slack API
                    channel_data = client.conversations_info(channel=channel_id)
                    channel_name = channel_data.data["channel"]["name"]
                    logger.info(
                        f"Fetched channel name {channel_name} for {channel_id} from API"
                    )
                except Exception as e:
                    logger.warning(f"Failed to get channel info for {channel_id}: {e}")
                    continue

            # replace the full match including any pipe content
            pattern = f"<#{channel_id}(?:\\|[^>]*)?>"
            text = re.sub(pattern, f"#{channel_name}", text)

        return text

    def interpolate_text_subteams(text):
        # returns early because we don't have usergroups:read permission added and
        # the only channel that really needs this data parsed at the moment is
        # #general which doesn't appear in the release report. If we need it in
        # the future, Sam says we'd need to create a new bot with that permission.
        return text

        # match <!subteam^SUBTEAMID> patterns
        subteam_mentions = re.findall(r"<!subteam\^([A-Z0-9]+)>", text)
        for subteam_id in subteam_mentions:
            try:
                usergroups_data = client.usergroups_list()
                for usergroup in usergroups_data.data["usergroups"]:
                    if usergroup["id"] == subteam_id:
                        subteam_name = usergroup["handle"]
                        text = text.replace(
                            f"<!subteam^{subteam_id}>", f"@{subteam_name}"
                        )
                        break
                else:
                    logger.warning(f"Subteam {subteam_id} not found in usergroups list")
            except Exception as e:
                logger.warning(f"Failed to get subteam info for {subteam_id}: {e}")
                continue

        return text

    def interpolate_text_urls_with_jinja_links(text):
        return re.sub(r"<(https?://[^>]+)>", r'<a href="\1">\1</a>', text)

    for channel_data in selected_channels:
        with transaction.atomic():
            topic = channel_data["topic"]["value"]
            if topic:
                topic = interpolate_text_usernames(topic)
                topic = interpolate_text_slack_channels(topic)
                topic = interpolate_text_subteams(topic)
                topic = interpolate_text_urls_with_jinja_links(topic)
            purpose = channel_data["purpose"]["value"]
            if purpose:
                purpose = interpolate_text_usernames(purpose)
                purpose = interpolate_text_slack_channels(purpose)
                purpose = interpolate_text_subteams(purpose)
                purpose = interpolate_text_urls_with_jinja_links(purpose)

            channel, created = Channel.objects.update_or_create(
                id=channel_data["id"],
                defaults={
                    "name": channel_data["name"],
                    "topic": topic,
                    "purpose": purpose,
                    "channel_created_ts": channel_data["created"],
                },
            )

        logger.info(f"updating {channel.id=}")
        update_channel_message_counts(channel)
