"""V3 migration status enum.

This is scaffolding for the V3 redesign migration. Each V3 view declares
its `v3_status` as a class attribute (see core/views.py, news/views.py).

`core/tests/test_v3_registry.py` iterates those views and checks that
declared templates exist and that `V3Mixin` usage matches the status.

When the migration finishes, delete this module, the `v3_status`
attributes on views, and the registry test. See `config/v3_urls.py` for
the full teardown procedure.
"""

from __future__ import annotations

from enum import Enum


class V3Status(Enum):
    """Migration status for a URL route.

    LEGACY_ONLY   — default; no V3 work started.

    V3_OPTIONAL   — legacy template by default, V3 template via waffle flag.
                    The view has both `template_name` (legacy) and
                    `v3_template_name` (V3).

    V3_ONLY       — V3 is the only implementation; no legacy counterpart.
                    Returns 404 when the `v3` flag is off.
    """

    LEGACY_ONLY = "legacy_only"
    V3_OPTIONAL = "v3_optional"
    V3_ONLY = "v3_only"
