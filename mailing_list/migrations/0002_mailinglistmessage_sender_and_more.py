# Generated by Django 4.2 on 2023-04-20 22:05

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import mptt.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("mailing_list", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="mailinglistmessage",
            name="sender",
            field=models.ForeignKey(
                blank=True,
                help_text="The registered user who sent the message.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="mailinglistmessage",
            name="sender_display",
            field=models.CharField(
                blank=True,
                help_text="The display name of the sender.",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="mailinglistmessage",
            name="sender_email",
            field=models.EmailField(
                blank=True,
                help_text="The email address of the sender.",
                max_length=254,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="mailinglistmessage",
            name="sent_at",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                help_text="The date and time when the message was sent.",
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="mailinglistmessage",
            name="body",
            field=models.TextField(help_text="The body of the message."),
        ),
        migrations.AlterField(
            model_name="mailinglistmessage",
            name="parent",
            field=mptt.fields.TreeForeignKey(
                blank=True,
                help_text="The parent message to which this message is a reply.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="replies",
                to="mailing_list.mailinglistmessage",
            ),
        ),
        migrations.AlterField(
            model_name="mailinglistmessage",
            name="subject",
            field=models.CharField(
                help_text="The subject of the message.", max_length=255
            ),
        ),
    ]
