"""
Migration script to create search_time table and update retrieve table.
Run this script manually: python migrate_time_refactor.py
"""
import os
import logging
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from app import create_app
from models import db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def migrate():
    """Migrate the database to the new schema."""
    app = create_app()
    
    with app.app_context():
        logger.info("Starting migration...")
        
        # 1. Create search_time table
        logger.info("Creating search_time table...")
        try:
            # We can use SQLAlchemy's create_all, but it checks all tables.
            # To be safe and specific, let's create just the new one if it doesn't exist.
            from models.search_time import SearchTime
            SearchTime.__table__.create(db.engine)
            logger.info("✅ search_time table created successfully.")
        except Exception as e:
            if "already exists" in str(e):
                logger.info("⚠️  search_time table already exists.")
            else:
                logger.error(f"❌ Failed to create search_time table: {e}")
                sys.exit(1)
        
        # 2. Alter retrieve table to drop columns
        logger.info("Altering retrieve table...")
        
        # Helper to drop column if exists
        def drop_column_if_exists(table_name, column_name):
            try:
                # Check if column exists first (PostgreSQL specific usually, but this is a generic attempt)
                # For PostgreSQL:
                check_sql = f"SELECT column_name FROM information_schema.columns WHERE table_name='{table_name}' AND column_name='{column_name}'"
                result = db.session.execute(db.text(check_sql)).fetchone()
                
                if result:
                    logger.info(f"Dropping {column_name} from {table_name}...")
                    db.session.execute(db.text(f"ALTER TABLE {table_name} DROP COLUMN {column_name}"))
                    db.session.commit()
                    logger.info(f"✅ Dropped {column_name}.")
                else:
                    logger.info(f"ℹ️  Column {column_name} does not exist in {table_name}.")
                    
            except Exception as e:
                db.session.rollback()
                logger.warning(f"⚠️  Could not drop {column_name}: {e}")

        drop_column_if_exists('retrieve', 'backend_time')
        drop_column_if_exists('retrieve', 'total_time')
        
        logger.info("Migration complete!")

if __name__ == '__main__':
    migrate()
