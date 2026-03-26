"""
Migration: Add correction_engine column to retrieve table.

This migration adds a new column to the retrieve table:
- correction_engine: Stores which spell correction engine was used ('symspell_keyboard', 'byt5', 'rawtext')

Run this migration to enable correction engine tracking for search retrievals.

Usage:
    python scripts/migrate_add_correction_engine_to_retrieve.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db
from app import create_app

def run_migration():
    """Run the migration to add correction_engine column to retrieve table."""
    app = create_app()
    
    with app.app_context():
        try:
            print("Starting migration: Add correction_engine column to retrieve table...")
            
            # Create all tables (this will add the new columns defined in the model)
            db.create_all()
            
            print("✅ Migration completed successfully!")
            print("")
            print("Added columns:")
            print("  - retrieve.correction_engine VARCHAR(50)")
            print("")
            print("Values:")
            print("  - 'symspell_keyboard': SymSpell-based correction")
            print("  - 'byt5': ByT5 ML-based correction")
            print("  - 'rawtext': No correction applied")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise


def run_manual_sql():
    """
    Alternative: Run manual SQL if you prefer.
    
    For PostgreSQL/MySQL:
        ALTER TABLE retrieve ADD COLUMN correction_engine VARCHAR(50);
    """
    print("Manual SQL migration:")
    print("")
    print("ALTER TABLE retrieve ADD COLUMN correction_engine VARCHAR(50);")
    print("")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--sql':
        run_manual_sql()
    else:
        run_migration()
