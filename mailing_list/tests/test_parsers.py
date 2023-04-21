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
    expected_keys = [
        "from",
        "date",
        "subject",
        "to",
        "message_id",
        "in_reply_to",
        "x_thread_depth",
        "body",
    ]
    assert all(key in messages[0] for key in expected_keys)
