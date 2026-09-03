"""Postgres search backend that unaccents the autocomplete vector too.

The stock backend assigns `simple` in its own `__init__` rather than reading it
from settings, so subclassing is the only seam.
"""

from modelsearch.backends.database.postgres.postgres import PostgresSearchBackend


class UnaccentedPostgresSearchBackend(PostgresSearchBackend):
    def __init__(self, params):
        super().__init__(params)
        self.autocomplete_config = params.get(
            "AUTOCOMPLETE_SEARCH_CONFIG", "simple_unaccent"
        )


SearchBackend = UnaccentedPostgresSearchBackend
