"""
Retrieval routes blueprint for FAISS operations.
Handles adding products to FAISS indices.
"""
import logging
from flask import Blueprint, request, jsonify
from services.faiss_retrieval_service import FAISSRetrievalService

logger = logging.getLogger(__name__)

retrieval_bp = Blueprint('retrieval', __name__, url_prefix='/api/retrieval')


@retrieval_bp.route('/search/text', methods=['POST'])
def search_text():
    """
    Perform text-only search.
    
    Request body:
    {
        "text": "red leather handbag",
        "textual_model_name": "ViT-B/32",
        "top_k": 10
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "error": "Request body is required"}), 400
            
        text = data.get('text')
        if not text:
            return jsonify({"status": "error", "error": "Missing required field: text"}), 400
            
        result = FAISSRetrievalService.search_text(
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
    Perform late fusion search (text + image).
    
    Request body:
    {
        "text": "red leather handbag",
        "textual_model_name": "ViT-B/32",
        "text_weight": 0.5,
        "image": "C:/path/to/image.jpg",
        "visual_model_name": "ViT-B/32",
        "top_k": 10
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "error": "Request body is required"}), 400
            
        text = data.get('text')
        image = data.get('image')
        
        # "sadece resim gelirse exception koy" -> If only image comes (no text), raise exception
        if image and not text:
             return jsonify({"status": "error", "error": "Text is required for late fusion search"}), 400
             
        if not text or not image:
            return jsonify({"status": "error", "error": "Both text and image are required for late fusion search"}), 400
            
        result = FAISSRetrievalService.search_late_fusion(
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
    Add a product to FAISS indices (textual and visual).
    
    This endpoint:
    1. Receives product data with images
    2. Validates all required fields
    3. Calls FAISSRetrievalService to encode and add to FAISS
    4. Returns FAISS vector IDs for tracking
    
    Request body:
    {
        "id": "product_001",
        "name": "Premium Leather Handbag",
        "description": "Elegant handcrafted leather bag",
        "brand": "LuxuryBrand",
        "category": "Accessories",
        "price": 299.99,
        "images": ["C:/absolute/path/to/image1.jpg", "C:/absolute/path/to/image2.jpg"],
        "textual_model_name": "ViT-B/32",  # Optional, defaults to ViT-B/32
        "visual_model_name": "ViT-B/32"    # Optional, defaults to ViT-B/32
    }
    
    Response (200 OK):
    {
        "status": "success",
        "message": "Product product_001 added successfully",
        "details": {
            "product_id": "product_001",
            "textual_vector_id": 0,
            "visual_vector_ids": [0, 1],
            "images_processed": 2
        }
    }
    
    Response (400 Bad Request):
    {
        "status": "error",
        "error": "Missing required field: name"
    }
    
    Response (500 Internal Server Error):
    {
        "status": "error",
        "error": "Failed to add product to FAISS"
    }
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
        result = FAISSRetrievalService.add_product(
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
