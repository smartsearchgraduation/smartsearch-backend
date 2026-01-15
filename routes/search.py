"""
API routes for handling search queries from the frontend.
"""
import logging
import time
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
    
    If raw_text_flag=True and search_id is provided, it will use the raw text
    from the original search to perform a new search without spell correction.
    
    Returns a search_id you can use with GET /search/<id> to fetch results.
    """
    start_time = time.time()
    try:
        data = request.get_json()
        print(f"DEBUG [routes/search.py]: Received search request data: {data}")

        # Check if this is a raw text search request
        raw_text_flag = data.get('raw_text_flag', False)
        original_search_id = data.get('search_id')
        image = data.get('image')
        
        # If raw_text_flag is True and search_id is provided, use raw text search
        if raw_text_flag and original_search_id:
            print(f"DEBUG [routes/search.py]: Raw text search mode - original_search_id={original_search_id}")
            
            result = SearchService.execute_rawtext_search(original_search_id, image)
            print(f"DEBUG [routes/search.py]: SearchService.execute_rawtext_search returned: {result}")
            
            duration = (time.time() - start_time) * 1000
            logger.info(f"[Search Route] 🏁 Total Request Time (incl. Flask): {duration:.2f}ms")
            
            return jsonify({
                'search_id': result['new_search_id'],
                'original_search_id': result['original_search_id']
            }), 201

        # Normal search flow - validate request
        if not data or 'raw_text' not in data:
            print("DEBUG [routes/search.py]: Missing 'raw_text' in request body")
            return jsonify({"error": "Missing 'raw_text' in request body"}), 400

        raw_text = data.get('raw_text', '')
        engine = data.get('engine')  # Extract optional correction engine
        
        print(f"DEBUG [routes/search.py]: Extracted raw_text='{raw_text}', image='{image}', engine='{engine}'")

        if not raw_text or not raw_text.strip():
            print("DEBUG [routes/search.py]: 'raw_text' is empty")
            return jsonify({"error": "'raw_text' cannot be empty"}), 400
        
        # Execute search through service
        print("DEBUG [routes/search.py]: Calling SearchService.execute_search...")
        result = SearchService.execute_search(raw_text, image, engine=engine)
        print(f"DEBUG [routes/search.py]: SearchService returned: {result}")
        
        # Log total time including Flask overhead
        duration = (time.time() - start_time) * 1000
        logger.info(f"[Search Route] 🏁 Total Request Time (incl. Flask): {duration:.2f}ms")
        
        # Return search_id and raw_text
        return jsonify({
            'search_id': result['search_id']
        }), 201

    except ValueError as e:
        logger.error(f"[Search] Value error: {e}")
        return jsonify({"error": str(e)}), 404
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
