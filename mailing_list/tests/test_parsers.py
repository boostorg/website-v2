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
