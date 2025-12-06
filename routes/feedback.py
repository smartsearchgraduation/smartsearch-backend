"""
Feedback routes blueprint (feedback and click tracking).
"""
from flask import Blueprint, request, jsonify

from models import db, Retrieve, SearchQuery

feedback_bp = Blueprint('feedback', __name__, url_prefix='/api')


@feedback_bp.route('/feedback', methods=['POST'])
def feedback():
    """
    Receive thumbs up/down feedback from frontend.
    
    Request body:
    {
        "query_id": 123,
        "product_id": 456,
        "is_ok": true
    }
    
    Response:
    {
        "ok": true
    }
    """
    try:
        data = request.get_json()
        
        # Validate request
        if not data or 'query_id' not in data or 'product_id' not in data or 'is_relevant' not in data:
            return jsonify({"error": "Missing required fields: query_id, product_id, is_relevant"}), 400
        
        query_id = data['query_id']
        product_id = data['product_id']
        is_relevant = data['is_relevant']
        
        # Find the retrieve record
        retrieve = Retrieve.query.filter_by(
            search_id=query_id,
            product_id=product_id
        ).first()
        
        if not retrieve:
            return jsonify({"error": "Search result not found"}), 404
        
        # Update feedback
        retrieve.is_relevant = is_relevant
        db.session.commit()
        
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@feedback_bp.route('/click', methods=['POST'])
def click():
    """
    Mark that a product was clicked.
    
    Request body:
    {
        "query_id": 123,
        "product_id": 456
    }
    
    Response:
    {
        "ok": true
    }
    """
    try:
        data = request.get_json()
        
        # Validate request
        if not data or 'query_id' not in data or 'product_id' not in data:
            return jsonify({"error": "Missing required fields: query_id, product_id"}), 400
        
        query_id = data['query_id']
        product_id = data['product_id']
        
        # Find the retrieve record
        retrieve = Retrieve.query.filter_by(
            search_id=query_id,
            product_id=product_id
        ).first()
        
        if not retrieve:
            return jsonify({"error": "Search result not found"}), 404
        
        # Update click status
        retrieve.is_clicked = True
        db.session.commit()
        
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@feedback_bp.route('/metrics', methods=['GET'])
def metrics():
    """
    Get search and feedback metrics.
    
    Response:
    {
        "total_searches": 100,
        "total_clicks": 50,
        "total_feedback": 30,
        "positive_feedback": 25,
        "negative_feedback": 5,
        "click_through_rate": 0.5,
        "avg_retrieval_time_ms": 150
    }
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
