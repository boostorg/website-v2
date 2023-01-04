import structlog

from dateutil.parser import ParserError, parse

logger = structlog.get_logger()


def parse_date(date_str):
    """Parses a date string to a datetime. Does not return an error."""
    try:
        return parse(date_str)
    except ParserError:
        logger.info("parse_date_invalid_date", date_str=date_str)
        return None
