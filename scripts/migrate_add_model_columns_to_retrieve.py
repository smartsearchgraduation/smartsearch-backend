"""
Migration: Add model tracking columns to retrieve table.

This migration adds two new columns to the retrieve table:
- textual_model_name: Stores which text embedding model was used
- visual_model_name: Stores which visual embedding model was used

Run this migration to enable model tracking for search retrievals.

Usage:
    python scripts/migrate_add_model_columns_to_retrieve.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db
from app import create_app

def run_migration():
    """Run the migration to add model columns to retrieve table."""
    app = create_app()
    
    with app.app_context():
        try:
            print("Starting migration: Add model columns to retrieve table...")
            
            # Create all tables (this will add the new columns defined in the model)
            db.create_all()
            
            print("✅ Migration completed successfully!")
            print("")
            print("Added columns:")
            print("  - retrieve.textual_model_name VARCHAR(100)")
            print("  - retrieve.visual_model_name VARCHAR(100)")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise


def run_manual_sql():
    """
    Alternative: Run manual SQL if you prefer.
    
    For PostgreSQL:
        ALTER TABLE retrieve ADD COLUMN textual_model_name VARCHAR(100);
        ALTER TABLE retrieve ADD COLUMN visual_model_name VARCHAR(100);
    
    For MySQL:
        ALTER TABLE retrieve ADD COLUMN textual_model_name VARCHAR(100);
        ALTER TABLE retrieve ADD COLUMN visual_model_name VARCHAR(100);
    """
    print("Manual SQL migration:")
    print("")
    print("ALTER TABLE retrieve ADD COLUMN textual_model_name VARCHAR(100);")
    print("ALTER TABLE retrieve ADD COLUMN visual_model_name VARCHAR(100);")
    print("")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--sql':
        run_manual_sql()
    else:
        run_migration()
