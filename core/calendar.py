import datetime
from django.conf import settings
import requests
from collections import defaultdict

from dateutil.parser import parse


def get_calendar(min_time=None, single_events=True, order_by="startTime"):
    """Retrieves JSON response for the Boost Google Calendar.

    Args:
    - min_time: The minimum start time to retrieve the calendar. Default is "now,"
                which means the default behavior is to return only future events.
                ISO format.
    - single_events: True allows us to retrieve recurring events as individual events
    - order_by: The order in which to retrieve and return the events

    See the docs for more information on query params available to this API:
    https://developers.google.com/calendar/api/v3/reference/events/list
    """
    if not min_time:
        min_time = (
            datetime.datetime.utcnow().isoformat() + "Z"
        )  # 'Z' indicates UTC time

    url = f"https://www.googleapis.com/calendar/v3/calendars/{settings.BOOST_CALENDAR}/events?key={settings.CALENDAR_API_KEY}&timeMin={min_time}&singleEvents={single_events}&orderBy={order_by}"

    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def extract_calendar_events(calendar_data, count=50):
    """Take the response from get_calendar() and extract the next N
    events, where N is the count argument.

    Args:
    - calendar_data: The response from the Google Calendar events API
    - count: The number of events to extract
    """
    event_data = calendar_data.get("items")

    if not event_data:
        return []

    # Don't get an IndexError
    if len(event_data) < count:
        events = event_data
    else:
        events = event_data[:count]

    return_data = []

    for event in events:
        start_date = event.get("start")
        start_raw = start_date["date"] if start_date else None
        try:
            start = parse(start_raw)
        except ValueError:
            start = None

        end_date = event.get("end")
        end_raw = end_date["date"] if end_date else None
        try:
            end = parse(end_raw)
        except ValueError:
            end = None

        event_dict = {
            "start": start,
            "end": end,
            "name": event.get("summary"),
            "description": event.get("description"),
        }
        return_data.append(event_dict)

    return return_data


def events_by_month(events):
    """Takes the events returned by extract_calendar_events
    and returns them organized in a dictionary by month and year
    for display purposes.
    """
    events_by_month = defaultdict(list)
    for event in events:
        month_year = event["start"].strftime("%B %Y")
        events_by_month[month_year].append(event)

    return events_by_month
