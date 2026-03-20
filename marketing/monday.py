import json
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

MONDAY_API_URL = "https://api.monday.com/v2"

# Monday.com column ID mappings — these are structural constants tied to the
# board schemas, not secrets. Update these if the board columns change.
CONTACTS_COLUMNS = {
    "email": "contact_email",
    "github_username": "text_mm14zw93",
    "date_joined": "date_mm1495ng",
    "last_login": "date_mm147ks8",
}

LEADS_COLUMNS = {
    "email": "lead_email",
    "company": "lead_company",
    "title": "text",
    "first_name": "text_mm14gktd",
    "last_name": "text_mm14cqj4",
    "github_username": "text_mm1dvdrt",
    "city": "text_mm14v5h5",
    "state": "text_mm14p6vv",
    "country": "text_mm14jjtj",
    "referrer": "text_mm14ebdc",
    "page": "text_mm1e9bx7",
    "captured_at": "date_mm14hcxb",
}


class MondayAPIError(Exception):
    """Raised when the Monday.com API returns an error response."""


class MondayRateLimitError(MondayAPIError):
    """Raised when the Monday.com API returns a 429 rate limit response."""

    def __init__(self, retry_after=30):
        self.retry_after = retry_after
        super().__init__(f"Rate limited, retry after {retry_after}s")


