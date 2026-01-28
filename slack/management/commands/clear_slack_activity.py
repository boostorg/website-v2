import logging

import djclick as click
from django.db import transaction

from slack.models import SlackActivityBucket, Channel


logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--confirm",
    is_flag=True,
    help="Confirm deletion of all slack activity data.",
)
@click.option(
    "--last-update-ts",
    default="0",
    help="Timestamp to set for last_update_ts on all channels (default: 0).",
)
def command(confirm, last_update_ts):
    """
    Delete all records in SlackActivityBucket and ChannelUpdateGap tables,
    and set last_update_ts to "0" for all Channels.

    WARNING: This will delete all slack activity tracking data and reset
    all channels to their initial state. Use with caution.
    """
    if not confirm:
        logger.error(
            "This command will delete ALL slack activity data. "
            "Use --confirm flag to proceed."
        )
        return

    with transaction.atomic():
        activity_count = SlackActivityBucket.objects.count()
        channel_count = Channel.objects.count()

        logger.info(f"Deleting {activity_count:,} SlackActivityBucket records...")
        SlackActivityBucket.objects.all().delete()

        logger.info(f"Resetting last_update_ts for {channel_count:,} Channels...")
        Channel.objects.all().update(last_update_ts=last_update_ts)

        logger.info("Successfully cleared all slack activity data.")
