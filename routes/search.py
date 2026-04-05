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
    - Fix any typos (if correction_enabled=true)
    - Search FAISS for matching products (if semantic_search_enabled=true)
    - Or do DB ilike search (if semantic_search_enabled=false)  
    - Fall back to database search if needed
    - Save everything for analytics
    
    Query Parameters (as form data):
    - raw_text (required): User's search query
    - images: Optional image file(s) for visual search
    - engine: Correction engine to use ('symspell', 'byt5')
    - correction_enabled: 'true' or 'false' (default: true)
    - semantic_search_enabled: 'true' or 'false' (default: true)
    - fusion_type: 'late', 'early', 'text', 'image', 'image_by_text', 'text_by_image'
    
    If raw_text_flag=True and search_id is provided, it will use the raw text
    from the original search to perform a new search without spell correction.
    
    Returns a search_id you can use with GET /search/<id> to fetch results.
    """
    start_time = time.time()
    try:
        # Get all form data
        form_data = request.form.to_dict()
        images = request.files.getlist('images')
        image = images[0] if len(images) > 0 else None
        
        print(f"DEBUG [routes/search.py]: Received form data: {form_data}")
        print(f"DEBUG [routes/search.py]: Images: {images}")

        # Check if this is a raw text search request
        raw_text_flag = form_data.get('raw_text_flag', '').lower() == 'true'
        original_search_id = form_data.get('search_id')
        
        # If raw_text_flag is True and search_id is provided, use raw text search
        if raw_text_flag and original_search_id:
            print(f"DEBUG [routes/search.py]: Raw text search mode - original_search_id={original_search_id}")
            
            # Get toggle settings for raw text search too
            semantic_enabled = form_data.get('semantic_search_enabled', '').lower() != 'false'
            fusion_type = form_data.get('fusion_type', 'late')
            correction_enabled = form_data.get('correction_enabled', '').lower() != 'false'
            
            result = SearchService.execute_rawtext_search(
                original_search_id, 
                image,
                semantic_search_enabled=semantic_enabled,
                fusion_type=fusion_type,
                correction_enabled=correction_enabled
            )
            print(f"DEBUG [routes/search.py]: SearchService.execute_rawtext_search returned: {result}")
            
            duration = (time.time() - start_time) * 1000
            logger.info(f"[Search Route] 🏁 Total Request Time (incl. Flask): {duration:.2f}ms")
            
            return jsonify({
                'search_id': result['new_search_id'],
                'original_search_id': result['original_search_id']
            }), 201

        # Validate raw_text
        raw_text = form_data.get('raw_text')
        if not raw_text:
            print("DEBUG [routes/search.py]: Missing 'raw_text' in request")
            return jsonify({"error": "Missing 'raw_text' in request"}), 400

        if not raw_text.strip():
            print("DEBUG [routes/search.py]: 'raw_text' is empty")
            return jsonify({"error": "'raw_text' cannot be empty"}), 400

        engine = form_data.get('engine')
        
        # Parse toggle parameters
        semantic_search_enabled = form_data.get('semantic_search_enabled', '').lower() != 'false'  # default: true
        correction_enabled = form_data.get('correction_enabled', '').lower() != 'false'  # default: true
        fusion_type = form_data.get('fusion_type', 'late')  # default: late fusion

        print(f"DEBUG [routes/search.py]: Extracted raw_text='{raw_text}', engine='{engine}'")
        print(f"DEBUG [routes/search.py]: Toggles: semantic={semantic_search_enabled}, correction={correction_enabled}, fusion={fusion_type}")

        # Execute search through service with toggles
        print("DEBUG [routes/search.py]: Calling SearchService.execute_search...")
        result = SearchService.execute_search(
            raw_text, 
            image, 
            engine=engine,
            semantic_search_enabled=semantic_search_enabled,
            correction_enabled=correction_enabled,
            fusion_type=fusion_type
        )
        print(f"DEBUG [routes/search.py]: SearchService returned: {result}")
        
        # Log total time including Flask overhead
        duration = (time.time() - start_time) * 1000
        logger.info(f"[Search Route] 🏁 Total Request Time (incl. Flask): {duration:.2f}ms")
        
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
