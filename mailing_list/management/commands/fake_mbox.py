from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
import mailbox
import random

from faker import Faker


class Command(BaseCommand):
    help = "Generate realistic-looking mbox file with fake messages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--num-messages",
            type=int,
            default=100,
            help="Number of messages to generate",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="mailing_list/tests/data/test_mbox.mbox",
            help="Output mbox file",
        )

    def handle(self, *args, **options):
        num_messages = options["num_messages"]
        mbox_file = options["output"]

        fake = Faker()
        mbox = mailbox.mbox(mbox_file)

        # Helper function to generate message content
        def generate_message_content():
            paragraphs = fake.paragraphs(nb=random.randint(1, 4))
            return "\n\n".join(paragraphs)

        message_parents = [None] * 3

        for i in range(num_messages):
            message = mailbox.mboxMessage()

            sender_name = fake.name()
            sender_email = f"{fake.user_name()}@example.com"
            message.set_from(f"{sender_name} ({sender_email})")

            date = datetime.now() - timedelta(days=random.randint(0, 365))
            message["Date"] = date.strftime("%Y-%m-%d %H:%M:%S")

            message["Subject"] = f"{fake.catch_phrase()} discussion"
            message["To"] = f"{fake.name()} <{fake.user_name()}@example.com>"

            content = generate_message_content()
            message.set_payload(content)

            # Add threading
            if i > 0:
                thread_level = random.choices(range(3), [0.5, 0.3, 0.2])[0]
                parent_message = message_parents[thread_level]

                if parent_message:
                    parent_message_id = parent_message["Message-ID"]
                    message["In-Reply-To"] = parent_message_id
                    message["References"] = parent_message_id

            mbox.add(message)

            # Update message_parents list
            message_parents.pop(0)
            message_parents.append(message)

        mbox.flush()
        mbox.close()

        self.stdout.write(
            self.style.SUCCESS(f"Generated {num_messages} messages in {mbox_file}")
        )
