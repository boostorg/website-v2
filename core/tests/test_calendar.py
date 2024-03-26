from datetime import datetime
from dateutil.parser import parse
from ..calendar import extract_calendar_events, events_by_month


def test_extract_calendar_events():
    mock_calendar_data = {
        "items": [
            {
                "start": {"date": "2024-02-21"},
                "end": {"date": "2024-02-22"},
                "summary": "Event 1",
                "description": "Description 1",
            },
            {
                "start": {"date": "2024-02-28"},
                "end": {"date": "2024-03-01"},
                "summary": "Event 2",
                "description": "Description 2",
            },
        ]
    }

    expected_output = [
        {
            "start": parse("2024-02-21"),
            "end": parse("2024-02-22"),
            "name": "Event 1",
            "description": "Description 1",
        },
        {
            "start": parse("2024-02-28"),
            "end": parse("2024-03-01"),
            "name": "Event 2",
            "description": "Description 2",
        },
    ]
    assert extract_calendar_events(mock_calendar_data, count=2) == expected_output


def test_extract_calendar_events_empty_data():
    # Test for empty calendar data
    result = extract_calendar_events({"items": []})
    assert result == []


def test_extract_calendar_events_less_than_count():
    # Test for the case where the number of events is less than the requested count
    mock_calendar_data = {
        "items": [
            {
                "start": {"date": "2024-02-21"},
                "end": {"date": "2024-02-22"},
                "summary": "Event 1",
                "description": "Description 1",
            }
        ]
    }
    expected_output = [
        {
            "start": parse("2024-02-21"),
            "end": parse("2024-02-22"),
            "name": "Event 1",
            "description": "Description 1",
        }
    ]
    assert extract_calendar_events(mock_calendar_data, count=2) == expected_output


def test_events_by_month():
    input_events = [
        {
            "start": datetime(2024, 2, 21),
            "end": datetime(2024, 2, 22),
            "name": "Event1",
            "description": "Desc1",
        },
        {
            "start": datetime(2024, 3, 1),
            "end": datetime(2024, 3, 2),
            "name": "Event2",
            "description": "Desc2",
        },
    ]

    expected = {
        "February 2024": [
            {
                "start": datetime(2024, 2, 21),
                "end": datetime(2024, 2, 22),
                "name": "Event1",
                "description": "Desc1",
            }
        ],
        "March 2024": [
            {
                "start": datetime(2024, 3, 1),
                "end": datetime(2024, 3, 2),
                "name": "Event2",
                "description": "Desc2",
            }
        ],
    }
    assert events_by_month(input_events) == expected


def test_events_by_month_no_events():
    input_events = []

    expected = {}
    assert events_by_month(input_events) == expected
