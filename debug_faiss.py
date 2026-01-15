"""Debug script to check FAISS score types."""
import sys
sys.path.insert(0, '.')

from app import create_app
app = create_app()

with app.app_context():
    from services.faiss_retrieval_service import faiss_service
    from models import db, Retrieve
    
    # Test FAISS search
    print("="*50)
    print("Testing FAISS Search")
    print("="*50)
    
    result = faiss_service.search_text('laptop', top_k=3)
    print(f"\nFAISS Result keys: {result.keys()}")
    print(f"Status: {result.get('status')}")
    
    results = result.get('results', [])
    print(f"\nResults count: {len(results)}")
    
    for p in results:
        pid = p['product_id']
        score = p.get('score')
        print(f"\n  product_id: {pid}")
        print(f"    type: {type(pid).__name__}")
        print(f"  score: {score}")
        print(f"    type: {type(score).__name__}")
    
    # Check existing retrieve records
    print("\n" + "="*50)
    print("Checking Retrieve Table (search_id=8)")
    print("="*50)
    
    retrieves = Retrieve.query.filter_by(search_id=8).order_by(Retrieve.rank).limit(5).all()
    for r in retrieves:
        print(f"\n  product_id: {r.product_id}, rank: {r.rank}, weight: {r.weight}")
        print(f"    weight type: {type(r.weight).__name__ if r.weight else 'None'}")
