from django.db import migrations

CREATE_MATVIEW = """
CREATE MATERIALIZED VIEW users_profile_role_eligibility AS
WITH commit_counts AS (
    SELECT ca.user_id, lv.library_id, COUNT(*) AS commit_count
    FROM libraries_commitauthor ca
    JOIN libraries_commit c ON c.author_id = ca.id
    JOIN libraries_libraryversion lv ON lv.id = c.library_version_id
    WHERE ca.user_id IS NOT NULL
    GROUP BY ca.user_id, lv.library_id
),
library_roles AS (
    SELECT la.user_id, la.library_id, 'Author' AS role
    FROM libraries_library_authors la
    UNION
    SELECT lm.user_id, lv.library_id, 'Maintainer' AS role
    FROM libraries_libraryversion_maintainers lm
    JOIN libraries_libraryversion lv ON lv.id = lm.libraryversion_id
    UNION
    SELECT cc.user_id, cc.library_id, 'Contributor' AS role
    FROM commit_counts cc
)
SELECT
    ROW_NUMBER() OVER (ORDER BY lr.user_id, lr.library_id, lr.role) AS id,
    lr.user_id,
    lr.library_id,
    lr.role,
    COALESCE(cc.commit_count, 0) AS commit_count
FROM library_roles lr
LEFT JOIN commit_counts cc
    ON cc.user_id = lr.user_id AND cc.library_id = lr.library_id;

CREATE UNIQUE INDEX users_profile_role_eligibility_key
    ON users_profile_role_eligibility (user_id, library_id, role);
"""

DROP_MATVIEW = "DROP MATERIALIZED VIEW IF EXISTS users_profile_role_eligibility;"


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0022_profileroleeligibility_user_displayed_profile_role_and_more"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE_MATVIEW, reverse_sql=DROP_MATVIEW),
    ]
