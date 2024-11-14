from django.core.management import call_command

from config.celery import app


@app.task
def fetch_slack_activity():
    call_command("fetch_slack_activity")
