from django.core.management import call_command

from config.celery import app


@app.task
def sync_monday_crm():
    call_command("sync_monday_crm")
