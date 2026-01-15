import os
import sys
from sqlalchemy import inspect, text

# Add current directory to path
sys.path.append(os.getcwd())

from app import create_app
from models import db

def check_database():
    print("Initializing application context...")
    try:
        app = create_app()
    except Exception as e:
        print(f"Failed to create app: {e}")
        return

    with app.app_context():
        # Try connecting
        print(f"Connecting to database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        try:
            engine = db.engine
            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                print(f"Successfully connected to database.")
        except Exception as e:
            print(f"Failed to connect to database: {e}")
            print("Please ensure PostgreSQL is running and credentials in config.py are correct.")
            return

        print("\nInspecting database schema...")
        try:
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
        except Exception as e:
            print(f"Failed to inspect database: {e}")
            return
        
        print(f"Found tables in DB: {existing_tables}")
        
        model_tables = db.metadata.tables
        all_good = True
        
        print("\nComparing Models <-> Database:")
        
        for table_name, table in model_tables.items():
            if table_name in existing_tables:
                print(f"[OK] Table '{table_name}' exists.")
                
                # Check columns
                try:
                    existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
                    model_columns = {col.name for col in table.columns}
                    
                    missing_columns = model_columns - existing_columns
                    if missing_columns:
                        print(f"    [WARNING] Missing columns in DB table '{table_name}': {missing_columns}")
                        all_good = False
                    
                    extra_columns = existing_columns - model_columns
                    if extra_columns:
                        print(f"    [INFO] Extra columns in DB table '{table_name}': {extra_columns}")
                except Exception as e:
                    print(f"    [ERROR] Failed to inspect columns for '{table_name}': {e}")
                    all_good = False
                    
            else:
                print(f"[MISSING] Table '{table_name}' does not exist in the database.")
                all_good = False

        if all_good:
            print("\nSUCCESS: Database is fully compatible with the models!")
        else:
            print("\nWARNING: Database schema has discrepancies.")

if __name__ == "__main__":
    check_database()
