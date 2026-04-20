"""
API routes for direct FAISS operations.
These endpoints let you add products to the search index and perform
various types of searches (text-only, late fusion with images, etc.).
"""

import os
import logging
from flask import Blueprint, request, jsonify, current_app, render_template_string
from services.faiss_retrieval_service import faiss_service
from config.models import (
    get_selected_models,
    save_selected_models,
    get_selected_fusion_endpoint,
    save_selected_fusion_endpoint,
    AVAILABLE_MODELS,
    is_valid_fusion_endpoint,
)

logger = logging.getLogger(__name__)

retrieval_bp = Blueprint("retrieval", __name__, url_prefix="/api/retrieval")


def _get_valid_model_ids():
    """Use the FAISS-advertised model catalog when available, otherwise local config."""
    model_ids = faiss_service.get_available_model_ids()
    return model_ids or list(AVAILABLE_MODELS.keys())


@retrieval_bp.route("/search/text", methods=["POST"])
def search_text():
    """
    Search for products using just text.

    Send a JSON body with "text" (required), and optionally "textual_model_name"
    and "top_k" to customize the search.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {"status": "error", "error": "Request body is required"}
            ), 400

        text = data.get("text")
        if not text:
            return jsonify(
                {"status": "error", "error": "Missing required field: text"}
            ), 400

        result = faiss_service.search_text(
            text=text,
            textual_model_name=data.get("textual_model_name", "ViT-B/32"),
            top_k=data.get("top_k", 10),
        )

        if result.get("status") == "error":
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Text search error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/search/late", methods=["POST"])
def search_late_fusion():
    """
    Search using both text and an image for best results.

    Send a JSON body with "text" and "image" (both required). You can also
    adjust "text_weight" to control how much the text vs image matters.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {"status": "error", "error": "Request body is required"}
            ), 400

        text = data.get("text")
        image = data.get("image")

        # Late fusion requires both text and image - reject requests with only an image
        if image and not text:
            return jsonify(
                {"status": "error", "error": "Text is required for late fusion search"}
            ), 400

        if not text or not image:
            return jsonify(
                {
                    "status": "error",
                    "error": "Both text and image are required for late fusion search",
                }
            ), 400

        result = faiss_service.search_late_fusion(
            text=text,
            image_path=image,
            text_weight=data.get("text_weight", 0.5),
            textual_model_name=data.get("textual_model_name", "ViT-B/32"),
            visual_model_name=data.get("visual_model_name", "ViT-B/32"),
            top_k=data.get("top_k", 10),
        )

        if result.get("status") == "error":
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Late fusion search error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/search/early", methods=["POST"])
def search_early_fusion():
    """
    Search using early fusion of text and image into a single embedding.

    Both text and image are fused into a single query embedding using CLIP's
    shared embedding space, then searches the Fused index.

    Request body:
        - text: Search query text (required)
        - image: Path to image file (required)
        - fused_model_name: CLIP model to use (default: ViT-B/32)
        - text_weight: Weight for text vs image (0.5 = equal, optional)
        - top_k: Number of results (default: 10)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {"status": "error", "error": "Request body is required"}
            ), 400

        text = data.get("text")
        image = data.get("image")

        if not text or not text.strip():
            return jsonify(
                {"status": "error", "error": "Missing required field: text"}
            ), 400

        if not image:
            return jsonify(
                {"status": "error", "error": "Missing required field: image"}
            ), 400

        result = faiss_service.search_early_fusion(
            text=text,
            image_path=image,
            text_weight=data.get("text_weight", 0.5),
            fused_model_name=data.get("fused_model_name", "ViT-B/32"),
            top_k=data.get("top_k", 10),
        )

        if result.get("status") == "error":
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Early fusion search error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/search/image", methods=["POST"])
def search_image():
    """
    Search for products using only an image (image-only search).

    Encodes the query image and searches the visual index to find
    visually similar products.

    Request body:
        - image: Path to image file (required)
        - visual_model_name: Which embedding model to use (default: ViT-B/32)
        - top_k: Number of results (default: 10)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {"status": "error", "error": "Request body is required"}
            ), 400

        image = data.get("image")

        if not image:
            return jsonify(
                {"status": "error", "error": "Missing required field: image"}
            ), 400

        result = faiss_service.search_image(
            image_path=image,
            visual_model_name=data.get("visual_model_name", "ViT-B/32"),
            top_k=data.get("top_k", 10),
        )

        if result.get("status") == "error":
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Image search error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/search/image-by-text", methods=["POST"])
def search_image_by_text():
    """
    Cross-modal search: Find product images using a text query.

    Encodes the text with CLIP's text encoder and searches the Visual index.
    Only CLIP models are supported since both modalities must share the
    same embedding space.

    Request body:
        - text: Search query text (required)
        - fused_model_name: CLIP model to use (default: ViT-B/32)
        - top_k: Number of results (default: 10)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {"status": "error", "error": "Request body is required"}
            ), 400

        text = data.get("text")

        if not text or not text.strip():
            return jsonify(
                {"status": "error", "error": "Missing required field: text"}
            ), 400

        result = faiss_service.search_image_by_text(
            text=text,
            fused_model_name=data.get("fused_model_name", "ViT-B/32"),
            top_k=data.get("top_k", 10),
        )

        if result.get("status") == "error":
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Image-by-text search error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/search/text-by-image", methods=["POST"])
def search_text_by_image():
    """
    Cross-modal search: Find product text descriptions using an image query.

    Encodes the image with CLIP's image encoder and searches the Textual index.
    Only CLIP models are supported since both modalities must share the
    same embedding space.

    Request body:
        - image: Path to image file (required)
        - fused_model_name: CLIP model to use (default: ViT-B/32)
        - top_k: Number of results (default: 10)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {"status": "error", "error": "Request body is required"}
            ), 400

        image = data.get("image")

        if not image:
            return jsonify(
                {"status": "error", "error": "Missing required field: image"}
            ), 400

        result = faiss_service.search_text_by_image(
            image_path=image,
            fused_model_name=data.get("fused_model_name", "ViT-B/32"),
            top_k=data.get("top_k", 10),
        )

        if result.get("status") == "error":
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Text-by-image search error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/add-product", methods=["POST"])
def add_product():
    """
    Add a product to the retrieval system for the specified model only.

    If the product already has embeddings for the active model, the request is
    skipped and a success response with "skipped": true is returned.
    """
    try:
        data = request.get_json()

        # Validate request body
        if not data:
            return jsonify(
                {"status": "error", "error": "Request body is required"}
            ), 400

        # Extract required fields
        product_id = data.get("id")
        name = data.get("name")
        description = data.get("description", "")
        brand = data.get("brand", "")
        category = data.get("category", "")
        price = data.get("price", 0.0)
        images = data.get("images", [])
        textual_model_name = data.get("textual_model_name", "ViT-B/32")
        visual_model_name = data.get("visual_model_name", "ViT-B/32")
        fused_model_name = data.get("fused_model_name", "ViT-B/32")

        # Validate required fields
        if not product_id:
            return jsonify(
                {"status": "error", "error": "Missing required field: id"}
            ), 400

        if not name:
            return jsonify(
                {"status": "error", "error": "Missing required field: name"}
            ), 400

        # Validate price
        try:
            price = float(price)
        except (ValueError, TypeError):
            return jsonify({"status": "error", "error": "Invalid price value"}), 400

        logger.info(
            f"[Retrieval] Adding product {product_id} to FAISS for model {textual_model_name}/{visual_model_name}"
        )

        # Call service to add product
        result = faiss_service.add_product(
            product_id=product_id,
            name=name,
            description=description,
            brand=brand,
            category=category,
            price=price,
            images=images,
            textual_model_name=textual_model_name,
            visual_model_name=visual_model_name,
            fused_model_name=fused_model_name,
        )

        # Check result status
        if result.get("status") == "error":
            logger.error(
                f"[Retrieval] Failed to add product {product_id}: {result.get('error')}"
            )
            return jsonify(result), 500

        logger.info(f"[Retrieval] Successfully added product {product_id} to FAISS")
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Unexpected error: {e}")
        return jsonify(
            {"status": "error", "error": "An unexpected error occurred"}
        ), 500


