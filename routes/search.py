"""
API routes for handling search queries from the frontend.
"""
import logging
from flask import Blueprint, request, jsonify

from models import db
from services.search_service import SearchService

logger = logging.getLogger(__name__)

search_bp = Blueprint('search', __name__, url_prefix='/api')


@search_bp.route('/search', methods=['POST'])
def search():
    """
    The main search endpoint - this is what the frontend calls.
    
    Send us the user's search text (and optionally an image), and we'll:
    - Fix any typos
    - Search FAISS for matching products  
    - Fall back to database search if needed
    - Save everything for analytics
    
    Returns a search_id you can use with GET /search/<id> to fetch results.
    """
    try:
        data = request.get_json()
        print(f"DEBUG [routes/search.py]: Received search request data: {data}")

        # Validate request
        if not data or 'raw_text' not in data:
            print("DEBUG [routes/search.py]: Missing 'raw_text' in request body")
            return jsonify({"error": "Missing 'raw_text' in request body"}), 400

        raw_text = data.get('raw_text', '')
        image = data.get('image')
        
        print(f"DEBUG [routes/search.py]: Extracted raw_text='{raw_text}', image='{image}'")

        if not raw_text or not raw_text.strip():
            print("DEBUG [routes/search.py]: 'raw_text' is empty")
            return jsonify({"error": "'raw_text' cannot be empty"}), 400
        
        # Execute search through service
        print("DEBUG [routes/search.py]: Calling SearchService.execute_search...")
        result = SearchService.execute_search(raw_text, image)
        print(f"DEBUG [routes/search.py]: SearchService returned: {result}")
        
        # Return search_id and raw_text
        return jsonify({
            'search_id': result['search_id']
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"[Search] Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


@search_bp.route('/search/<int:search_id>', methods=['GET'])
def get_search(search_id):
    """
    Fetch the results of a previous search.
    
    Use the search_id returned from POST /search to get all the matching
    products with their details, images (as base64), and scores.
    """
    try:
        result = SearchService.get_search_by_id(search_id)
        
        if result is None:
            return jsonify({"error": "Search query not found"}), 404
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"[Search] Unexpected error getting search {search_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500
