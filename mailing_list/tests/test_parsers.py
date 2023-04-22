from datetime import datetime
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
    """ Test that the convert_date function returns a datetime object"""
    date_string = "2023-02-03 17:25:13"
    expected = datetime(2023, 2, 3, 17, 25, 13)
    parser = MailParser("mailing_list/tests/data/test_mbox.mbox")
    result = parser.convert_date(date_string)
    assert result == expected


def test_parse_message():
    """Test that the parse_message function returns a dictionary of required fields"""
    mail_parser = MailParser("mailing_list/tests/data/test_mbox.mbox")
    message = {
        "from": "John Doe <johndoe@example.com>",
        "date": "2023-02-03 17:25:13",
        "subject": "Test Subject",
        "to": "Jane Smith <janesmith@example.com>",
        "message_id": "<unique-id@example.com>",
        "in_reply_to": None,
        "x_thread_depth": None,
        "body": "Test message body",
    }
    
    expected = {
        "sender_email": "John Doe <johndoe@example.com>",
        "subject": "Test Subject",
        "body": "Test message body",
        "sent_at": datetime(2023, 2, 3, 17, 25, 13),
        "message_id": "<unique-id@example.com>",
        "parent": None,
        "data": message,
    }
    result = mail_parser.parse_message(message)
    assert result == expected

