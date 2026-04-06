"""
API routes for handling search queries from the frontend.
"""

import logging
import time
import os
import uuid
from flask import Blueprint, request, jsonify, current_app

from models import db
from services.search_service import SearchService

logger = logging.getLogger(__name__)

search_bp = Blueprint("search", __name__, url_prefix="/api")


# TODO: QUICK FIX - This is a minimal solution to handle FileStorage objects
# The proper fix should involve database schema changes and proper image management
# This just saves search images to uploads folder permanently
def save_search_image(file):
    """Quick fix: save search image to uploads folder so FAISS can get file path"""
    if not file or file.filename == "":
        return None

    try:
        # Extract file extension from original filename
        original_ext = os.path.splitext(file.filename)[1].lower()
        if not original_ext:
            # Default to .jpg if no extension provided
            original_ext = ".jpg"

        # Validate it's an image extension
        allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        if original_ext not in allowed_extensions:
            raise ValueError(f"Unsupported image format: {original_ext}")

        filename = f"search_{uuid.uuid4().hex}{original_ext}"
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads/products")
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        # Verify file was saved successfully
        if not os.path.exists(file_path):
            raise OSError("File save failed - file not found after save")

        return file_path
    except Exception as e:
        logger.error(f"[Search] Failed to save search image: {e}")
        raise ValueError(f"Image processing failed: {str(e)}")


@search_bp.route("/search", methods=["POST"])
def search():
    """
    The main search endpoint - this is what the frontend calls.

    Send us the user's search text (and optionally an image), and we'll:
    - Fix any typos (if correction_enabled=true)
    - Search FAISS for matching products
    - Fall back to database search if needed
    - Save everything for analytics

    Query Parameters (as form data):
    - raw_text (required): User's search query
    - images: Optional image file(s) for visual search
    - engine: Correction engine to use ('symspell', 'byt5')
    - correction_enabled: 'true' or 'false' (default: true)

    Fusion type (late/early) is determined automatically from FAISS results:
    - text_only: when only text is provided
    - image_only: when only image is provided
    - late_fusion: when both provided and FAISS returns text_score + image_score
    - early_fusion: when both provided and FAISS returns combined_score only
    - db_fallback: when FAISS fails

    Returns a search_id you can use with GET /search/<id> to fetch results.
    """
    start_time = time.time()
    try:
        # Get all form data
        form_data = request.form.to_dict()
        images = request.files.getlist("images")
        image_file = images[0] if len(images) > 0 else None

        # TODO: QUICK FIX - Convert FileStorage to file path for FAISS compatibility
        # This should be replaced with proper image management in the future
        try:
            image = save_search_image(image_file) if image_file else None
        except ValueError as e:
            logger.error(f"[Search] Image validation error: {e}")
            return jsonify({"error": str(e)}), 400

        print(f"DEBUG [routes/search.py]: Received form data: {form_data}")
        print(f"DEBUG [routes/search.py]: Images: {images}")
        if image_file:
            print(f"DEBUG [routes/search.py]: Saved search image to: {image}")

        # Validate raw_text
        raw_text = form_data.get("raw_text")
        if not raw_text:
            print("DEBUG [routes/search.py]: Missing 'raw_text' in request")
            return jsonify({"error": "Missing 'raw_text' in request"}), 400

        if not raw_text.strip():
            print("DEBUG [routes/search.py]: 'raw_text' is empty")
            return jsonify({"error": "'raw_text' cannot be empty"}), 400

        engine = form_data.get("engine")

        # Parse toggle parameters
        correction_enabled = (
            form_data.get("correction_enabled", "").lower() != "false"
        )  # default: true

        print(
            f"DEBUG [routes/search.py]: Extracted raw_text='{raw_text}', engine='{engine}'"
        )
        print(f"DEBUG [routes/search.py]: Toggles: correction={correction_enabled}")

        # Execute search through service with toggles
        print("DEBUG [routes/search.py]: Calling SearchService.execute_search...")
        result = SearchService.execute_search(
            raw_text,
            image,
            engine=engine,
            semantic_search_enabled=True,  # Always true
            correction_enabled=correction_enabled,
        )
        print(f"DEBUG [routes/search.py]: SearchService returned: {result}")

        # Log total time including Flask overhead
        duration = (time.time() - start_time) * 1000
        logger.info(
            f"[Search Route] 🏁 Total Request Time (incl. Flask): {duration:.2f}ms"
        )

        return jsonify({"search_id": result["search_id"]}), 201

    except ValueError as e:
        logger.error(f"[Search] Value error: {e}")
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        db.session.rollback()
        logger.error(f"[Search] Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


@search_bp.route("/search/<int:search_id>", methods=["GET"])
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


@search_bp.route("/search/db-fallback", methods=["POST"])
def db_fallback_search():
    """
    DB fallback endpoint - performs database search using text from an existing search.

    Takes a search_id, retrieves the original text, performs a simple DB ILIKE search
    on product names, and returns the first 20 matching products.
    Does NOT save anything to the database.

    Request Body (JSON):
        - search_id (required): The ID of the search to get text from

    Returns:
        - original_search_id: The search_id that was provided
        - search_text: The text that was used for search
        - products: Array of up to 20 products with product_id, name, price, score
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        search_id = data.get("search_id")
        if not search_id:
            return jsonify({"error": "Missing required field: search_id"}), 400

        # Validate search_id is an integer
        try:
            search_id = int(search_id)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid search_id, must be an integer"}), 400

        logger.info(f"[Search Route] DB fallback request for search_id={search_id}")

        result = SearchService.execute_db_fallback_search(search_id)

        return jsonify(result), 200

    except ValueError as e:
        logger.error(f"[Search] Value error in DB fallback: {e}")
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"[Search] Unexpected error in DB fallback: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500
