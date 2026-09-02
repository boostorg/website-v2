from django.db import migrations

# `english` with `unaccent` ahead of the stemmer, so "Perez" and "Pérez" reduce
# to the same lexeme. `unaccent` is a filtering dictionary, so scripts it cannot
# fold pass through untouched.
CREATE = """
CREATE TEXT SEARCH CONFIGURATION english_unaccent ( COPY = english );
ALTER TEXT SEARCH CONFIGURATION english_unaccent
  ALTER MAPPING FOR hword, hword_part, word WITH unaccent, english_stem;
"""

DROP = "DROP TEXT SEARCH CONFIGURATION IF EXISTS english_unaccent;"


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_wysiwygimage"),
        # Installs the `unaccent` extension the configuration below maps to.
        ("versions", "0012_review_reviewresult"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE, reverse_sql=DROP),
    ]
