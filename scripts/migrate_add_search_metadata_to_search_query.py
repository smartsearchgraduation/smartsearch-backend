"""
Migration: Add search metadata columns to search_query table.

This persists the frontend search mode and whether correction was enabled so
GET /api/search/<id> can return those values alongside the base64 query image.

Usage:
    python scripts/migrate_add_search_metadata_to_search_query.py
"""
import os
import sys

from sqlalchemy import inspect, text

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db


def run_migration():
    """Add search_query.search_mode and correction_enabled if missing."""
    app = create_app()

    with app.app_context():
        try:
            print("Starting migration: Add search metadata columns to search_query...")

            db.create_all()

            inspector = inspect(db.engine)
            columns = {column["name"] for column in inspector.get_columns("search_query")}

            added_columns = []

            if "search_mode" not in columns:
                db.session.execute(
                    text("ALTER TABLE search_query ADD COLUMN search_mode VARCHAR(10)")
                )
                db.session.execute(
                    text("UPDATE search_query SET search_mode = 'std' WHERE search_mode IS NULL")
                )
                added_columns.append("search_query.search_mode VARCHAR(10)")
            else:
                print("Column already exists: search_query.search_mode")

            if "correction_enabled" not in columns:
                db.session.execute(
                    text("ALTER TABLE search_query ADD COLUMN correction_enabled BOOLEAN")
                )
                db.session.execute(
                    text(
                        "UPDATE search_query "
                        "SET correction_enabled = TRUE "
                        "WHERE correction_enabled IS NULL"
                    )
                )
                added_columns.append("search_query.correction_enabled BOOLEAN")
            else:
                print("Column already exists: search_query.correction_enabled")

            db.session.commit()

            if added_columns:
                print("Migration completed successfully!")
                print("")
                print("Added columns:")
                for column in added_columns:
                    print(f"  - {column}")
            else:
                print("No changes needed.")

        except Exception as e:
            db.session.rollback()
            print(f"Migration failed: {e}")
            raise


def run_manual_sql():
    """Print manual SQL for environments where you prefer direct execution."""
    print("Manual SQL migration:")
    print("")
    print("ALTER TABLE search_query ADD COLUMN search_mode VARCHAR(10);")
    print("UPDATE search_query SET search_mode = 'std' WHERE search_mode IS NULL;")
    print("ALTER TABLE search_query ADD COLUMN correction_enabled BOOLEAN;")
    print(
        "UPDATE search_query SET correction_enabled = TRUE "
        "WHERE correction_enabled IS NULL;"
    )
    print("")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--sql":
        run_manual_sql()
    else:
        run_migration()
