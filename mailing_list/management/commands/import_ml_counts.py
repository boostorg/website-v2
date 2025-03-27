# Copyright 2024 Dave O'Connor
# Derived from code by Joaquin M Lopez Munoz.
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)
import djclick as click
import logging
import re
import warnings
from datetime import timedelta, datetime
import html

from dateutil.relativedelta import relativedelta
from unidecode import unidecode

import requests

from mailing_list.constants import (
    ML_STATS_URLS,
    LATIN_1_EQUIVS,
    ARG_DATE_REGEX,
    AUTHOR_PATTERN_REGEX,
    DATE_PATTERN_REGEX,
)
from mailing_list.models import PostingData

logger = logging.getLogger(__name__)

arg_date_pattern = re.compile(ARG_DATE_REGEX)
author_pattern = re.compile(AUTHOR_PATTERN_REGEX)
date_pattern = re.compile(DATE_PATTERN_REGEX)


def decode_broken_html(str):
    def latin_1_ord(char):
        n = ord(char)
        return LATIN_1_EQUIVS.get(n, n)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return unidecode(
            bytearray(map(latin_1_ord, html.unescape(str))).decode("utf-8", "ignore")
        )


def parse_start_datetime(date_str):
    m = arg_date_pattern.match(date_str)
    if not m:
        raise ValueError("wrong date format")
    logger.info(f"{m=} {m.group(1)=} {m.group(2)=} {m.group(3)=}")
    return datetime(
        int(m.group(3)) if m.group(3) else 1,
        int(m.group(2)) if m.group(2) else 1,
        int(m.group(1)),
        0,
        0,
        0,
    )


def parse_end_datetime(date_str):
    m = arg_date_pattern.match(date_str)
    if not m:
        raise ValueError("wrong date format")
    logger.info(f"{m=} {m.group(1)=} {m.group(2)=} {m.group(3)=}")
    if m.group(2):
        if m.group(3):
            return datetime(
                int(m.group(3)), int(m.group(2)), int(m.group(1)), 23, 59, 59
            )
        else:
            return (
                datetime(int(m.group(1)), int(m.group(2)), 1) + timedelta(days=31),
                23,
                59,
                59,
            ).replace(day=1) - timedelta(days=1)
    return datetime(int(m.group(1)), 12, 31, 23, 59, 59)


def retrieve_authors_from_ml(url, start_date, end_date):
    posts = []
    logger.info(f"Retrieving data from {url=}.")
    r = requests.get(url)
    if r.status_code == 404:
        return posts

    author = None
    for line in r.text.splitlines():
        author_match = author_pattern.match(line)
        if author_match:
            # needs multiple passes to work
            author = decode_broken_html(author_match.group(1))
        else:
            date_pattern_match = date_pattern.match(line)
            if author and date_pattern_match:
                post_date = datetime.strptime(
                    date_pattern_match.group(1), "%Y-%m-%d %H:%M:%S"
                )
                if start_date <= post_date and post_date <= end_date:
                    posts.append(PostingData(name=author, post_time=post_date))
    return posts


def retrieve_authors(start_date, end_date):
    logger.info(f"retrieve_authors from {start_date=} to {end_date=}")
    start_month = datetime(start_date.year, start_date.month, 1)
    end_month = datetime(end_date.year, end_date.month, 1)
    authors = []
    while start_month <= end_month:
        for ml in ML_STATS_URLS:
            authors += retrieve_authors_from_ml(
                ml.format(start_month.year, start_month.month), start_date, end_date
            )
        start_month = start_month + relativedelta(months=+1)
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
        parse_start_datetime(start_date) if start_date else datetime(1998, 11, 11)
    )
    logger.info(f"{start_date=}")
    end_date = parse_end_datetime(end_date) if end_date else datetime.now()
    logger.info(f"{end_date=}")
    retrieve_authors(start_date, end_date)
