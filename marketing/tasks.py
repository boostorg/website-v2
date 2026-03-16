from django.core.management import call_command

from config.celery import app


@app.task(soft_time_limit=900, time_limit=960)
def sync_monday_crm():
    call_command("sync_monday_crm")
