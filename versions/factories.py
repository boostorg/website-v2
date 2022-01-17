import factory
from factory import fuzzy

from .models import Version, VersionFile


class VersionFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: "version%s" % n)
    release_date = factory.Faker("date_object")

    class Meta:
        model = Version

    @factory.post_generation
    def files(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            # A list of files were passed in, use them
            for file in extracted:
                self.files.add(file)


class VersionFileFactory(factory.django.DjangoModelFactory):
    file = factory.Faker("file_name")
    operating_system = fuzzy.FuzzyChoice(
        VersionFile.OPERATING_SYSTEM_CHOICES, getter=lambda c: c[0]
    )

    class Meta:
        model = VersionFile
