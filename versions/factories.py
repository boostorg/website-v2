import factory

from .models import Version


class VersionFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: "version%s" % n)
    file = factory.Faker("file_name")
    release_date = factory.Faker("date_object")

    class Meta:
        model = Version
