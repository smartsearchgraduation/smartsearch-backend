"""
This module provides the TextCorrectorService, which manages connections to 
external microservices for spell-checking and typo correction.
"""
import os
import time
import logging
from typing import Dict, Any

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger(__name__)

# Service URLs from environment
CORRECTION_SERVICE_URL = os.getenv('CORRECTION_SERVICE_URL', 'http://localhost:5001/correct')


class TextCorrectorService:
    """
    A simple service for the text correction microservice.
    
    This fixes typos and spelling mistakes in search queries before we send
    them to FAISS. For example, "ipohne" becomes "iphone".
    """
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or CORRECTION_SERVICE_URL
    
    def correct(self, raw_text: str) -> Dict[str, Any]:
        """
        Fix any typos or spelling mistakes in the search query.
        
        Sends the raw text to our correction service and returns the cleaned-up
        version. If the service is down, we just return the original text
        so searches still work (just without spell correction).
        
        Args:
            raw_text: The user's original search query, typos and all
        
        Returns:
            A dict with 'corrected_text' and 'success' flag
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


# Create a single shared instance for the whole app
text_corrector_service = TextCorrectorService()
