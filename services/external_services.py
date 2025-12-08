"""
External services integration module.
Handles communication with Text Corrector and FAISS services.
"""
import os
import time
import logging
from typing import Optional, List, Dict, Any

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger(__name__)

# Service URLs from environment
CORRECTION_SERVICE_URL = os.getenv('CORRECTION_SERVICE_URL', 'http://localhost:5001/correct')
FAISS_SERVICE_URL = os.getenv('FAISS_SERVICE_URL', 'http://localhost:5002/api/retrieval/search')


class TextCorrectorClient:
    """
    Client for Text Corrector service.
    Handles typo correction via HTTP API.
    
    API Contract per work.txt:
        POST { "text": raw_text } -> { "corrected_text": "..." }
    """
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or CORRECTION_SERVICE_URL
    
    def correct(self, raw_text: str) -> Dict[str, Any]:
        """
        Send raw text to Text Corrector service and get corrected version.
        
        API Contract:
            POST { "text": raw_text } -> { "corrected_text": "..." }
        
        Args:
            raw_text: Raw search query from user
            
        Returns:
            dict with:
                - corrected_text: Corrected/normalized query
                - success: Whether the call succeeded
        """
        print(f"DEBUG [TextCorrectorClient]: correct called with raw_text='{raw_text}'")
        if not HAS_REQUESTS:
            logger.warning("[TextCorrector] requests library not installed, returning original text")
            print("DEBUG [TextCorrectorClient]: requests library missing")
            return {
                'corrected_text': raw_text,
                'success': False
            }
        
        start_time = time.time()
        try:
            logger.info(f"[TextCorrector] Calling service at {self.base_url} with text: '{raw_text}'")
            print(f"DEBUG [TextCorrectorClient]: POST {self.base_url} payload={{'query': '{raw_text}', 'model': 'symspell'}}")
            response = requests.post(
                self.base_url,
                json={'query': raw_text, 'model': 'symspell'},
                timeout=5
            )
            print(f"DEBUG [TextCorrectorClient]: Response status={response.status_code}")
            response.raise_for_status()
            result = response.json()
            print(f"DEBUG [TextCorrectorClient]: Response body={result}")
            
            corrected_text = result.get('corrected_query', raw_text)
            duration = (time.time() - start_time) * 1000
            
            if corrected_text != raw_text:
                logger.info(f"[TextCorrector] Correction applied: '{raw_text}' -> '{corrected_text}' (took {duration:.2f}ms)")
            else:
                logger.info(f"[TextCorrector] No correction needed for '{raw_text}' (took {duration:.2f}ms)")
            
            return {
                'corrected_text': corrected_text,
                'success': True
            }
        except requests.exceptions.ConnectionError:
            duration = (time.time() - start_time) * 1000
            logger.warning(f"[TextCorrector] Service not available at {self.base_url} (took {duration:.2f}ms), returning original text")
            print(f"DEBUG [TextCorrectorClient]: ConnectionError to {self.base_url}")
            return {
                'corrected_text': raw_text,
                'success': False
            }
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"[TextCorrector] Error: {e} (took {duration:.2f}ms), returning original text")
            print(f"DEBUG [TextCorrectorClient]: EXCEPTION: {e}")
            return {
                'corrected_text': raw_text,
                'success': False
            }


