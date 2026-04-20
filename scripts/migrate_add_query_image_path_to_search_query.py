"""
Migration: Add query_image_path column to search_query table.

This migration persists the uploaded search image path so
GET /api/search/<id> can return the original query image later.

Usage:
    python scripts/migrate_add_query_image_path_to_search_query.py
"""
import os
import sys

from sqlalchemy import inspect, text

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db


def run_migration():
    """Add search_query.query_image_path if it does not already exist."""
    app = create_app()

    with app.app_context():
        try:
            print("Starting migration: Add query_image_path column to search_query...")

            db.create_all()

            inspector = inspect(db.engine)
            columns = {column["name"] for column in inspector.get_columns("search_query")}

            if "query_image_path" in columns:
                print("ℹ️ Column already exists: search_query.query_image_path")
                return

            db.session.execute(
                text("ALTER TABLE search_query ADD COLUMN query_image_path TEXT")
            )
            db.session.commit()

            print("✅ Migration completed successfully!")
            print("")
            print("Added column:")
            print("  - search_query.query_image_path TEXT")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
            raise


def run_manual_sql():
    """Print manual SQL for environments where you prefer direct execution."""
    print("Manual SQL migration:")
    print("")
    print("ALTER TABLE search_query ADD COLUMN query_image_path TEXT;")
    print("")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--sql":
        run_manual_sql()
    else:
        run_migration()
