"""
API routes for user feedback and click tracking on search results.
"""
import traceback
from flask import Blueprint, request, jsonify

from models import db, Retrieve, SearchQuery

feedback_bp = Blueprint('feedback', __name__, url_prefix='/api')


@feedback_bp.route('/feedback', methods=['POST'])
def feedback():
    """
    Record whether a user liked a search result (thumbs up/down).
    
    Send the query_id, product_id, and is_relevant (true/false).
    We use this to improve search quality over time.
    """
    print("\n" + "="*60)
    print("[FEEDBACK] POST /api/feedback called")
    print("="*60)
    
    try:
        data = request.get_json()
        print(f"[FEEDBACK] Request data: {data}")
        
        # Validate request
        if not data or 'query_id' not in data or 'product_id' not in data or 'is_relevant' not in data:
            print("[FEEDBACK] ERROR: Missing required fields")
            return jsonify({"error": "Missing required fields: query_id, product_id, is_relevant"}), 400
        
        # Convert to int to ensure proper DB type matching (BigInteger)
        query_id = int(data['query_id'])
        product_id = int(data['product_id'])
        is_relevant = data['is_relevant']
        
        print(f"[FEEDBACK] query_id={query_id}, product_id={product_id}, is_relevant={is_relevant}")
        print(f"[FEEDBACK] Types - query_id: {type(query_id)}, product_id: {type(product_id)}")
        
        # Find the retrieve record
        print(f"[FEEDBACK] Searching for Retrieve record with search_id={query_id}, product_id={product_id}")
        retrieve = Retrieve.query.filter_by(
            search_id=query_id,
            product_id=product_id
        ).first()
        
        if not retrieve:
            print(f"[FEEDBACK] ERROR: No Retrieve record found!")
            # Debug: show what records exist for this search_id
            existing = Retrieve.query.filter_by(search_id=int(query_id)).all()
            print(f"[FEEDBACK] Existing records for search_id={query_id}: {len(existing)}")
            for r in existing[:5]:
                print(f"  - product_id={r.product_id}, rank={r.rank}")
            return jsonify({"error": "Search result not found"}), 404
        
        print(f"[FEEDBACK] Found Retrieve record: {retrieve}")
        
        # Update feedback
        retrieve.is_relevant = is_relevant
        db.session.commit()
        
        print(f"[FEEDBACK] SUCCESS: Updated is_relevant to {is_relevant}")
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        print(f"[FEEDBACK] EXCEPTION: {type(e).__name__}: {str(e)}")
        print(f"[FEEDBACK] Traceback:\n{traceback.format_exc()}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@feedback_bp.route('/click', methods=['POST'])
def click():
    """
    Track when a user clicks on a search result.
    
    Send query_id and product_id so we know which result was clicked.
    Helps us measure how useful our search results are.
    """
    print("\n" + "="*60)
    print("[CLICK] POST /api/click called")
    print("="*60)
    
    try:
        data = request.get_json()
        print(f"[CLICK] Request data: {data}")
        
        # Validate request
        if not data or 'query_id' not in data or 'product_id' not in data:
            print("[CLICK] ERROR: Missing required fields")
            return jsonify({"error": "Missing required fields: query_id, product_id"}), 400
        
        # Convert to int to ensure proper DB type matching (BigInteger)
        query_id = int(data['query_id'])
        product_id = int(data['product_id'])
        
        print(f"[CLICK] query_id={query_id}, product_id={product_id}")
        print(f"[CLICK] Types - query_id: {type(query_id)}, product_id: {type(product_id)}")
        
        # Find the retrieve record
        print(f"[CLICK] Searching for Retrieve record...")
        retrieve = Retrieve.query.filter_by(
            search_id=query_id,
            product_id=product_id
        ).first()
        
        if not retrieve:
            print(f"[CLICK] ERROR: No Retrieve record found!")
            existing = Retrieve.query.filter_by(search_id=int(query_id)).all()
            print(f"[CLICK] Existing records for search_id={query_id}: {len(existing)}")
            for r in existing[:5]:
                print(f"  - product_id={r.product_id}, rank={r.rank}")
            return jsonify({"error": "Search result not found"}), 404
        
        print(f"[CLICK] Found Retrieve record: {retrieve}")
        
        # Update click status
        retrieve.is_clicked = True
        db.session.commit()
        
        print(f"[CLICK] SUCCESS: Updated is_clicked to True")
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        print(f"[CLICK] EXCEPTION: {type(e).__name__}: {str(e)}")
        print(f"[CLICK] Traceback:\n{traceback.format_exc()}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@feedback_bp.route('/metrics', methods=['GET'])
def metrics():
    """
    Get overall search performance statistics.
    
    Returns things like total searches, click-through rate, and
    how many thumbs up/down we've received. Useful for dashboards.
    """
    try:
        # Count total searches
        total_searches = SearchQuery.query.count()
        
        # Count clicks and feedback
        total_clicks = Retrieve.query.filter(Retrieve.is_clicked == True).count()
        
        positive_feedback = Retrieve.query.filter(Retrieve.is_relevant == True).count()
        negative_feedback = Retrieve.query.filter(Retrieve.is_relevant == False).count()
        total_feedback = positive_feedback + negative_feedback
        
        # Calculate click-through rate
        total_results = Retrieve.query.count()
        ctr = total_clicks / total_results if total_results > 0 else 0
        
        # Calculate average retrieval time
        avg_time = db.session.query(
            db.func.avg(SearchQuery.time_to_retrieve)
        ).scalar() or 0
        
        return jsonify({
            "total_searches": total_searches,
            "total_clicks": total_clicks,
            "total_feedback": total_feedback,
            "positive_feedback": positive_feedback,
            "negative_feedback": negative_feedback,
            "click_through_rate": round(ctr, 4),
            "avg_retrieval_time_ms": round(float(avg_time), 2)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