class MondayClient:
    """
    Minimal Monday.com GraphQL client for one-way CRM push.

    Required settings:
        MONDAY_API_TOKEN          - personal API token
        MONDAY_CONTACTS_BOARD_ID  - board ID for the Contacts board
        MONDAY_LEADS_BOARD_ID     - board ID for the Leads board
    """

    def __init__(self, token=None):
        self.token = token or settings.MONDAY_API_TOKEN
        if not self.token:
            raise ValueError(
                "No Monday.com API token provided or found in MONDAY_API_TOKEN setting."
            )
        for attr in ("MONDAY_CONTACTS_BOARD_ID", "MONDAY_LEADS_BOARD_ID"):
            if not getattr(settings, attr, None):
                raise ValueError(f"{attr} is not configured.")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": self.token,
                "Content-Type": "application/json",
            }
        )

    # ------------------------------------------------------------------
    # Low-level GraphQL
    # ------------------------------------------------------------------

    def _query(self, query, variables=None):
        """Execute a GraphQL query/mutation. Raises on HTTP or API errors."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = self.session.post(MONDAY_API_URL, json=payload)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 30))
            raise MondayRateLimitError(retry_after)
        response.raise_for_status()

        data = response.json()
        if "errors" in data:
            raise MondayAPIError(f"Monday.com API error: {data['errors']}")
        return data["data"]

    def _query_with_retry(self, query, variables=None, max_retries=3):
        """Execute a GraphQL query with exponential backoff retry.

        Non-transient errors (MondayAPIError) are raised immediately.
        Only transient errors (network, HTTP 5xx) are retried.
        """
        for attempt in range(1, max_retries + 1):
            try:
                return self._query(query, variables)
            except MondayRateLimitError as e:
                if attempt == max_retries:
                    raise
                logger.warning(
                    "Monday.com rate limited, waiting %ds (attempt %d/%d)",
                    e.retry_after,
                    attempt,
                    max_retries,
                )
                time.sleep(e.retry_after)
            except MondayAPIError:
                raise
            except requests.RequestException:
                if attempt == max_retries:
                    raise
                wait = 2**attempt
                logger.warning(
                    "Monday.com API retry attempt=%d, waiting %ds", attempt, wait
                )
                time.sleep(wait)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def find_item_by_email(self, board_id, email_column_id, email):
        """
        Search a board for an item matching the given email.
        Returns the item ID string if found, else None.
        """
        query = """
        query ($board_id: ID!, $column_id: String!, $value: String!) {
            items_page_by_column_values(
                limit: 1
                board_id: $board_id
                columns: [{column_id: $column_id, column_values: [$value]}]
            ) {
                items { id }
            }
        }
        """
        variables = {
            "board_id": str(board_id),
            "column_id": email_column_id,
            "value": email,
        }
        data = self._query_with_retry(query, variables)
        items = data.get("items_page_by_column_values", {}).get("items", [])
        return items[0]["id"] if items else None

    def get_all_emails(self, board_id, email_column_id):
        """Fetch all items from a board, returning {email: item_id}."""
        lookup = {}
        cursor = None
        while True:
            if cursor:
                query = """
                query ($cursor: String!, $col_ids: [String!]) {
                    next_items_page(limit: 500, cursor: $cursor) {
                        cursor
                        items { id column_values(ids: $col_ids) { text } }
                    }
                }
                """
                variables = {"cursor": cursor, "col_ids": [email_column_id]}
                data = self._query_with_retry(query, variables)
                page = data["next_items_page"]
            else:
                query = """
                query ($board_id: ID!, $col_ids: [String!]) {
                    boards(ids: [$board_id]) {
                        items_page(limit: 500) {
                            cursor
                            items { id column_values(ids: $col_ids) { text } }
                        }
                    }
                }
                """
                variables = {
                    "board_id": str(board_id),
                    "col_ids": [email_column_id],
                }
                data = self._query_with_retry(query, variables)
                page = data["boards"][0]["items_page"]

            for item in page["items"]:
                email = (item["column_values"][0]["text"] or "").strip()
                if email:
                    lookup[email] = item["id"]

            cursor = page["cursor"]
            if not cursor:
                break
        return lookup

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    BATCH_SIZE = 25

    def create_item(self, board_id, item_name, column_values):
        """Create a new item on a board. Returns the new item ID."""
        mutation = """
        mutation ($board_id: ID!, $item_name: String!, $column_values: JSON!) {
            create_item(
                board_id: $board_id
                item_name: $item_name
                column_values: $column_values
            ) { id }
        }
        """
        variables = {
            "board_id": str(board_id),
            "item_name": item_name,
            "column_values": json.dumps(column_values),
        }
        data = self._query_with_retry(mutation, variables)
        return data["create_item"]["id"]

    def create_items_batch(self, board_id, items):
        """Create multiple items in one API call using aliased mutations.

        items: list of (item_name, column_values) tuples.
        Returns list of created item IDs.
        """
        if not items:
            return []
        parts = []
        variables = {"board_id": str(board_id)}
        for i, (name, col_vals) in enumerate(items):
            parts.append(
                f"i{i}: create_item(board_id: $board_id, "
                f"item_name: $name_{i}, column_values: $cols_{i}) {{ id }}"
            )
            variables[f"name_{i}"] = name
            variables[f"cols_{i}"] = json.dumps(col_vals)

        type_decls = ["$board_id: ID!"]
        for i in range(len(items)):
            type_decls.append(f"$name_{i}: String!")
            type_decls.append(f"$cols_{i}: JSON!")

        mutation = "mutation (%s) { %s }" % (
            ", ".join(type_decls),
            " ".join(parts),
        )
        data = self._query_with_retry(mutation, variables)
        return [data[f"i{i}"]["id"] for i in range(len(items))]

    def update_items_batch(self, board_id, items):
        """Update multiple items in one API call using aliased mutations.

        items: list of (item_id, column_values) tuples.
        Returns list of updated item IDs.
        """
        if not items:
            return []
        parts = []
        variables = {"board_id": str(board_id)}
        for i, (item_id, col_vals) in enumerate(items):
            parts.append(
                f"i{i}: change_multiple_column_values(board_id: $board_id, "
                f"item_id: $id_{i}, column_values: $cols_{i}) {{ id }}"
            )
            variables[f"id_{i}"] = str(item_id)
            variables[f"cols_{i}"] = json.dumps(col_vals)

        type_decls = ["$board_id: ID!"]
        for i in range(len(items)):
            type_decls.append(f"$id_{i}: ID!")
            type_decls.append(f"$cols_{i}: JSON!")

        mutation = "mutation (%s) { %s }" % (
            ", ".join(type_decls),
            " ".join(parts),
        )
        data = self._query_with_retry(mutation, variables)
        return [data[f"i{i}"]["id"] for i in range(len(items))]

    def update_item(self, board_id, item_id, column_values):
        """Update column values on an existing item. Returns item ID."""
        mutation = """
        mutation ($board_id: ID!, $item_id: ID!, $column_values: JSON!) {
            change_multiple_column_values(
                board_id: $board_id
                item_id: $item_id
                column_values: $column_values
            ) { id }
        }
        """
        variables = {
            "board_id": str(board_id),
            "item_id": str(item_id),
            "column_values": json.dumps(column_values),
        }
        data = self._query_with_retry(mutation, variables)
        return data["change_multiple_column_values"]["id"]

    # ------------------------------------------------------------------
    # Upsert (composed from search + create/update)
    # ------------------------------------------------------------------

    def _format_date(self, dt):
        """Format a datetime for Monday.com date columns (YYYY-MM-DD)."""
        if dt is None:
            return None
        return dt.strftime("%Y-%m-%d")

    def _contact_row(self, user):
        """Build (item_name, column_values) for a User."""
        email_col = CONTACTS_COLUMNS["email"]
        name = (user.display_name or "").strip() or user.email.split("@")[0]
        column_values = {
            email_col: {"email": user.email, "text": user.email},
        }
        if user.github_username:
            column_values[CONTACTS_COLUMNS["github_username"]] = user.github_username
        if user.date_joined:
            column_values[CONTACTS_COLUMNS["date_joined"]] = self._format_date(
                user.date_joined
            )
        if user.last_login:
            column_values[CONTACTS_COLUMNS["last_login"]] = self._format_date(
                user.last_login
            )
        return name, column_values

    def _lead_row(self, captured_email):
        """Build (item_name, column_values) for a CapturedEmail."""
        email_col = LEADS_COLUMNS["email"]
        column_values = {
            email_col: {"email": captured_email.email, "text": captured_email.email},
        }
        for field, key in [
            ("company", "company"),
            ("title", "title"),
            ("first_name", "first_name"),
            ("last_name", "last_name"),
            ("github_username", "github_username"),
            ("address_city", "city"),
            ("address_state", "state"),
            ("address_country", "country"),
            ("referrer", "referrer"),
        ]:
            value = getattr(captured_email, field, "")
            if value:
                column_values[LEADS_COLUMNS[key]] = value
        if captured_email.page:
            column_values[LEADS_COLUMNS["page"]] = captured_email.page.title
        if captured_email.created_at:
            column_values[LEADS_COLUMNS["captured_at"]] = self._format_date(
                captured_email.created_at
            )
        return captured_email.email, column_values

    def upsert_contact(self, user):
        """
        Upsert a User instance into the Contacts board.
        Returns (item_id, "created" | "updated").
        """
        board_id = settings.MONDAY_CONTACTS_BOARD_ID
        email_col = CONTACTS_COLUMNS["email"]
        name, column_values = self._contact_row(user)

        item_id = self.find_item_by_email(board_id, email_col, user.email)
        if item_id:
            self.update_item(board_id, item_id, column_values)
            return item_id, "updated"
        else:
            item_id = self.create_item(board_id, name, column_values)
            return item_id, "created"

    def upsert_lead(self, captured_email):
        """
        Upsert a CapturedEmail instance into the Leads board.
        Returns (item_id, "created" | "updated").
        """
        board_id = settings.MONDAY_LEADS_BOARD_ID
        email_col = LEADS_COLUMNS["email"]
        name, column_values = self._lead_row(captured_email)

        item_id = self.find_item_by_email(board_id, email_col, captured_email.email)
        if item_id:
            self.update_item(board_id, item_id, column_values)
            return item_id, "updated"
        else:
            item_id = self.create_item(board_id, name, column_values)
            return item_id, "created"

    def _commit_batch(self, board_id, create_buf, update_buf, counters):
        """Commit create/update buffers when they reach BATCH_SIZE."""
        if len(create_buf) >= self.BATCH_SIZE:
            self.create_items_batch(board_id, create_buf)
            counters[0] += len(create_buf)
            create_buf.clear()
        if len(update_buf) >= self.BATCH_SIZE:
            self.update_items_batch(board_id, update_buf)
            counters[1] += len(update_buf)
            update_buf.clear()

    def bulk_upsert_contacts(self, users):
        """Bulk upsert Users into the Contacts board. Returns (created, updated)."""
        board_id = settings.MONDAY_CONTACTS_BOARD_ID
        email_col = CONTACTS_COLUMNS["email"]
        existing = self.get_all_emails(board_id, email_col)

        create_buf, update_buf = [], []
        counters = [0, 0]  # [created, updated]
        for user in users.iterator():
            name, col_vals = self._contact_row(user)
            item_id = existing.get(user.email)
            if item_id:
                update_buf.append((item_id, col_vals))
            else:
                create_buf.append((name, col_vals))
            self._commit_batch(board_id, create_buf, update_buf, counters)

        # Flush remaining
        if create_buf:
            self.create_items_batch(board_id, create_buf)
            counters[0] += len(create_buf)
        if update_buf:
            self.update_items_batch(board_id, update_buf)
            counters[1] += len(update_buf)

        return counters[0], counters[1]

    def bulk_upsert_leads(self, leads):
        """Bulk upsert CapturedEmails into the Leads board. Returns (created, updated)."""
        board_id = settings.MONDAY_LEADS_BOARD_ID
        email_col = LEADS_COLUMNS["email"]
        existing = self.get_all_emails(board_id, email_col)

        create_buf, update_buf = [], []
        counters = [0, 0]  # [created, updated]
        for lead in leads.iterator():
            name, col_vals = self._lead_row(lead)
            item_id = existing.get(lead.email)
            if item_id:
                update_buf.append((item_id, col_vals))
            else:
                create_buf.append((name, col_vals))
            self._commit_batch(board_id, create_buf, update_buf, counters)

        # Flush remaining
        if create_buf:
            self.create_items_batch(board_id, create_buf)
            counters[0] += len(create_buf)
        if update_buf:
            self.update_items_batch(board_id, update_buf)
            counters[1] += len(update_buf)

        return counters[0], counters[1]
