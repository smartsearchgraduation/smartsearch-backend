"""
This module handles all communication with the FAISS retrieval microservice.
It provides methods for searching products using text, images, or a combination
of both (late fusion), as well as adding new products to the search index.
"""
import os
import time
import logging
from typing import Dict, Any, List

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from flask import current_app

logger = logging.getLogger(__name__)

# These URLs point to the FAISS microservice 
FAISS_SERVICE_URL = os.getenv('FAISS_SERVICE_URL', 'http://localhost:5002/api/retrieval/search')
FAISS_ADD_PRODUCT_URL = os.getenv('FAISS_ADD_PRODUCT_URL', 'http://localhost:5002/api/retrieval/add-product')
FAISS_TEXT_SEARCH_URL = os.getenv('FAISS_TEXT_SEARCH_URL', 'http://localhost:5002/api/retrieval/search/text')
FAISS_LATE_FUSION_URL = os.getenv('FAISS_LATE_FUSION_URL', 'http://localhost:5002/api/retrieval/search/late')
FAISS_DELETE_PRODUCT_URL = os.getenv('FAISS_DELETE_PRODUCT_URL', 'http://localhost:5002/api/retrieval/delete-product')


class FAISSRetrievalService:
    """
    The main client for talking to our FAISS search service.
    
    This class handles all the heavy lifting for product search:
    - Text-based searches (find products matching a query)
    - Late fusion searches (combine text + image for better results)
    - Adding new products to the search index
    
    All the actual embedding and indexing happens in the FAISS microservice;
    we just send HTTP requests and handle the responses here.
    """
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or FAISS_SERVICE_URL
        self.add_product_url = FAISS_ADD_PRODUCT_URL
        self.text_search_url = FAISS_TEXT_SEARCH_URL
        self.late_fusion_url = FAISS_LATE_FUSION_URL
        self.delete_product_url = FAISS_DELETE_PRODUCT_URL

    def search(
        self,
        query_text: str,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Search for products using a text query.
        
        Sends the query to FAISS and returns a ranked list of matching products.
        Each result includes a product_id and a relevance score.
        
        Args:
            query_text: The search query (ideally already spell-corrected)
            top_k: How many results to return (default: 10)
        
        Returns:
            A dict with 'products' list and 'success' flag
        """
        if not HAS_REQUESTS:
            logger.warning("[FAISS] requests library not installed, returning empty results")
            return {'products': [], 'success': False}
        
        start_time = time.time()
        try:
            logger.info(f"[FAISS] Calling service at {self.base_url} with query: '{query_text}'")
            response = requests.post(
                self.base_url,
                json={
                    'query': query_text,
                    'top_k': top_k
                },
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            
            products = result.get('products', [])
            duration = (time.time() - start_time) * 1000
            
            if not products:
                logger.info(f"[FAISS] Query: '{query_text}' -> empty results (took {duration:.2f}ms)")
                return {'products': [], 'success': False}
            
            logger.info(f"[FAISS] Query: '{query_text}' -> {len(products)} results (took {duration:.2f}ms)")
            
            return {
                'products': products,
                'success': True
            }
        except requests.exceptions.ConnectionError:
            duration = (time.time() - start_time) * 1000
            logger.warning(f"[FAISS] Service not available at {self.base_url} (took {duration:.2f}ms)")
            return {'products': [], 'success': False}
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"[FAISS] Error: {e} (took {duration:.2f}ms)")
            return {'products': [], 'success': False}

    def search_text(
        self,
        text: str,
        textual_model_name: str = "BAAI/bge-large-en-v1.5",
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Run a text-only search against the FAISS index.
        
        just takes a text query and finds matching products based on semantic similarity.
        
        Args:
            text: What the user is searching for
            textual_model_name: Which embedding model to use (default: ViT-B/32)
            top_k: Maximum number of results to return
        
        Returns:
            Search results with product IDs and scores, or an error message
        """
        if not text or not text.strip():
            return {"status": "error", "error": "text is required"}
            
        if not HAS_REQUESTS:
            logger.warning("[FAISS] requests library not installed")
            return {'status': 'error', 'error': 'requests library missing'}
            
        try:
            logger.info(f"[FAISS] Text search: '{text}' (model={textual_model_name})")
            payload = {
                'text': text,
                'textual_model_name': textual_model_name,
                'top_k': top_k
            }
            response = requests.post(
                self.text_search_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', response.text)
                except:
                    error_msg = response.text
                
                logger.error(f"[FAISS] Text search failed: {response.status_code} - {error_msg}")
                return {'status': 'error', 'error': f"FAISS Error ({response.status_code}): {error_msg}"}

            result = response.json()
            
            if result.get('status') == 'success' or result.get('success', False):
                return result
            else:
                error = result.get('error', 'Unknown error from FAISS service')
                logger.error(f"[FAISS] Text search failed: {error}")
                return {'status': 'error', 'error': error}

        except Exception as e:
            logger.error(f"[FAISS] Text search error: {e}")
            return {'status': 'error', 'error': str(e)}

    def search_late_fusion(
        self,
        text: str,
        image_path: str,
        text_weight: float = 0.5,
        textual_model_name: str = "BAAI/bge-large-en-v1.5",
        visual_model_name: str = "ViT-B/32",
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Search using both text and an image for better accuracy.
        
        Late fusion combines the scores from text matching and visual similarity
        to find products that match both what the user typed AND what they're
        looking at. Great for "find me something like this" searches.
        
        Args:
            text: The user's search query
            image_path: Full path to the uploaded image file
            text_weight: How much to prioritize text vs image (0.5 = equal)
            textual_model_name: Model for encoding the text
            visual_model_name: Model for encoding the image
            top_k: How many results to return
        
        Returns:
            Search results combining both text and visual matching
        """
        if not text or not text.strip():
            return {"status": "error", "error": "text is required"}
            
        if not image_path or not os.path.exists(image_path):
            return {"status": "error", "error": f"Image not found: {image_path}"}
            
        if not HAS_REQUESTS:
            logger.warning("[FAISS] requests library not installed")
            return {'status': 'error', 'error': 'requests library missing'}
            
        try:
            logger.info(f"[FAISS] Late fusion search: '{text}' + '{image_path}'")
            payload = {
                'text': text,
                'image': image_path,
                'text_weight': text_weight,
                'textual_model_name': textual_model_name,
                'visual_model_name': visual_model_name,
                'top_k': top_k
            }
            response = requests.post(
                self.late_fusion_url,
                json=payload,
                timeout=15
            )
            
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', response.text)
                except:
                    error_msg = response.text
                
                logger.error(f"[FAISS] Late fusion search failed: {response.status_code} - {error_msg}")
                return {'status': 'error', 'error': f"FAISS Error ({response.status_code}): {error_msg}"}

            result = response.json()
            
            if result.get('status') == 'success' or result.get('success', False):
                return result
            else:
                error = result.get('error', 'Unknown error from FAISS service')
                logger.error(f"[FAISS] Late fusion search failed: {error}")
                return {'status': 'error', 'error': error}

        except Exception as e:
            logger.error(f"[FAISS] Late fusion search error: {e}")
            return {'status': 'error', 'error': str(e)}

    def add_product(
        self,
        product_id: str,
        name: str,
        description: str,
        brand: str,
        category: str,
        price: float,
        images: List[str],
        textual_model_name: str = "BAAI/bge-large-en-v1.5",
        visual_model_name: str = "ViT-B/32",
        fused_model_name: str = "ViT-B/32"
    ) -> Dict[str, Any]:
        """
        Add a new product to the FAISS search index.
        
        This sends the product's text info (name, description, etc.) and images
        to the FAISS service, which will create embeddings and add them to the
        appropriate indices. After this, the product will show up in searches.
        
        Args:
            product_id: The unique ID for this product
            name: Product name (required - this is what users search for)
            description: Longer product description
            brand: Brand/manufacturer name
            category: Product category for filtering
            price: Product price
            images: List of image file paths to index for visual search
            textual_model_name: Embedding model for text (default: ViT-B/32)
            visual_model_name: Embedding model for images
            fused_model_name: Model for combined embeddings
        
        Returns:
            Result dict with the FAISS vector IDs assigned to this product
        """
        try:
            logger.info(f"[FAISS] Adding product {product_id} with {len(images)} images")
            
            # Validate required fields
            if not product_id:
                return {"status": "error", "error": "product_id is required"}
            
            if not name or not name.strip():
                return {"status": "error", "error": "name is required and cannot be empty"}
            
            if not HAS_REQUESTS:
                logger.warning("[FAISS] requests library not installed")
                return {"status": "error", "error": "requests library not installed"}
            
            # Get upload folder
            upload_folder = current_app.config.get('UPLOAD_FOLDER')

            # Check that image files exist
            valid_images = []
            if images and isinstance(images, list):
                for img_path in images:
                    if not os.path.isabs(img_path):
                        full_path = os.path.join(upload_folder, img_path)
                    else:
                        full_path = img_path
                    
                    # Normalize path to use forward slashes for cross-platform compatibility
                    full_path = full_path.replace('\\', '/')
                        
                    if not os.path.exists(full_path.replace('/', '\\')):  # Check with native path
                        logger.warning(f"[FAISS] Image not found: {full_path}")
                    else:
                        valid_images.append(full_path)
                        logger.info(f"[FAISS] Valid image path: {full_path}")
            
            start_time = time.time()
            
            # Construct payload
            payload = {
                'id': product_id,
                'name': name,
                'description': description,
                'brand': brand,
                'category': category,
                'price': price,
                'images': valid_images,
                'textual_model_name': textual_model_name,
                'visual_model_name': visual_model_name,
                'fused_model_name': fused_model_name
            }
            
            # Debug: Log full payload for troubleshooting
            logger.info(f"[FAISS] Full add_product payload: {payload}")
            
            response = requests.post(
                self.add_product_url,
                json=payload,
                timeout=120
            )
            
            duration = (time.time() - start_time) * 1000
            
            if response.status_code not in [200, 201]:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', response.text)
                except:
                    error_msg = response.text
                
                logger.error(f"[FAISS] Failed to add product {product_id}: {response.status_code} - {error_msg}")
                return {"status": "error", "error": f"FAISS Error ({response.status_code}): {error_msg}"}
                
            result = response.json()
            
            if result.get('success', False) or result.get('status') == 'success':
                data = result.get('data', result.get('details', {}))
                textual_vector_id = data.get('textual_vector_id', 0)
                visual_vector_ids = data.get('visual_vector_ids', [])
                images_processed = len(visual_vector_ids)
                
                logger.info(
                    f"[FAISS] Successfully added product {product_id}: "
                    f"text_id={textual_vector_id}, visual_ids={visual_vector_ids} "
                    f"(took {duration:.2f}ms)"
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
            else:
                error = result.get('error', 'FAISS service failed to add product')
                logger.error(f"[FAISS] Failed to add product {product_id}: {error}")
                return {"status": "error", "error": error}
                
        except requests.exceptions.ConnectionError:
            logger.error(f"[FAISS] Service not available at {self.add_product_url}")
            return {"status": "error", "error": "FAISS service not available"}
        except requests.exceptions.Timeout:
            logger.error(f"[FAISS] Request timeout adding product {product_id}")
            return {"status": "error", "error": "Request timeout - image processing may have failed"}
        except Exception as e:
            logger.error(f"[FAISS] Error adding product {product_id}: {e}")
            return {"status": "error", "error": str(e)}

    def delete_product(self, product_id: str) -> Dict[str, Any]:
        """
        Delete a product from the FAISS search index.
        
        This sends a DELETE request to the FAISS service to remove all embeddings
        (textual and visual) associated with the given product ID.
        
        Args:
            product_id: The unique ID of the product to delete
        
        Returns:
            Result dict with status indicating success or failure
        """
        if not HAS_REQUESTS:
            logger.warning("[FAISS] requests library not installed")
            return {"status": "error", "error": "requests library not installed"}
        
        try:
            logger.info(f"[FAISS] Deleting product {product_id} from index")
            
            start_time = time.time()
            
            # Build the URL with product_id
            url = f"{self.delete_product_url}/{product_id}"
            
            response = requests.delete(
                url,
                timeout=30
            )
            
            duration = (time.time() - start_time) * 1000
            
            if response.status_code == 404:
                logger.warning(f"[FAISS] Product {product_id} not found in FAISS index (took {duration:.2f}ms)")
                return {"status": "success", "message": f"Product {product_id} not in FAISS index"}
            
            if response.status_code not in [200, 204]:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', response.text)
                except:
                    error_msg = response.text
                
                logger.error(f"[FAISS] Failed to delete product {product_id}: {response.status_code} - {error_msg}")
                return {"status": "error", "error": f"FAISS Error ({response.status_code}): {error_msg}"}
            
            # Try to parse response if present
            try:
                result = response.json()
            except:
                result = {}
            
            logger.info(f"[FAISS] Successfully deleted product {product_id} from index (took {duration:.2f}ms)")
            
            return {
                "status": "success",
                "message": f"Product {product_id} deleted from FAISS index",
                "details": result
            }
            
        except requests.exceptions.ConnectionError:
            logger.error(f"[FAISS] Service not available at {self.delete_product_url}")
            return {"status": "error", "error": "FAISS service not available"}
        except requests.exceptions.Timeout:
            logger.error(f"[FAISS] Request timeout deleting product {product_id}")
            return {"status": "error", "error": "Request timeout"}
        except Exception as e:
            logger.error(f"[FAISS] Error deleting product {product_id}: {e}")
            return {"status": "error", "error": str(e)}


# Create a single shared instance for the whole app
faiss_service = FAISSRetrievalService()

