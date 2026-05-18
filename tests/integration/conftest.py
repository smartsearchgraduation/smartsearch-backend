"""
Integration test conftest - re-exports the session-scoped `app`, `client`, and
`db_session` fixtures from the parent `tests/conftest.py` so that integration
tests can use them without duplicating fixture setup.
"""
import os
import sys

import pytest

# Make sure the parent `tests` directory is importable, then re-export fixtures.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from conftest import app, client, db_session  # noqa: F401,E402


# ---------------------------------------------------------------------------
# SQLite UDF registration for ARRAY_AGG / ARRAY_REMOVE
# ---------------------------------------------------------------------------
# The production query in services/search_service.py uses Postgres-only
# ARRAY_AGG and ARRAY_REMOVE aggregates/functions. The integration tests run
# against an in-memory SQLite DB, so we register equivalent Python UDFs at
# connection time. This unblocks PERF-BE-013 (and any other test that exercises
# the cached search-result query path).
import json as _json
import sqlalchemy as _sa
from sqlalchemy import event as _event


class _ArrayAgg:
    """SQLite aggregate emulating Postgres ARRAY_AGG. Returns a JSON string array."""
    def __init__(self):
        self._items = []

    def step(self, value):
        self._items.append(value)

    def finalize(self):
        # Production code calls .images on the result - it expects a Python list
        # OR a JSON string the consumer json.loads. To survive both code paths
        # we emit a JSON-encoded array; the SQL also wraps us in ARRAY_REMOVE
        # below, which can JSON-decode and re-encode.
        return _json.dumps(self._items)


def _array_remove(arr_json, target):
    """SQLite scalar emulating Postgres ARRAY_REMOVE(arr, target)."""
    if arr_json is None:
        return _json.dumps([])
    try:
        items = _json.loads(arr_json)
    except (ValueError, TypeError):
        return arr_json
    return _json.dumps([x for x in items if x != target])


@_event.listens_for(_sa.engine.Engine, "connect")
def _register_sqlite_aggregates(dbapi_connection, _connection_record):
    # Only attach for sqlite - other dialects already have ARRAY_AGG.
    if "sqlite3" in dbapi_connection.__class__.__module__:
        dbapi_connection.create_aggregate("ARRAY_AGG", 1, _ArrayAgg)
        dbapi_connection.create_function("ARRAY_REMOVE", 2, _array_remove)


@pytest.fixture(autouse=True)
def _raise_request_size_limits(app):  # noqa: F811
    """
    Ensure integration tests can submit large payloads (e.g. base64-encoded
    images up to a few hundred KB). Werkzeug 3.x introduced a default
    MAX_FORM_MEMORY_SIZE of ~500 KB which causes 413 errors for tests that
    POST JSON bodies above that threshold. Production deployments configure
    these limits via WSGI/server config; the test app fixture must do the
    same to honor the test specs.
    """
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
    # MAX_FORM_MEMORY_SIZE may not be a recognized Flask config key on older
    # Werkzeug versions; setting an unknown key on app.config is a harmless
    # no-op, so we set it unconditionally.
    app.config["MAX_FORM_MEMORY_SIZE"] = 32 * 1024 * 1024
    yield