@retrieval_bp.route("/update-product/<product_id>", methods=["PUT"])
def update_product(product_id):
    """
    Update a product in the retrieval system.

    Removes old embeddings from ALL model folders, then re-indexes with the active model.
    """
    try:
        data = request.get_json()

        # Validate request body
        if not data:
            return jsonify(
                {"status": "error", "error": "Request body is required"}
            ), 400

        # Extract fields
        name = data.get("name", "")
        description = data.get("description", "")
        brand = data.get("brand", "")
        category = data.get("category", "")
        price = data.get("price", 0.0)
        images = data.get("images", [])
        textual_model_name = data.get("textual_model_name", "ViT-B/32")
        visual_model_name = data.get("visual_model_name", "ViT-B/32")
        fused_model_name = data.get("fused_model_name", "ViT-B/32")

        # Validate price
        try:
            price = float(price)
        except (ValueError, TypeError):
            return jsonify({"status": "error", "error": "Invalid price value"}), 400

        logger.info(f"[Retrieval] Updating product {product_id} in FAISS")

        # Call service to update product
        result = faiss_service.update_product(
            product_id=product_id,
            name=name,
            description=description,
            brand=brand,
            category=category,
            price=price,
            images=images,
            textual_model_name=textual_model_name,
            visual_model_name=visual_model_name,
            fused_model_name=fused_model_name,
        )

        # Check result status
        if result.get("status") == "error":
            logger.error(
                f"[Retrieval] Failed to update product {product_id}: {result.get('error')}"
            )
            return jsonify(result), 500

        logger.info(f"[Retrieval] Successfully updated product {product_id} in FAISS")
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Unexpected error updating product {product_id}: {e}")
        return jsonify(
            {"status": "error", "error": "An unexpected error occurred"}
        ), 500


