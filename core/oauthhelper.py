from django.conf import settings

from oauth2_provider.models import Application


def get_oauth_client():
    try:
        return Application.objects.get(name=settings.OAUTH_APP_NAME)
    except Application.DoesNotExist:
        return
