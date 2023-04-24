import pytz
from datetime import datetime

from mailing_list.models import MailingListMessage
from mailing_list.parsers import MailParser


def test_parse():
    """
    Test that the parser returns a list of messages.
    If you update the test_mbox.mbox file, you may need to update the expected number of messages.
    """
    mbox_file = "mailing_list/tests/data/test_mbox.mbox"

    parser = MailParser(mbox_file)
    messages = parser.parse()
    assert len(messages) == 100

    # Check the keys of the first message in the list
    expected = [
        "from",
        "date",
        "subject",
        "to",
        "message_id",
        "in_reply_to",
        "x_thread_depth",
        "body",
    ]
    assert all(key in messages[0] for key in expected)


def test_convert_date():
    """Test that the convert_date function returns a datetime object"""
    date_string = "2023-02-03 17:25:13"
    expected = datetime(2023, 2, 3, 17, 25, 13)
    parser = MailParser("mailing_list/tests/data/test_mbox.mbox")
    result = parser.convert_date(date_string)
    assert result == expected


def test_extract_sender_parts():
    parser = MailParser("mailing_list/tests/data/test_mbox.mbox")
    email_string = "Taylor Swift <tswift@example.com>"
    expected_sender_display = "Taylor Swift"
    expected_sender_email = "tswift@example.com"
    sender_display, sender_email = parser.extract_sender_parts(email_string)
    assert sender_display == expected_sender_display
    assert sender_email == expected_sender_email


def test_parse_message():
    """Test that the parse_message function returns a dictionary of required fields"""
    mail_parser = MailParser("mailing_list/tests/data/test_mbox.mbox")
    message = {
        "from": "Taylor Swift <tswift@example.com>",
        "date": "2023-02-03 17:25:13",
        "subject": "Test Subject",
        "to": "Jane Smith <janesmith@example.com>",
        "message_id": "<unique-id@example.com>",
        "in_reply_to": None,
        "x_thread_depth": None,
        "body": "Test message body",
    }

    expected = {
        "sender_email": "tswift@example.com",
        "sender_display": "Taylor Swift",
        "subject": "Test Subject",
        "body": "Test message body",
        "sent_at": datetime(2023, 2, 3, 17, 25, 13),
        "message_id": "<unique-id@example.com>",
        "parent": None,
        "data": message,
    }
    result = mail_parser.parse_message(message)
    assert result == expected


def test_save_messages(db):
    """Test that the save_messages function saves messages to the database"""
    message_id = "<a5697ca2-9ea8-4585-94e3-5a1c98cff39d@example.com>"
    count = MailingListMessage.objects.count()
    assert MailingListMessage.objects.filter(message_id=message_id).exists() is False
    parser = MailParser("mailing_list/tests/data/test_single_mbox.mbox")
    parser.save_messages()
    assert MailingListMessage.objects.count() == count + 1
    assert MailingListMessage.objects.filter(message_id=message_id).exists() is True
    obj = MailingListMessage.objects.get(message_id=message_id)
    assert obj.subject is not None
    assert obj.body is not None
