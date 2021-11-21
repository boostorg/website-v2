import factory

import django.contrib.auth.models as auth_models
from django.utils import timezone

from .models import User

class VersionGroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = auth_models.Group

    name = 'version_manager'


class UserFactory(factory.django.DjangoModelFactory):
    email = factory.Sequence(lambda n: "user%s@example.com" % n)
    first_name = factory.Sequence(lambda n: "User%s Bob" % n)
    last_name = factory.Sequence(lambda n: "User%s Smith" % n)

    last_login = factory.LazyFunction(timezone.now)

    password = factory.PostGenerationMethodCall("set_password", "password")

    class Meta:
        model = User
        django_get_or_create = ("email",)
    
    @factory.post_generation
    def groups(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for group in extracted:
                self.groups.add(group)


class StaffUserFactory(UserFactory):
    is_staff = True


class SuperUserFactory(StaffUserFactory):
    is_superuser = True
