from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
import mailbox
import random
import uuid

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
            "--output", type=str, default="test_mbox.mbox", help="Output mbox file"
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

        parent_messages = []

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

            message_id = f"<{uuid.uuid4()}@example.com>"
            message["Message-ID"] = message_id

            # Add threading
            if parent_messages and random.random() < 0.6:
                max_thread_depth = 3
                parent_message = random.choice(parent_messages)
                parent_depth = int(parent_message.get("X-Thread-Depth", 1))

                if parent_depth < max_thread_depth:
                    message["In-Reply-To"] = parent_message["Message-ID"]
                    message["X-Thread-Depth"] = str(parent_depth + 1)

            mbox.add(message)
            parent_messages.append(message)

        mbox.flush()
        mbox.close()

        self.stdout.write(
            self.style.SUCCESS(f"Generated {num_messages} messages in {mbox_file}")
        )
