from django.core.management import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    help = "Convenience command to test saving a photo from a GH profile"

    def handle(self, *args, **options):
        """A functional test.

        Having trouble getting the patch to work for the underlying function. Replace
        "testing" with your username and run `./manage.py photos_test`, then you will
        see your photo in the admin for whoever your first user is.
        """
        user = User.objects.first()
        user.image = None
        user.github_username = "testing"
        user.save()
        user.refresh_from_db()
        assert bool(user.image) is False
        user.save_image_from_github()
        user.refresh_from_db()
        assert bool(user.image) is True
