import mailbox


class MailParser:
    """Parse an mbox archive and return a list of messages"""

    def __init__(self, mbox_file):
        self.mbox_file = mbox_file

    def parse(self):
        mbox = mailbox.mbox(self.mbox_file)
        messages = []
        for message in mbox:
            messages.append(message)
        return messages