@retrieval_bp.route("/delete-product/<product_id>", methods=["DELETE"])
def delete_product(product_id):
    """
    Delete a product from the retrieval system.

    Removes all embeddings for a product from ALL model folders.
    """
    try:
        logger.info(f"[Retrieval] Deleting product {product_id} from FAISS")

        # Call service to delete product
        result = faiss_service.delete_product(product_id)

        # Check result status
        if result.get("status") == "error":
            logger.error(
                f"[Retrieval] Failed to delete product {product_id}: {result.get('error')}"
            )
            return jsonify(result), 500

        logger.info(f"[Retrieval] Successfully deleted product {product_id} from FAISS")
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Unexpected error deleting product {product_id}: {e}")
        return jsonify(
            {"status": "error", "error": "An unexpected error occurred"}
        ), 500


@retrieval_bp.route("/index-stats", methods=["GET"])
def get_index_stats():
    """
    Get index statistics for all models.

    Returns per-model index statistics showing how many textual, visual, and fused embeddings exist in each model folder.
    """
    try:
        logger.info("[Retrieval] Fetching index statistics")

        result = faiss_service.get_index_stats()

        if result.get("status") == "error":
            logger.error(
                f"[Retrieval] Failed to get index stats: {result.get('error')}"
            )
            return jsonify(result), 500

        logger.info("[Retrieval] Successfully fetched index statistics")
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Unexpected error fetching index stats: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/models", methods=["GET"])
def get_available_models():
    """
    Get the list of available textual and visual models from the FAISS service.

    Returns a list of supported embedding models that can be used for search
    operations. This endpoint is useful for populating UI dropdowns or
    validating model selections.

    The response includes:
    - textual_models: Models available for text embedding (array of {name, dimension})
    - visual_models: Models available for image embedding (array of {name, dimension})
    - defaults: Default model selections for both text and visual
    - source: Whether the data came from 'faiss_service' or 'local_config'
    """
    try:
        logger.info("[Retrieval] Fetching available models")

        result = faiss_service.get_available_models()

        if result.get("status") == "error":
            logger.warning(
                f"[Retrieval] Models fetch returned error: {result.get('error')}"
            )
            return jsonify(result), 500

        logger.info(
            f"[Retrieval] Successfully fetched models from {result.get('source', 'unknown')}"
        )
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Unexpected error fetching models: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/stats", methods=["GET"])
def get_system_stats():
    """
    Get comprehensive system statistics.
    """
    try:
        logger.info("[Retrieval] Fetching system statistics")

        # Get index statistics
        stats_result = faiss_service.get_index_stats()

        # Get available models
        models_result = faiss_service.get_available_models()

        # Get selected models
        from config.models import get_selected_models

        selected_models = get_selected_models()

        # Combine all stats
        system_stats = {
            "status": "success",
            "data": {
                "index_stats": stats_result.get(
                    "indices", stats_result.get("data", {})
                ),
                "available_models": models_result.get("data", {}),
                "selected_models": selected_models,
                "service_status": "healthy",
            },
        }

        logger.info("[Retrieval] Successfully fetched system statistics")
        return jsonify(system_stats), 200

    except Exception as e:
        logger.error(f"[Retrieval] Unexpected error fetching stats: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/clear-index", methods=["DELETE"])
