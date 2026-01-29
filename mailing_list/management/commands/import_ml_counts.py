# Copyright 2024 Dave O'Connor
# Derived from code by Joaquin M Lopez Munoz.
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)
import djclick as click
import logging
import re
from datetime import timedelta, datetime


from mailing_list.constants import (
    ARG_DATE_REGEX,
    AUTHOR_PATTERN_REGEX,
    DATE_PATTERN_REGEX,
)
from mailing_list.models import PostingData, ListPosting

logger = logging.getLogger(__name__)

arg_date_pattern = re.compile(ARG_DATE_REGEX)
author_pattern = re.compile(AUTHOR_PATTERN_REGEX)
date_pattern = re.compile(DATE_PATTERN_REGEX)


def parse_datetime(date_str: str, is_start: bool) -> datetime:
    """
    Parse a date string (YYYY, YYYY-MM, YYYY-MM-DD) into a datetime object.

    If is_start=True, returns the earliest time possible for the data given.
    If is_start=False, returns the latest time possible for the data given.
    """
    m = arg_date_pattern.match(date_str)
    if not m:
        raise ValueError(f"Invalid date format: {date_str!r}")

    year_text, month_text, day_text = m.groups()
    year = int(year_text)
    month = int(month_text) if month_text is not None else (1 if is_start else 12)
    day = int(day_text) if day_text is not None else 1

    if is_start:
        # Start date - return start of day
        return datetime(year, month, day, 0, 0, 0)

    # End date - return latest datetime possible from given criteria
    if day_text is None:
        # No day provided: find the last day of the month
        first_of_next_month = (datetime(year, month, 1) + timedelta(days=31)).replace(
            day=1
        )
        last_day_of_month = first_of_next_month - timedelta(days=1)
        day = last_day_of_month.day

    return datetime(year, month, day, 23, 59, 59)


def retrieve_authors(start_date, end_date):
    logger.info(f"Retrieve_authors from {start_date:%Y-%m-%d} to {end_date:%Y-%m-%d}")
    authors = []
    for p in ListPosting.objects.filter(date__gte=start_date, date__lte=end_date):
        authors.append(PostingData(name=p.sender_id, post_time=p.date))

    PostingData.objects.filter(
        post_time__gte=start_date, post_time__lte=end_date
    ).delete()
    PostingData.objects.bulk_create(authors)


@click.command()
@click.option("--start_date", is_flag=False, help="Start Date", default=None)
@click.option("--end_date", is_flag=False, help="End Date", default=None)
def command(start_date, end_date):
    logger.info(f"Starting import_ml_counts {start_date=} {end_date=}")
    start_date = (
        parse_datetime(start_date, is_start=True)
        if start_date
        else datetime(1998, 11, 11)
    )
    logger.info(f"{start_date = }")
    end_date = parse_datetime(end_date, is_start=False) if end_date else datetime.now()
    logger.info(f"{end_date = }")
    retrieve_authors(start_date, end_date)
