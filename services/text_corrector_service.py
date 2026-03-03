"""
This module provides the TextCorrectorService, which manages connections to 
external microservices for spell-checking and typo correction.
"""
import os
import time
import logging
from typing import Dict, Any, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger(__name__)

# Service URLs from environment
CORRECTION_SERVICE_URL = os.getenv('CORRECTION_SERVICE_URL', 'http://localhost:5001/correct')

# Available correction engines
ENGINE_SYMSPELL = 'symspell_keyboard'
ENGINE_BYT5 = 'byt5'
DEFAULT_ENGINE = ENGINE_BYT5


class TextCorrectorService:
    """
    A simple service for the text correction microservice.
    
    This fixes typos and spelling mistakes in search queries before we send
    them to FAISS. For example, "iphnoe" becomes "iphone".
    
    Supports two engines:
    - symspell_keyboard: Fast, dictionary-based correction
    - byt5_finetuned: ML-based correction using fine-tuned ByT5 model
    """
    
    def __init__(self, base_url: str = None, default_engine: str = None):
        self.base_url = base_url or CORRECTION_SERVICE_URL
        self.default_engine = default_engine or DEFAULT_ENGINE
    
    def correct(self, raw_text: str, engine: Optional[str] = None) -> Dict[str, Any]:
        """
        Fix any typos or spelling mistakes in the search query.
        
        Sends the raw text to our correction service and returns the cleaned-up
        version. If the service is down, we just return the original text
        so searches still work (just without spell correction).
        
        Args:
            raw_text: The user's original search query, typos and all
            engine: Which correction engine to use ('symspell_keyboard' or 'byt5')
                   Defaults to 'symspell_keyboard' if not specified
        
        Returns:
            A dict with 'corrected_text', 'success' flag, 'changed', and 'latency_ms'
        """
        if not HAS_REQUESTS:
            logger.warning("[TextCorrector] requests library not installed, returning original text")
            return {
                'corrected_text': raw_text,
                'success': False,
                'changed': False,
                'latency_ms': 0
            }
        
        # Map common engine names to internal constants
        engine_map = {
            'symspell': ENGINE_SYMSPELL,
            'symspell_keyboard': ENGINE_SYMSPELL,
            'byt5': ENGINE_BYT5
        }
        
        # Use specified engine, map it if possible, otherwise use as-is or default
        correction_engine = engine_map.get(engine, engine) if engine else self.default_engine
        
        start_time = time.time()
        try:
            logger.debug(f"📥 POST /correct - New correction request")
            logger.debug(f"   📝 Query: '{raw_text}'")
            logger.debug(f"   🔧 Model: {correction_engine}")
            
            # New API format
            request_payload = {
                'query': raw_text,
                'model': correction_engine,
            }
            
            response = requests.post(
                self.base_url,
                json=request_payload,
                timeout=10  # Increased timeout for ML model
            )
            response.raise_for_status()
            result = response.json()
            
            # Parse new response format according to user's specified structure
            # response_json = { "original_query": ..., "corrected_query": ..., 
            #                   "changed": ..., "model_used": ..., "latency_ms": ... }
            corrected_text = result.get('corrected_query', result.get('corrected', raw_text))
            changed = result.get('changed', False)
            latency_ms = result.get('latency_ms', 0)
            actual_model = result.get('model_used', correction_engine)
            
            logger.debug(f"📤 Response:")
            logger.debug(f"   📝 Original:  '{raw_text}'")
            logger.debug(f"   ✏️  Corrected: '{corrected_text}'")
            logger.debug(f"   🔄 Changed:   {changed}")
            logger.debug(f"   ⏱️  Latency:   {latency_ms:.2f}ms")
            
            duration = (time.time() - start_time) * 1000
            
            if changed:
                logger.info(f"✅ '{raw_text}' → '{corrected_text}' (engine: {actual_model}, took {duration:.2f}ms)")
            else:
                logger.info(f"ℹ️  No correction needed for '{raw_text}' (engine: {actual_model}, took {duration:.2f}ms)")
            
            return {
                'corrected_text': corrected_text,
                'success': True,
                'changed': changed,
                'latency_ms': duration,
                'engine': actual_model
            }
        except requests.exceptions.ConnectionError:
            duration = (time.time() - start_time) * 1000
            logger.warning(f"[TextCorrector] Service not available at {self.base_url} (took {duration:.2f}ms), returning original text")
            return {
                'corrected_text': raw_text,
                'success': False,
                'changed': False,
                'latency_ms': duration
            }
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"[TextCorrector] Error: {e} (took {duration:.2f}ms), returning original text")
            return {
                'corrected_text': raw_text,
                'success': False,
                'changed': False,
                'latency_ms': duration
            }


# Create a single shared instance for the whole app
text_corrector_service = TextCorrectorService()

