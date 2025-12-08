"""
FAISS Retrieval service for adding products to FAISS indices.
Handles text and visual embedding generation and storage.
"""
import os
import logging
from typing import Dict, Any, List, Optional
from flask import current_app
from .external_services import faiss_client

logger = logging.getLogger(__name__)


class FAISSRetrievalService:
    """
    Service class for FAISS retrieval operations.
    
    Handles:
    1. Adding products to FAISS indices (text + visual)
    2. Encoding product metadata (name, description, brand, category)
    3. Processing product images for visual embeddings
    4. Managing FAISS index updates
    """
    
    @staticmethod
    def search(
        query_text: str,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Perform generic search via FAISS service.
        
        Args:
            query_text: Search query
            top_k: Number of results
            
        Returns:
            dict with results
        """
        try:
            if not query_text or not query_text.strip():
                return {
                    "status": "error",
                    "error": "query_text is required"
                }
                
            result = faiss_client.search(
                query_text=query_text,
                top_k=top_k
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[FAISSRetrieval] Search error: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    @staticmethod
    def search_text(
        text: str,
        textual_model_name: str = "ViT-B/32",
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Perform text-only search.
        
        Args:
            text: Search query
            textual_model_name: Model name
            top_k: Number of results
            
        Returns:
            dict with results
        """
        print(f"DEBUG [FAISSRetrievalService]: search_text called with text='{text}'")
        try:
            if not text or not text.strip():
                print("DEBUG [FAISSRetrievalService]: text is empty")
                return {
                    "status": "error",
                    "error": "text is required"
                }
                
            print("DEBUG [FAISSRetrievalService]: Calling faiss_client.search_text...")
            result = faiss_client.search_text(
                text=text,
                textual_model_name=textual_model_name,
                top_k=top_k
            )
            print(f"DEBUG [FAISSRetrievalService]: faiss_client returned: {result}")
            
            if result.get('status') == 'error':
                print(f"DEBUG [FAISSRetrievalService]: Error in result: {result}")
                return result
                
            return result
            
        except Exception as e:
            print(f"DEBUG [FAISSRetrievalService]: EXCEPTION: {e}")
            logger.error(f"[FAISSRetrieval] Text search error: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    @staticmethod
    def search_late_fusion(
        text: str,
        image_path: str,
        text_weight: float = 0.5,
        textual_model_name: str = "ViT-B/32",
        visual_model_name: str = "ViT-B/32",
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Perform late fusion search (text + image).
        
        Args:
            text: Search query
            image_path: Path to query image
            text_weight: Weight for text score
            textual_model_name: Text model name
            visual_model_name: Visual model name
            top_k: Number of results
            
        Returns:
            dict with results
        """
        print(f"DEBUG [FAISSRetrievalService]: search_late_fusion called with text='{text}', image_path='{image_path}'")
        try:
            if not text or not text.strip():
                print("DEBUG [FAISSRetrievalService]: text is empty")
                return {
                    "status": "error",
                    "error": "text is required"
                }
                
            if not image_path or not os.path.exists(image_path):
                print(f"DEBUG [FAISSRetrievalService]: Image not found at {image_path}")
                return {
                    "status": "error",
                    "error": f"Image not found: {image_path}"
                }
                
            print("DEBUG [FAISSRetrievalService]: Calling faiss_client.search_late_fusion...")
            result = faiss_client.search_late_fusion(
                text=text,
                image_path=image_path,
                text_weight=text_weight,
                textual_model_name=textual_model_name,
                visual_model_name=visual_model_name,
                top_k=top_k
            )
            print(f"DEBUG [FAISSRetrievalService]: faiss_client returned: {result}")
            
            if result.get('status') == 'error':
                print(f"DEBUG [FAISSRetrievalService]: Error in result: {result}")
                return result
                
            return result
            
        except Exception as e:
            print(f"DEBUG [FAISSRetrievalService]: EXCEPTION: {e}")
            logger.error(f"[FAISSRetrieval] Late fusion search error: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    @staticmethod
    def add_product(
        product_id: str,
        name: str,
        description: str,
        brand: str,
        category: str,
        price: float,
        images: List[str],
        textual_model_name: str = "ViT-B/32",
        visual_model_name: str = "ViT-B/32",
        fused_model_name: str = "ViT-B/32"

    ) -> Dict[str, Any]:
        """
        Add a product to FAISS indices (textual and visual).
        
        Flow:
        1. Validate inputs (product_id, name, images)
        2. Prepare textual data: concatenate name, description, brand, category
        3. Call FAISS service to add product with text and image paths
        4. FAISS service handles:
           - Text encoding using specified model
           - Image encoding for each image path
           - Adding vectors to FAISS indices
           - Returning vector IDs for tracking
        
        Args:
            product_id: Unique product identifier
            name: Product name
            description: Product description
            brand: Brand name
            category: Category name
            price: Product price
            images: List of absolute image paths
            textual_model_name: Model name for text encoding (e.g., "ViT-B/32")
            visual_model_name: Model name for image encoding (e.g., "ViT-B/32")
        
        Returns:
            dict with:
                - status: "success" or "error"
                - message: Status message
                - details: (on success)
                    - product_id: Product ID
                    - textual_vector_id: FAISS index ID for text embedding
                    - visual_vector_ids: List of FAISS index IDs for image embeddings
                    - images_processed: Count of successfully processed images
                - error: (on failure) Error message
        """
        try:
            logger.info(f"[FAISSRetrieval] Adding product {product_id} with {len(images)} images")
            
            # Validate required fields
            if not product_id:
                return {
                    "status": "error",
                    "error": "product_id is required"
                }
            
            if not name or not name.strip():
                return {
                    "status": "error",
                    "error": "name is required and cannot be empty"
                }
            
            # Get upload folder
            upload_folder = current_app.config.get('UPLOAD_FOLDER')

            # Check that image files exist
            valid_images = []
            if images and isinstance(images, list):
                for img_path in images:
                    # If path is relative, assume it's in upload folder
                    if not os.path.isabs(img_path):
                        full_path = os.path.join(upload_folder, img_path)
                    else:
                        full_path = img_path
                        
                    if not os.path.exists(full_path):
                        logger.warning(f"[FAISSRetrieval] Image not found: {full_path}")
                    else:
                        valid_images.append(full_path)
            
            # Call FAISS service to add product
            result = faiss_client.add_product(
                product_id=product_id,
                image_paths=valid_images,
                textual_model=textual_model_name,
                visual_model=visual_model_name,
                fused_model_name=fused_model_name,
                name=name,
                description=description,
                brand=brand,
                category=category,
                price=price
            )
            
            if not result.get('success', False):
                error_msg = result.get('error', 'FAISS service failed to add product')
                logger.error(f"[FAISSRetrieval] Failed to add product {product_id}: {error_msg}")
                return {
                    "status": "error",
                    "error": error_msg
                }
            
            # Extract FAISS response details
            faiss_data = result.get('data', {})
            textual_vector_id = faiss_data.get('textual_vector_id', 0)
            visual_vector_ids = faiss_data.get('visual_vector_ids', [])
            images_processed = len(visual_vector_ids)
            
            logger.info(
                f"[FAISSRetrieval] Successfully added product {product_id}: "
                f"text_id={textual_vector_id}, visual_ids={visual_vector_ids}"
            )
            
            return {
                "status": "success",
                "message": f"Product {product_id} added successfully",
                "details": {
                    "product_id": product_id,
                    "textual_vector_id": textual_vector_id,
                    "visual_vector_ids": visual_vector_ids,
                    "images_processed": images_processed
                }
            }
            
        except Exception as e:
            logger.error(f"[FAISSRetrieval] Error adding product {product_id}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
