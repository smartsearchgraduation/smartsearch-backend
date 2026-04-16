"""
API routes for handling search queries from the frontend.
"""

import logging
import time
import os
import uuid
import base64
import re
from flask import Blueprint, request, jsonify, current_app

from models import db
from services.search_service import SearchService
from config.models import get_selected_fusion_endpoint

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


def save_base64_image(base64_data):
    """
    Save base64 encoded image to file and return the path.

    Supports data URI format (data:image/jpeg;base64,/9j/4AAQ...)
    or raw base64 string.
    """
    if not base64_data:
        return None

    try:
        # Handle data URI format
        if base64_data.startswith("data:"):
            # Extract mime type and base64 data
            match = re.match(r"data:([^;]+);base64,(.+)", base64_data)
            if match:
                mime_type = match.group(1)
                base64_content = match.group(2)

                # Map mime type to extension
                mime_to_ext = {
                    "image/jpeg": ".jpg",
                    "image/jpg": ".jpg",
                    "image/png": ".png",
                    "image/gif": ".gif",
                    "image/webp": ".webp",
                    "image/bmp": ".bmp",
                }
                ext = mime_to_ext.get(mime_type, ".jpg")
            else:
                ext = ".jpg"
                base64_content = base64_data.split(",")[-1]
        else:
            ext = ".jpg"
            base64_content = base64_data

        # Decode base64
        image_data = base64.b64decode(base64_content)

        # Save to file
        filename = f"search_{uuid.uuid4().hex}{ext}"
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads/products")
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)

        with open(file_path, "wb") as f:
            f.write(image_data)

        # Verify
        if not os.path.exists(file_path):
            raise OSError("File save failed - file not found after save")

        logger.info(f"[Search] Base64 image saved to: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"[Search] Failed to save base64 image: {e}")
        raise ValueError(f"Base64 image processing failed: {str(e)}")


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
    - raw_text (optional): User's search query (required if no image provided)
    - images: Optional image file(s) for visual search (required if no text provided)
        - search_mode: Search mode ('std', 'iwt', 'twi')
            - std: Normal search flow (text/image/late/early fusion)
            - iwt: Image-by-text (text -> visual index)
            - twi: Text-by-image (image -> textual index)
    - engine: Correction engine to use ('symspell', 'byt5')
    - correction_enabled: 'true' or 'false' (default: true)

    Fusion type (late/early) is determined from saved config:
    - text_only: when only text is provided
    - image_only: when only image is provided
    - late_fusion: when both provided and fusion_endpoint='late'
    - early_fusion: when both provided and fusion_endpoint='early' (TODO: base64 not supported yet)
    - db_fallback: when FAISS fails

    Returns a search_id you can use with GET /search/<id> to fetch results.
    """
    start_time = time.time()
    try:
        # Check fusion endpoint setting
        fusion_endpoint = get_selected_fusion_endpoint()
        logger.info(f"[Search Route] ⚙️ Configured fusion endpoint: {fusion_endpoint}")

        # Get all form data
        form_data = request.form.to_dict()
        images = request.files.getlist("images")
        image_file = images[0] if len(images) > 0 else None

        # Check for base64 image in form data
        base64_image = form_data.get("image_base64")

        image = None

        # Handle file upload
        if image_file:
            try:
                image = save_search_image(image_file)
                logger.info(f"[Search Route] Image saved from file upload: {image}")
            except ValueError as e:
                logger.error(f"[Search] Image validation error: {e}")
                return jsonify({"error": str(e)}), 400

        # Handle base64 image
        elif base64_image:
            try:
                image = save_base64_image(base64_image)
                logger.info(f"[Search Route] Image saved from base64: {image}")
            except ValueError as e:
                logger.error(f"[Search] Base64 image validation error: {e}")
                return jsonify({"error": str(e)}), 400

        print(f"DEBUG [routes/search.py]: Received form data: {form_data}")

        # Get raw_text (now optional if image is provided)
        raw_text = form_data.get("raw_text", "")
        search_mode = (form_data.get("search_mode") or "std").strip().lower()

        if search_mode not in {"std", "iwt", "twi"}:
            return jsonify(
                {
                    "error": "Invalid search_mode. Allowed values: 'std', 'iwt', 'twi'"
                }
            ), 400

        # Validate request payload according to selected search mode
        has_text = raw_text and raw_text.strip()
        has_image = bool(image)

        if search_mode == "iwt" and not has_text:
            return jsonify({"error": "'raw_text' is required for search_mode='iwt'"}), 400

        if search_mode == "twi" and not has_image:
            return jsonify({"error": "'image' is required for search_mode='twi'"}), 400

        if search_mode == "std" and not has_text and not has_image:
            print(
                "DEBUG [routes/search.py]: Missing both 'raw_text' and 'image' in request"
            )
            return jsonify(
                {"error": "Either 'raw_text' or 'image' must be provided"}
            ), 400

        engine = form_data.get("engine")

        # Parse toggle parameters
        correction_enabled = (
            form_data.get("correction_enabled", "").lower() != "false"
        )  # default: true

        print(
            f"DEBUG [routes/search.py]: Extracted raw_text='{raw_text}', engine='{engine}'"
        )
        print(
            f"DEBUG [routes/search.py]: Toggles: correction={correction_enabled}, search_mode={search_mode}"
        )

        # Execute search through service with toggles
        print("DEBUG [routes/search.py]: Calling SearchService.execute_search...")
        result = SearchService.execute_search(
            raw_text,
            image,
            engine=engine,
            semantic_search_enabled=True,  # Always true
            correction_enabled=correction_enabled,
            search_mode=search_mode,
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
    on product names, and returns all matching products.
    Does NOT save anything to the database.

    Request Body (JSON):
        - search_id (required): The ID of the search to get text from

    Returns:
        - original_search_id: The search_id that was provided
        - search_text: The text that was used for search
        - products: Array of all matching products with product_id, name, price, score
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
