"""
Search routes blueprint.
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
    Handle search query from frontend.
    
    This endpoint orchestrates the search process:
    1. Receives raw text input from the user.
    2. Validates the input.
    3. Delegates the search logic to SearchService.execute_search(), which:
       - Calls the Text Correction Service.
       - Calls the FAISS Service for semantic retrieval.
       - Fallbacks to database search if FAISS is unavailable.
       - Logs the query and results to the database.
    4. Returns the search_id for subsequent result retrieval.
    
    Request body:
    {
        "raw_text": "iphone 15 pro"
    }
    
    Response (201 Created):
    {
        "search_id": 123
    }
    
    Returns:
        JSON response with search_id or error message.
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
    Get a specific search query with its results.
    
    Response format per work.txt spec:
    {
        "search_id": 123,
        "corrected_text": "...",
        "products": [
            {
                "product_id": ...,
                "name": "...",
                "price": ...,
                "rank": ...,
                "score": ...,
                "brand": "Brand Name",
                "image_url": "https://...",
                "categories": ["Elektronik", "Akıllı Telefon"]
            },
            ...
        ]
    }
    
    Returns 404 if search_id doesn't exist.
    """
    try:
        result = SearchService.get_search_by_id(search_id)
        
        if result is None:
            return jsonify({"error": "Search query not found"}), 404
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"[Search] Unexpected error getting search {search_id}: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500
