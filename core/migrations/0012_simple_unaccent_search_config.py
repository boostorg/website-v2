from django.db import migrations

# The autocomplete vector uses `simple` to avoid stemming a partial word down to
# something it is no longer a prefix of. `simple` does not fold diacritics
# either, which left "Lope" unable to reach "López" while "Lópe" could.
CREATE = """
CREATE TEXT SEARCH CONFIGURATION simple_unaccent ( COPY = simple );
ALTER TEXT SEARCH CONFIGURATION simple_unaccent
  ALTER MAPPING FOR hword, hword_part, word WITH unaccent, simple;
"""

DROP = "DROP TEXT SEARCH CONFIGURATION IF EXISTS simple_unaccent;"


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_english_unaccent_search_config"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE, reverse_sql=DROP),
    ]