def clear_index():
    """
    Clear all products from the FAISS search index.

    Use this endpoint when you need to rebuild the entire index from scratch,
    for example after changing embedding models. This will delete all textual
    and visual embeddings from the FAISS index.

    After clearing, you should add products back using either:
    - POST /api/retrieval/add-product (single product)
    - POST /api/bulk-faiss/add-all (all products from database)
    """
    try:
        logger.info("[Retrieval] Clearing FAISS index")

        result = faiss_service.clear_index()

        if result.get("status") == "error":
            logger.error(f"[Retrieval] Clear index failed: {result.get('error')}")
            return jsonify(result), 500

        logger.info(f"[Retrieval] Index cleared: {result.get('details', {})}")
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Unexpected error clearing index: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/test-product", methods=["POST"])
def add_test_product():
    """
    Add a test product to verify FAISS service is working.

    This endpoint adds a minimal test product to the FAISS index to perform
    a smoke test. Use this after clearing the index to verify the FAISS
    service is responsive before running a bulk import.

    Send optional JSON body with "product_id" to customize the test product ID.
    """
    try:
        data = request.get_json() or {}
        product_id = data.get("product_id", "test-product-001")

        logger.info(f"[Retrieval] Adding test product: {product_id}")

        result = faiss_service.add_test_product(product_id=product_id)

        if result.get("status") == "error":
            logger.error(f"[Retrieval] Test product failed: {result.get('error')}")
            return jsonify(result), 500

        logger.info(f"[Retrieval] Test product added successfully: {product_id}")
        return jsonify(
            {
                "status": "success",
                "message": f"Test product {product_id} added successfully",
                "details": result.get("details", {}),
            }
        ), 200

    except Exception as e:
        logger.error(f"[Retrieval] Unexpected error adding test product: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/selected-models", methods=["GET"])
def get_selected_models_endpoint():
    """
    Get currently selected models (for admin panel).

    Returns the models that will be used for bulk import operations
    if no models are specified in the request.
    """
    try:
        models = get_selected_models()

        return jsonify({"status": "success", "data": models}), 200

    except Exception as e:
        logger.error(f"[Retrieval] Error getting selected models: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/selected-models", methods=["POST"])
