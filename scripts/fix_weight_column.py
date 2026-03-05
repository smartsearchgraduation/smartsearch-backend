"""Check and fix weight column type in database."""
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from app import create_app
app = create_app()

with app.app_context():
    from models import db
    from sqlalchemy import text, inspect
    
    # Check current column type
    print("="*50)
    print("Checking 'weight' column type in 'retrieve' table")
    print("="*50)
    
    inspector = inspect(db.engine)
    columns = inspector.get_columns('retrieve')
    
    for col in columns:
        if col['name'] == 'weight':
            print(f"\nColumn: {col['name']}")
            print(f"  Type: {col['type']}")
            print(f"  Nullable: {col['nullable']}")
            break
    
    # If it's INTEGER, alter to FLOAT
    print("\n" + "="*50)
    print("Altering column to DOUBLE PRECISION (Float)")
    print("="*50)
    
    try:
        db.session.execute(text("""
            ALTER TABLE retrieve 
            ALTER COLUMN weight TYPE DOUBLE PRECISION 
            USING weight::DOUBLE PRECISION
        """))
        db.session.commit()
        print("\n✅ Column 'weight' successfully changed to DOUBLE PRECISION!")
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Error: {e}")
    
    # Verify the change
    print("\n" + "="*50)
    print("Verifying column type after change")
    print("="*50)
    
    inspector = inspect(db.engine)
    columns = inspector.get_columns('retrieve')
    
    for col in columns:
        if col['name'] == 'weight':
            print(f"\nColumn: {col['name']}")
            print(f"  Type: {col['type']}")
