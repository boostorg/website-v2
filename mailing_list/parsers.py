from datetime import datetime
from email.utils import parseaddr

import mailbox

from .models import MailingListMessage


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

    # def save(self):
    #     messages = self.parse()
    #     for message in messages:
    #         message_data = self.parse_message(message)
    #         MailingListMessage.objects.create(**message_data)

    def parse_message(self, message):
        """Parse a message and return a dictionary of required fields"""
        sender_display, sender_email = self.extract_sender_parts(message["from"])
        return {
            "sender_email": sender_email,
            "sender_display": sender_display,
            "subject": message["subject"],
            "body": message["body"],
            "sent_at": self.convert_date(message["date"]),
            "message_id": message["message_id"],
            "parent": message["in_reply_to"],
            "data": message,
        }

    def convert_date(self, date_string):
        """Convert a date string into a datetime object"""
        format_string = "%Y-%m-%d %H:%M:%S"
        return datetime.strptime(date_string, format_string)

    def extract_sender_parts(self, email_string):
        """Extract the user display and email address from a string"""
        display, email = parseaddr(email_string)
        return display, email
