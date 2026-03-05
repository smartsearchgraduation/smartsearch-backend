"""Debug script to perform a new search and check weights."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from app import create_app
app = create_app()

with app.app_context():
    from services.search_service import SearchService
    from models import db, Retrieve
    
    # Perform a new search
    print("="*50)
    print("Performing NEW Search")
    print("="*50)
    
    result = SearchService.execute_search("telefon")
    search_id = result['search_id']
    print(f"\nNew search_id: {search_id}")
    
    # Check the retrieve records
    print("\n" + "="*50)
    print(f"Checking Retrieve Table (search_id={search_id})")
    print("="*50)
    
    retrieves = Retrieve.query.filter_by(search_id=search_id).order_by(Retrieve.rank).all()
    for r in retrieves:
        print(f"  rank: {r.rank}, product_id: {r.product_id}, weight: {r.weight}")
