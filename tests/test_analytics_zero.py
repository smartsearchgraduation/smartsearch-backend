import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import unittest
import json
from app import create_app
from models import db, SearchTime, SearchQuery
from datetime import datetime, timezone

class TestAnalyticsZeroValues(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        # Create dummy data
        self.search = SearchQuery(raw_text="zero_test", timestamp=datetime.now(timezone.utc))
        db.session.add(self.search)
        db.session.commit()
        
        self.st = SearchTime(search_id=self.search.search_id)
        db.session.add(self.st)
        db.session.commit()
        self.search_id = self.search.search_id

    def tearDown(self):
        db.session.delete(self.st)
        db.session.delete(self.search)
        db.session.commit()
        self.ctx.pop()

    def test_zero_duration(self):
        print(f"\nTesting POST with duration=0 for search_id={self.search_id}...")
        payload = {
            "search_id": self.search_id,
            "search_duration": 0,
            "product_load_duration": 100
        }
        
        response = self.client.post(
            '/api/analytics/search-duration',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        print(f"Response: {response.status_code}")
        self.assertEqual(response.status_code, 200)
        
        st = SearchTime.query.get(self.search_id)
        self.assertEqual(st.search_duration, 0)
        print("✅ Duration=0 accepted and saved")

if __name__ == '__main__':
    unittest.main()