class FAISSClient:
    """
    Client for FAISS retrieval service.
    Receives product IDs in ranked order and returns them to search service.
    """
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or FAISS_SERVICE_URL
        # Separate URL for add-product endpoint
        self.add_product_url = os.getenv('FAISS_ADD_PRODUCT_URL', 'http://localhost:5002/api/retrieval/add-product')
        # Separate URLs for specific search types
        self.text_search_url = os.getenv('FAISS_TEXT_SEARCH_URL', 'http://localhost:5002/api/retrieval/search/text')
        self.late_fusion_url = os.getenv('FAISS_LATE_FUSION_URL', 'http://localhost:5002/api/retrieval/search/late')
    
    def search(
        self, 
        query_text: str, 
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Send query to FAISS service and get ranked product IDs.
        
        API Contract:
            POST { "query": corrected_text, "top_k": 20 } ->
                { "products": [ { "product_id": 123, "score": 0.98 }, ... ] }
        
        Args:
            query_text: Corrected/normalized search query
            top_k: Number of results to return
            
        Returns:
            dict with:
                - products: List of product matches with scores (in FAISS ranking order)
                    - product_id: Product ID
                    - score: Similarity score (0-1)
                - success: Whether the call succeeded
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
            
            # FAISS returns product_ids in ranked order
            products = result.get('products', [])
            duration = (time.time() - start_time) * 1000
            
            if not products:
                logger.info(f"[FAISS] Query: '{query_text}' -> empty results (took {duration:.2f}ms), will fallback")
                return {'products': [], 'success': False}
            
            logger.info(f"[FAISS] Query: '{query_text}' -> {len(products)} results (took {duration:.2f}ms)")
            
            return {
                'products': products,
                'success': True
            }
        except requests.exceptions.ConnectionError:
            duration = (time.time() - start_time) * 1000
            logger.warning(f"[FAISS] Service not available at {self.base_url} (took {duration:.2f}ms), will fallback to DB")
            return {'products': [], 'success': False}
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"[FAISS] Error: {e} (took {duration:.2f}ms), will fallback to DB")
            return {'products': [], 'success': False}
    
    def search_text(
        self,
        text: str,
        textual_model_name: str = "ViT-B/32",
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Perform text-only search via FAISS service.
        
        Args:
            text: Search query text
            textual_model_name: Model to use for encoding
            top_k: Number of results
            
        Returns:
            dict with results and meta
        """
        print(f"DEBUG [FAISSClient]: search_text called with text='{text}'")
        if not HAS_REQUESTS:
            logger.warning("[FAISS] requests library not installed")
            print("DEBUG [FAISSClient]: requests library missing")
            return {'status': 'error', 'error': 'requests library missing'}
            
        try:
            logger.info(f"[FAISS] Text search: '{text}' (model={textual_model_name})")
            payload = {
                'text': text,
                'textual_model_name': textual_model_name,
                'top_k': top_k
            }
            print(f"DEBUG [FAISSClient]: POST {self.text_search_url} payload={payload}")
            response = requests.post(
                self.text_search_url,
                json=payload,
                timeout=10
            )
            print(f"DEBUG [FAISSClient]: Response status={response.status_code}")
            
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', response.text)
                except:
                    error_msg = response.text
                
                logger.error(f"[FAISS] Text search failed: {response.status_code} - {error_msg}")
                print(f"DEBUG [FAISSClient]: Error response: {error_msg}")
                return {'status': 'error', 'error': f"FAISS Error ({response.status_code}): {error_msg}"}

            result = response.json()
            print(f"DEBUG [FAISSClient]: Response body={result}")
            
            if result.get('status') == 'success' or result.get('success', False):
                return result
            else:
                error = result.get('error', 'Unknown error from FAISS service')
                logger.error(f"[FAISS] Text search failed: {error}")
                print(f"DEBUG [FAISSClient]: Failed status in body: {error}")
                return {'status': 'error', 'error': error}

        except Exception as e:
            logger.error(f"[FAISS] Text search error: {e}")
            print(f"DEBUG [FAISSClient]: EXCEPTION: {e}")
            return {'status': 'error', 'error': str(e)}

    def search_late_fusion(
        self,
        text: str,
        image_path: str,
        text_weight: float = 0.5,
        textual_model_name: str = "ViT-B/32",
        visual_model_name: str = "ViT-B/32",
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Perform late fusion search (text + image) via FAISS service.
        
        Args:
            text: Search query text
            image_path: Absolute path to query image
            text_weight: Weight for text score (0.0 to 1.0)
            textual_model_name: Model for text encoding
            visual_model_name: Model for image encoding
            top_k: Number of results
            
        Returns:
            dict with results and meta
        """
        print(f"DEBUG [FAISSClient]: search_late_fusion called with text='{text}', image='{image_path}'")
        if not HAS_REQUESTS:
            logger.warning("[FAISS] requests library not installed")
            print("DEBUG [FAISSClient]: requests library missing")
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
            print(f"DEBUG [FAISSClient]: POST {self.late_fusion_url} payload={payload}")
            response = requests.post(
                self.late_fusion_url,
                json=payload,
                timeout=15
            )
            print(f"DEBUG [FAISSClient]: Response status={response.status_code}")
            
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', response.text)
                except:
                    error_msg = response.text
                
                logger.error(f"[FAISS] Late fusion search failed: {response.status_code} - {error_msg}")
                print(f"DEBUG [FAISSClient]: Error response: {error_msg}")
                return {'status': 'error', 'error': f"FAISS Error ({response.status_code}): {error_msg}"}

            result = response.json()
            print(f"DEBUG [FAISSClient]: Response body={result}")
            
            if result.get('status') == 'success' or result.get('success', False):
                return result
            else:
                error = result.get('error', 'Unknown error from FAISS service')
                logger.error(f"[FAISS] Late fusion search failed: {error}")
                print(f"DEBUG [FAISSClient]: Failed status in body: {error}")
                return {'status': 'error', 'error': error}

        except Exception as e:
            logger.error(f"[FAISS] Late fusion search error: {e}")
            print(f"DEBUG [FAISSClient]: EXCEPTION: {e}")
            return {'status': 'error', 'error': str(e)}

    def add_product(
        self,
        product_id: str,
        image_paths: List[str],
        textual_model: str = "ViT-B/32",
        visual_model: str = "ViT-B/32",
        fused_model_name: str = "ViT-B/32",
        name: str = "",
        description: str = "",
        brand: str = "",
        category: str = "",
        price: float = 0.0
    ) -> Dict[str, Any]:
        """
        Add a product to FAISS indices (textual and visual).
        
        API Contract:
            POST /api/add-product {
                "id": "product_001",
                "name": "...",
                "description": "...",
                "brand": "...",
                "category": "...",
                "price": 299.99,
                "images": ["C:/path/to/image1.jpg", "C:/path/to/image2.jpg"],
                "textual_model_name": "ViT-B/32",
                "visual_model_name": "ViT-B/32",
                "fused_model_name": "ViT-B/32"
            }
            
            Response:
            {
                "success": true,
                "data": {
                    "product_id": "product_001",
                    "textual_vector_id": 0,
                    "visual_vector_ids": [0, 1],
                    "images_processed": 2
                }
            }
        
        Args:
            product_id: Unique product identifier
            image_paths: List of absolute paths to product images
            textual_model: Model name for text encoding (e.g., "ViT-B/32")
            visual_model: Model name for image encoding (e.g., "ViT-B/32")
            fused_model_name: Model name for fused encoding
            name: Product name
            description: Product description
            brand: Brand name
            category: Category name
            price: Product price
        
        Returns:
            dict with:
                - success: Whether the operation succeeded
                - data: (on success)
                    - product_id: Product ID
                    - textual_vector_id: FAISS index ID for text embedding
                    - visual_vector_ids: List of FAISS index IDs for image embeddings
                    - images_processed: Count of successfully processed images
                - error: (on failure) Error message
        """
        if not HAS_REQUESTS:
            logger.warning("[FAISS] requests library not installed, cannot add product")
            return {
                'success': False,
                'error': 'requests library not installed'
            }
        
        start_time = time.time()
        try:
            logger.info(f"[FAISS] Adding product {product_id} to FAISS at {self.add_product_url}")
            
            # Construct payload matching the user's requested format
            payload = {
                'id': product_id,
                'name': name,
                'description': description,
                'brand': brand,
                'category': category,
                'price': price,
                'images': image_paths,
                'textual_model_name': textual_model,
                'visual_model_name': visual_model,
                'fused_model_name': fused_model_name
            }
            
            response = requests.post(
                self.add_product_url,
                json=payload,
                timeout=30  # Longer timeout for image processing
            )
            
            if response.status_code not in [200, 201]:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', response.text)
                except:
                    error_msg = response.text
                
                logger.error(f"[FAISS] Failed to add product {product_id}: {response.status_code} - {error_msg}")
                return {
                    'success': False,
                    'error': f"FAISS Error ({response.status_code}): {error_msg}"
                }
                
            result = response.json()
            
            duration = (time.time() - start_time) * 1000
            
            if result.get('success', False) or result.get('status') == 'success':
                data = result.get('data', {})
                if not data and 'details' in result:
                    data = result['details']
                    
                logger.info(
                    f"[FAISS] Successfully added product {product_id} "
                    f"(text_id={data.get('textual_vector_id')}, "
                    f"visual_ids={data.get('visual_vector_ids')}, "
                    f"took {duration:.2f}ms)"
                )
                # Ensure we return a format compatible with what we expect
                if 'data' not in result and 'details' in result:
                    result['data'] = result['details']
                result['success'] = True
                return result
            else:
                error = result.get('error', 'Unknown error from FAISS service')
                logger.error(f"[FAISS] Failed to add product {product_id}: {error} (took {duration:.2f}ms)")
                return {
                    'success': False,
                    'error': error
                }
                
        except requests.exceptions.ConnectionError:
            duration = (time.time() - start_time) * 1000
            logger.error(f"[FAISS] Service not available at {self.add_product_url} (took {duration:.2f}ms)")
            return {
                'success': False,
                'error': 'FAISS service not available'
            }
        except requests.exceptions.Timeout:
            duration = (time.time() - start_time) * 1000
            logger.error(f"[FAISS] Request timeout adding product {product_id} (took {duration:.2f}ms)")
            return {
                'success': False,
                'error': 'Request timeout - image processing may have failed'
            }
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"[FAISS] Error adding product {product_id}: {e} (took {duration:.2f}ms)")
            return {
                'success': False,
                'error': str(e)
            }


# Singleton instances
text_corrector = TextCorrectorClient()
faiss_client = FAISSClient()
