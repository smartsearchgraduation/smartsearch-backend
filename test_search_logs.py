"""Test search with detailed logging."""
import sys
import logging
sys.path.insert(0, '.')

# Configure logging to show all logs
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

from app import create_app
app = create_app()

with app.app_context():
    from services.search_service import SearchService
    
    print("\n" + "="*70)
    print("TESTING SEARCH WITH DETAILED LOGGING")
    print("="*70 + "\n")
    
    # Test search
    result = SearchService.execute_search("ayakkabi")
    
    print("\n" + "="*70)
    print(f"RESULT: {result}")
    print("="*70)
