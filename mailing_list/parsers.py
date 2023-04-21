import mailbox


class MailParser:
    """Parse an mbox archive and return a dictionary of required fields"""

    def __init__(self, mbox_file):
        self.mbox_file = mbox_file

    def parse(self):
        mbox = mailbox.mbox(self.mbox_file)
        messages = []
        for message in mbox:
            msg_dict = {
                "from": message.get("From"),
                "date": message["Date"],
                "subject": message["Subject"],
                "to": message["To"],
                "message_id": message["Message-ID"],
                "in_reply_to": message["In-Reply-To"],
                "x_thread_depth": message["X-Thread-Depth"],
                "body": message.get_payload(),
            }
            messages.append(msg_dict)
        return messages
