import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from model_bakery import baker

from mailing_list.models import MailingListMessage

subjects = [
    "Re: Master is open for merges",
    "Re: Suggestion for ccmath library",
    "Re: Update on boost::asio",
    "Re: boost::python issue",
    "Re: boost::filesystem question",
    "Re: boost::mpl - New release?",
    "Re: boost::log - Configuration",
]

sender_displays = [
    "Oliver Smith",
    "Sophia Johnson",
    "Liam Williams",
    "Ava Taylor",
    "Noah Davis",
    "Isabella Brown",
    "Lucas Wilson",
]


class Command(BaseCommand):
    help = "Generate realistic-looking test data for MailingListMessage model"

    def handle(self, *args, **options):
        self.stdout.write("Generating test data...")

        for _ in range(5):
            # Create a top-level message
            top_level_message = baker.make(
                MailingListMessage,
                sender=None,
                sender_email=None,
                sender_display=random.choice(sender_displays),
                subject=random.choice(subjects),
                sent_at=timezone.now() - timezone.timedelta(days=random.randint(1, 30)),
            )

            # Create replies for the top-level message
            for _ in range(random.randint(1, 5)):
                baker.make(
                    MailingListMessage,
                    sender=None,
                    sender_email=None,
                    sender_display=random.choice(sender_displays),
                    subject=f"Re: {top_level_message.subject}",
                    parent=top_level_message,
                    sent_at=timezone.now()
                    - timezone.timedelta(days=random.randint(1, 30)),
                )

        self.stdout.write(self.style.SUCCESS("Test data generated successfully!"))
