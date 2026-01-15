"""
Demo script to print analytics API responses.
"""
import json
from app import create_app
from models import db, SearchTime, SearchQuery
from datetime import datetime

def demo():
    app = create_app()
    app.testing = True
    client = app.test_client()
    
    with app.app_context():
        # Create dummy data
        search = SearchQuery(raw_text="demo_search", timestamp=datetime.utcnow())
        db.session.add(search)
        db.session.commit()
        
        st = SearchTime(
            search_id=search.search_id,
            correction_time=12.5,
            faiss_time=45.2,
            db_time=10.1,
            backend_total_time=67.8,
            search_duration=1200.5,
            product_load_duration=300.2
        )
        db.session.add(st)
        db.session.commit()
        
        try:
            # 1. GET All Logs
            print("\n" + "="*50)
            print(f"REQUEST: GET /api/analytics/logs")
            print("="*50)
            response = client.get('/api/analytics/logs')
            data = response.get_json()
            print(json.dumps(data, indent=2))
            
            # 2. GET Single Log
            print("\n" + "="*50)
            print(f"REQUEST: GET /api/analytics/logs/{search.search_id}")
            print("="*50)
            response = client.get(f'/api/analytics/logs/{search.search_id}')
            data = response.get_json()
            print(json.dumps(data, indent=2))
            
        finally:
            # Cleanup
            db.session.delete(st)
            db.session.delete(search)
            db.session.commit()

if __name__ == '__main__':
    demo()