def save_selected_models_endpoint():
    """
    Save selected models (from admin panel).

    These models will be used for subsequent bulk import operations
    if no models are specified in the request.

    Request body:
        - textual_model: Textual embedding model name
        - visual_model: Visual model name
        - fusion_endpoint: 'late' or 'early' (optional, defaults to current)
    """
    try:
        data = request.get_json() or {}

        textual_model = data.get("textual_model")
        visual_model = data.get("visual_model")
        fusion_endpoint = data.get("fusion_endpoint")  # Optional

        # Validate required fields
        if not textual_model or not visual_model:
            return jsonify(
                {
                    "status": "error",
                    "error": "Both textual_model and visual_model are required",
                }
            ), 400

        available_model_ids = _get_valid_model_ids()

        # Validate model names
        if textual_model not in available_model_ids:
            return jsonify(
                {
                    "status": "error",
                    "error": f"Invalid textual model: {textual_model}. Available: {available_model_ids}",
                }
            ), 400

        if visual_model not in available_model_ids:
            return jsonify(
                {
                    "status": "error",
                    "error": f"Invalid visual model: {visual_model}. Available: {available_model_ids}",
                }
            ), 400

        # Validate fusion_endpoint if provided
        if fusion_endpoint and not is_valid_fusion_endpoint(fusion_endpoint):
            return jsonify(
                {
                    "status": "error",
                    "error": f"Invalid fusion_endpoint: {fusion_endpoint}. Must be 'late' or 'early'",
                }
            ), 400

        # Save to config (with fusion_endpoint)
        save_selected_models(textual_model, visual_model, fusion_endpoint)

        logger.info(
            f"[Retrieval] Models saved - Textual: {textual_model}, Visual: {visual_model}, Fusion: {fusion_endpoint or 'unchanged'}"
        )

        return jsonify(
            {
                "status": "success",
                "message": "Models saved successfully",
                "data": {
                    "textual_model": textual_model,
                    "visual_model": visual_model,
                    "fusion_endpoint": fusion_endpoint
                    or get_selected_fusion_endpoint(),
                },
            }
        ), 200

    except Exception as e:
        logger.error(f"[Retrieval] Error saving selected models: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/fusion-endpoint", methods=["GET"])
def get_fusion_endpoint():
    """
    Get currently selected fusion endpoint (for admin panel).

    Returns the fusion endpoint ('late' or 'early') that will be used
    for text+image searches.
    """
    try:
        endpoint = get_selected_fusion_endpoint()

        return jsonify(
            {
                "status": "success",
                "data": {
                    "fusion_endpoint": endpoint,
                    "description": "Late Fusion"
                    if endpoint == "late"
                    else "Early Fusion (CLIP)",
                },
            }
        ), 200

    except Exception as e:
        logger.error(f"[Retrieval] Error getting fusion endpoint: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/fusion-endpoint", methods=["POST"])
