"""
Integration test conftest - re-exports the session-scoped `app`, `client`, and
`db_session` fixtures from the parent `tests/conftest.py` so that integration
tests can use them without duplicating fixture setup.
"""
import os
import sys

# Make sure the parent `tests` directory is importable, then re-export fixtures.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from conftest import app, client, db_session  # noqa: F401,E402
