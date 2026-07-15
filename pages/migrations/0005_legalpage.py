import django.db.models.deletion
import modelcluster.contrib.taggit
import wagtail.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wagtailcore", "0096_referenceindex_referenceindex_source_object_and_more"),
        ("pages", "0004_alter_postpage_content"),
    ]

    operations = [
        migrations.CreateModel(
            name="LegalPage",
            fields=[
                (
                    "page_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="wagtailcore.page",
                    ),
                ),
                ("body", wagtail.fields.RichTextField(blank=True)),
                (
                    "tags",
                    modelcluster.contrib.taggit.ClusterTaggableManager(
                        blank=True,
                        help_text="A comma-separated list of tags.",
                        through="pages.TaggedContent",
                        to="pages.ContentTag",
                        verbose_name="Tags",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("wagtailcore.page",),
        ),
    ]
