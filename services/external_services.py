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
FAISS_SERVICE_URL = os.getenv('FAISS_SERVICE_URL', 'http://localhost:5002/api/search')


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
        if not HAS_REQUESTS:
            logger.warning("[TextCorrector] requests library not installed, returning original text")
            return {
                'corrected_text': raw_text,
                'success': False
            }
        
        start_time = time.time()
        try:
            logger.info(f"[TextCorrector] Calling service at {self.base_url} with text: '{raw_text}'")
            response = requests.post(
                self.base_url,
                json={'query': raw_text, 'model': 'symspell'},
                timeout=5
            )
            response.raise_for_status()
            result = response.json()
            
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
            return {
                'corrected_text': raw_text,
                'success': False
            }
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"[TextCorrector] Error: {e} (took {duration:.2f}ms), returning original text")
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
    
    def search(
        self, 
        query_text: str, 
        top_k: int = 20
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


# Singleton instances
text_corrector = TextCorrectorClient()
faiss_client = FAISSClient()
