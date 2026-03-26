"""
API routes for direct FAISS operations.
These endpoints let you add products to the search index and perform
various types of searches (text-only, late fusion with images, etc.).
"""
import logging
from flask import Blueprint, request, jsonify
from services.faiss_retrieval_service import faiss_service

logger = logging.getLogger(__name__)

retrieval_bp = Blueprint('retrieval', __name__, url_prefix='/api/retrieval')


@retrieval_bp.route('/search/text', methods=['POST'])
def search_text():
    """
    Search for products using just text.
    
    Send a JSON body with "text" (required), and optionally "textual_model_name"
    and "top_k" to customize the search.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "error": "Request body is required"}), 400
            
        text = data.get('text')
        if not text:
            return jsonify({"status": "error", "error": "Missing required field: text"}), 400
            
        result = faiss_service.search_text(
            text=text,
            textual_model_name=data.get('textual_model_name', 'ViT-B/32'),
            top_k=data.get('top_k', 10)
        )
        
        if result.get('status') == 'error':
            return jsonify(result), 500
            
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"[Retrieval] Text search error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route('/search/late', methods=['POST'])
def search_late_fusion():
    """
    Search using both text and an image for best results.
    
    Send a JSON body with "text" and "image" (both required). You can also
    adjust "text_weight" to control how much the text vs image matters.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "error": "Request body is required"}), 400
            
        text = data.get('text')
        image = data.get('image')
        
        # Late fusion requires both text and image - reject requests with only an image
        if image and not text:
             return jsonify({"status": "error", "error": "Text is required for late fusion search"}), 400
             
        if not text or not image:
            return jsonify({"status": "error", "error": "Both text and image are required for late fusion search"}), 400
            
        result = faiss_service.search_late_fusion(
            text=text,
            image_path=image,
            text_weight=data.get('text_weight', 0.5),
            textual_model_name=data.get('textual_model_name', 'ViT-B/32'),
            visual_model_name=data.get('visual_model_name', 'ViT-B/32'),
            top_k=data.get('top_k', 10)
        )
        
        if result.get('status') == 'error':
            return jsonify(result), 500
            
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"[Retrieval] Late fusion search error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@retrieval_bp.route('/add-product', methods=['POST'])
def add_product():
    """
    Add a product directly to the FAISS search index.
    
    Use this to make a product searchable without going through the main
    products API. You'll need to provide the product ID, name, and image paths.
    The product will be indexed for both text and visual search.
    """
    try:
        data = request.get_json()
        
        # Validate request body
        if not data:
            return jsonify({
                "status": "error",
                "error": "Request body is required"
            }), 400
        
        # Extract required fields
        product_id = data.get('id')
        name = data.get('name')
        description = data.get('description', '')
        brand = data.get('brand', '')
        category = data.get('category', '')
        price = data.get('price', 0.0)
        images = data.get('images', [])
        textual_model_name = data.get('textual_model_name', 'ViT-B/32')
        visual_model_name = data.get('visual_model_name', 'ViT-B/32')
        fused_model_name = data.get('fused_model_name', 'ViT-B/32')
        
        # Validate required fields
        if not product_id:
            return jsonify({
                "status": "error",
                "error": "Missing required field: id"
            }), 400
        
        if not name:
            return jsonify({
                "status": "error",
                "error": "Missing required field: name"
            }), 400
        
        # Validate price
        try:
            price = float(price)
        except (ValueError, TypeError):
            return jsonify({
                "status": "error",
                "error": "Invalid price value"
            }), 400
        
        logger.info(f"[Retrieval] Adding product {product_id} to FAISS")
        
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
            fused_model_name=fused_model_name
        )
        
        # Check result status
        if result.get('status') == 'error':
            logger.error(f"[Retrieval] Failed to add product {product_id}: {result.get('error')}")
            return jsonify(result), 500

        logger.info(f"[Retrieval] Successfully added product {product_id} to FAISS")
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "error": "An unexpected error occurred"
        }), 500


@retrieval_bp.route('/models', methods=['GET'])
def get_available_models():
    """
    Get the list of available textual and visual models from the FAISS service.

    Returns a list of supported embedding models that can be used for search
    operations. This endpoint is useful for populating UI dropdowns or
    validating model selections.

    The response includes:
    - textual_models: Models available for text embedding
    - visual_models: Models available for image embedding
    - defaults: Default model selections for both text and visual
    - source: Whether the data came from 'faiss_service' or 'local_config'
    """
    try:
        logger.info("[Retrieval] Fetching available models")

        result = faiss_service.get_available_models()

        if result.get('status') == 'error':
            logger.warning(f"[Retrieval] Models fetch returned error: {result.get('error')}")
            return jsonify(result), 500

        logger.info(f"[Retrieval] Successfully fetched models from {result.get('source', 'unknown')}")
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Unexpected error fetching models: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@retrieval_bp.route('/clear-index', methods=['DELETE'])
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

        if result.get('status') == 'error':
            logger.error(f"[Retrieval] Clear index failed: {result.get('error')}")
            return jsonify(result), 500

        logger.info(f"[Retrieval] Index cleared: {result.get('details', {})}")
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Retrieval] Unexpected error clearing index: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@retrieval_bp.route('/test-product', methods=['POST'])
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
        product_id = data.get('product_id', 'test-product-001')

        logger.info(f"[Retrieval] Adding test product: {product_id}")

        result = faiss_service.add_test_product(product_id=product_id)

        if result.get('status') == 'error':
            logger.error(f"[Retrieval] Test product failed: {result.get('error')}")
            return jsonify(result), 500

        logger.info(f"[Retrieval] Test product added successfully: {product_id}")
        return jsonify({
            "status": "success",
            "message": f"Test product {product_id} added successfully",
            "details": result.get('details', {})
        }), 200

    except Exception as e:
        logger.error(f"[Retrieval] Unexpected error adding test product: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500