def save_fusion_endpoint():
    """
    Save selected fusion endpoint (from admin panel).

    This determines which FAISS endpoint to use when both text and image
    are provided in a search query:
    - 'late': Late Fusion (separate embeddings, weighted combination)
    - 'early': Early Fusion (CLIP, single fused embedding)

    Request body:
        - fusion_endpoint: 'late' or 'early'
    """
    try:
        data = request.get_json() or {}

        fusion_endpoint = data.get("fusion_endpoint")

        # Validate required fields
        if not fusion_endpoint:
            return jsonify(
                {"status": "error", "error": "fusion_endpoint is required"}
            ), 400

        # Validate endpoint value
        if not is_valid_fusion_endpoint(fusion_endpoint):
            return jsonify(
                {
                    "status": "error",
                    "error": f"Invalid fusion_endpoint: {fusion_endpoint}. Must be 'late' or 'early'",
                }
            ), 400

        # Save to config
        save_selected_fusion_endpoint(fusion_endpoint)

        logger.info(f"[Retrieval] Fusion endpoint saved: {fusion_endpoint}")

        return jsonify(
            {
                "status": "success",
                "message": "Fusion endpoint saved successfully",
                "data": {
                    "fusion_endpoint": fusion_endpoint,
                    "description": "Late Fusion"
                    if fusion_endpoint == "late"
                    else "Early Fusion (CLIP)",
                },
            }
        ), 200

    except Exception as e:
        logger.error(f"[Retrieval] Error saving fusion endpoint: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route("/selected-models/save-and-rebuild", methods=["GET", "POST"])
def save_and_rebuild():
    """
    Save selected models and rebuild FAISS index (POST), or get current settings (GET).

    GET: Returns current selected models without any changes.

    POST: Rebuilds FAISS index with current or specified settings.
    If models not specified in request, uses previously saved values.

    Workflow:
    1. Gets current saved models (or uses request values if provided)
    2. Saves to config (updates fusion_endpoint if provided)
    3. Clears FAISS index
    4. Waits for FAISS initialization
    5. Adds all products from database

    POST Request body (all optional):
        - textual_model: Textual embedding model (defaults to saved)
        - visual_model: Visual embedding model (defaults to saved)
        - fusion_endpoint: 'late' or 'early' (defaults to saved)
        - wait_duration_seconds: Seconds to wait after clear (default: 60)
    """
    import time
    from models import db
    from models.product import Product
    from models.product_image import ProductImage
    from sqlalchemy.orm import joinedload

    # GET: Return current settings without rebuilding
    if request.method == "GET":
        models = get_selected_models()
        return jsonify({"status": "success", "data": models}), 200

    start_time = time.time()

    try:
        data = request.get_json() or {}

        # Get current saved models as defaults
        current_models = get_selected_models()

        # Use request values if provided, otherwise use saved values
        textual_model = data.get("textual_model") or current_models.get("textual_model")
        visual_model = data.get("visual_model") or current_models.get("visual_model")
        fusion_endpoint = data.get(
            "fusion_endpoint"
        )  # Optional - None means keep current
        wait_duration_seconds = data.get("wait_duration_seconds", 60)

        # DEBUG: Log incoming request
        logger.info(f"[Rebuild] 📥 Request received: {data}")
        logger.info(
            f"[Rebuild] 🔧 Parsed - Textual: {textual_model}, Visual: {visual_model}, Fusion: {fusion_endpoint}"
        )
        logger.info(f"[Rebuild] 💾 Current saved models: {current_models}")

        # Validate required fields (should always have defaults from config)
        if not textual_model or not visual_model:
            return jsonify(
                {
                    "status": "error",
                    "error": "No models configured. Please select models first.",
                }
            ), 400

        available_model_ids = _get_valid_model_ids()

        # Validate model names
        if textual_model not in available_model_ids:
            return jsonify(
                {
                    "status": "error",
                    "error": f"Invalid textual model: {textual_model}. Available: {available_model_ids}",
                }
            ), 400

        if visual_model not in available_model_ids:
            return jsonify(
                {
                    "status": "error",
                    "error": f"Invalid visual model: {visual_model}. Available: {available_model_ids}",
                }
            ), 400

        # Validate fusion_endpoint if provided
        if fusion_endpoint and not is_valid_fusion_endpoint(fusion_endpoint):
            return jsonify(
                {
                    "status": "error",
                    "error": f"Invalid fusion_endpoint: {fusion_endpoint}. Must be 'late' or 'early'",
                }
            ), 400

        # Step 1: Save models to config
        logger.info(
            f"[Rebuild] Step 1/3: Saving models - Textual: {textual_model}, "
            f"Visual: {visual_model}, Fusion: {fusion_endpoint or 'unchanged (will use existing)'}"
        )
        save_selected_models(textual_model, visual_model, fusion_endpoint)
        effective_fusion_endpoint = get_selected_fusion_endpoint()
        logger.info(
            f"[Rebuild] ✅ Saved! Effective fusion endpoint: {effective_fusion_endpoint}"
        )

        # Step 2: Clear FAISS index
        logger.info(f"[Rebuild] Step 2/3: Clearing FAISS index")
        clear_result = faiss_service.clear_index()

        if clear_result.get("status") == "error":
            logger.warning(
                f"[Rebuild] Clear index returned error: {clear_result.get('error')}, continuing anyway"
            )

        # Step 3: Wait for FAISS initialization
        logger.info(
            f"[Rebuild] Step 3/3: Waiting {wait_duration_seconds}s for FAISS initialization..."
        )
        time.sleep(wait_duration_seconds)
        logger.info(
            f"[Rebuild] ✅ Wait completed ({wait_duration_seconds}s), starting product import"
        )

        # Step 4: Add all products from database
        products = (
            Product.query.filter_by(is_active=True)
            .options(
                joinedload(Product.brand),
            )
            .all()
        )

        if not products:
            return jsonify(
                {"status": "error", "error": "No products found in database"}
            ), 404

        total_products = len(products)
        successful_count = 0
        failed_count = 0
        errors = []

        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads/products")

        for idx, product in enumerate(products):
            try:
                brand_name = product.brand.name if product.brand else ""
                categories = list(product.categories)
                category_name = categories[0].name if categories else ""

                image_paths = []
                for img in product.images:
                    raw_url = img.url

                    # Handle different URL formats
                    if raw_url.startswith("/uploads/products/"):
                        # Web URL path - use config UPLOAD_FOLDER + filename
                        upload_folder = current_app.config.get(
                            "UPLOAD_FOLDER", "uploads/products"
                        )
                        if not os.path.isabs(upload_folder):
                            upload_folder = os.path.join(
                                current_app.root_path, upload_folder
                            )
                        filename = os.path.basename(raw_url)
                        image_path = os.path.join(upload_folder, filename)
                    elif os.path.isabs(raw_url):
                        # Already absolute file path
                        image_path = raw_url
                    else:
                        # Just filename or relative path - join with upload folder
                        upload_folder = current_app.config.get(
                            "UPLOAD_FOLDER", "uploads/products"
                        )
                        if not os.path.isabs(upload_folder):
                            upload_folder = os.path.join(
                                current_app.root_path, upload_folder
                            )
                        image_path = os.path.join(
                            upload_folder, os.path.basename(raw_url)
                        )

                    # Normalize path for Windows
                    image_path = os.path.normpath(image_path)

                    if os.path.exists(image_path):
                        image_paths.append(image_path)
                        logger.debug(f"[Rebuild] Valid image: {image_path}")
                    else:
                        logger.warning(
                            f"[Rebuild] Image not found: {image_path} (raw: {raw_url})"
                        )

                result = faiss_service.add_product(
                    product_id=str(product.product_id),
                    name=product.name,
                    description=product.description or "",
                    brand=brand_name,
                    category=category_name,
                    price=float(product.price) if product.price else 0.0,
                    images=image_paths,
                    textual_model_name=textual_model,
                    visual_model_name=visual_model,
                )

                if result.get("status") == "success":
                    successful_count += 1
                    logger.info(f"[Rebuild] ✅ Product {product.product_id} added")
                else:
                    failed_count += 1
                    errors.append(
                        {
                            "product_id": product.product_id,
                            "error": result.get("error", "Unknown error"),
                        }
                    )
                    logger.error(
                        f"[Rebuild] ❌ Product {product.product_id} failed: {result.get('error')}"
                    )

            except Exception as e:
                failed_count += 1
                errors.append({"product_id": product.product_id, "error": str(e)})
                logger.error(
                    f"[Rebuild] ❌ Product {product.product_id} exception: {e}"
                )

        total_duration = (time.time() - start_time) * 1000

        logger.info(
            f"[Rebuild] Completed: {successful_count}/{total_products} products in {total_duration:.2f}ms"
        )

        return jsonify(
            {
                "status": "success",
                "message": f"Models saved and FAISS index rebuilt successfully",
                "data": {
                    "textual_model": textual_model,
                    "visual_model": visual_model,
                    "fusion_endpoint": effective_fusion_endpoint,
                    "total_products": total_products,
                    "successful_count": successful_count,
                    "failed_count": failed_count,
                    "total_duration_ms": total_duration,
                    "wait_duration_seconds": wait_duration_seconds,
                },
                "errors": errors[:10],  # Limit to first 10 errors
            }
        ), 200

    except Exception as e:
        logger.error(f"[Rebuild] Failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500
