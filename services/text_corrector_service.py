"""
This module provides the TextCorrectorService, which manages connections to
external microservices for spell-checking and typo correction.
"""
import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger(__name__)

# Service URLs from environment
CORRECTION_SERVICE_URL = os.getenv('CORRECTION_SERVICE_URL', 'http://127.0.0.1:5001/correct')
CORRECTION_MODELS_URL = os.getenv('CORRECTION_MODELS_URL', 'http://127.0.0.1:5001/models')

# Persisted selection lives next to selected_models.json under config/
SELECTED_ENGINE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'config', 'selected_correction_engine.json')
)

# Available correction engines
ENGINE_SYMSPELL = 'symspell_keyboard'
ENGINE_BYT5 = 'byt5-small'
DEFAULT_ENGINE = ENGINE_BYT5

# Available correction models
AVAILABLE_CORRECTION_MODELS = {
    ENGINE_SYMSPELL: "SymSpell (Hızlı - Keyboard Based)",
    ENGINE_BYT5: "ByT5 Finetuned (ML Model - Daha Doğru)",
}


def _load_persisted_engine() -> Optional[str]:
    try:
        with open(SELECTED_ENGINE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        engine = data.get('engine')
        if isinstance(engine, str) and engine.strip():
            return engine.strip()
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.warning(f"[TextCorrector] Failed to load persisted engine: {e}")
    return None


def _persist_engine(engine: str) -> None:
    payload = {
        'engine': engine,
        'last_updated': datetime.utcnow().isoformat() + 'Z',
    }
    os.makedirs(os.path.dirname(SELECTED_ENGINE_PATH), exist_ok=True)
    with open(SELECTED_ENGINE_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)


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
        self.models_url = CORRECTION_MODELS_URL
        persisted = _load_persisted_engine()
        self.default_engine = default_engine or persisted or DEFAULT_ENGINE
        if persisted:
            logger.info(f"[TextCorrector] Loaded persisted engine: '{persisted}'")
    
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
            'byt5': ENGINE_BYT5,
            'byt5-base': ENGINE_BYT5,
            'byt5-small': 'byt5-small',
            'byt5-large': 'byt5-large',
            'qwen-3.5-2b': 'qwen-3.5-2b',
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

    def get_available_models(self) -> Dict[str, Any]:
        """
        Get the list of available text correction models from the correction service.

        Fetches the supported spell-checking and typo correction models.
        This is useful for populating UI dropdowns or validating model selections.

        Returns:
            Dict with 'models' list containing model objects with 'id' and 'name' fields,
            plus the default model. Falls back to local config if service is unavailable.
        """
        if not HAS_REQUESTS:
            logger.warning("[TextCorrector] requests library not installed, using local config")
            return self._get_local_models()

        try:
            logger.info(f"[TextCorrector] Fetching available models from {self.models_url}")

            response = requests.get(
                self.models_url,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"[TextCorrector] Successfully fetched available models")
                data = result.get('data', result)
                engines = data.get('correction_models', [])
                default_engine = data.get('defaults', {}).get('correction', self.default_engine)
                return {
                    "status": "success",
                    "data": {
                        "engines": engines,
                        "defaults": {"engine": default_engine},
                        "selected_engine": self.default_engine,
                    },
                    "source": "correction_service"
                }
            else:
                logger.warning(f"[TextCorrector] Models endpoint returned {response.status_code}, using local config")
                return self._get_local_models()

        except requests.exceptions.ConnectionError:
            logger.warning(f"[TextCorrector] Service not available at {self.models_url}, using local config")
            return self._get_local_models()
        except requests.exceptions.Timeout:
            logger.warning(f"[TextCorrector] Request timeout fetching models, using local config")
            return self._get_local_models()
        except Exception as e:
            logger.error(f"[TextCorrector] Error fetching models: {e}, using local config")
            return self._get_local_models()

    def save_selected_engine(self, engine: str) -> Dict[str, Any]:
        """Save the selected correction engine as the new default."""
        if not engine or not isinstance(engine, str) or not engine.strip():
            return {
                "status": "error",
                "error": "Invalid engine value",
            }
        engine = engine.strip()
        old = self.default_engine
        self.default_engine = engine
        try:
            _persist_engine(engine)
        except Exception as e:
            logger.error(f"[TextCorrector] Failed to persist engine '{engine}': {e}")
            return {
                "status": "error",
                "error": f"Failed to persist engine: {e}",
            }
        logger.info(f"[TextCorrector] Default engine changed: '{old}' -> '{engine}' (persisted)")
        return {
            "status": "success",
            "message": f"Correction engine saved: {engine}",
            "data": {"engine": engine},
        }

    def _get_local_models(self) -> Dict[str, Any]:
        """
        Get available correction models from local configuration as a fallback.

        Returns:
            Dict with models list from AVAILABLE_CORRECTION_MODELS
        """
        try:
            engines = [
                {"name": model_id, "description": display_name}
                for model_id, display_name in AVAILABLE_CORRECTION_MODELS.items()
            ]

            return {
                "status": "success",
                "data": {
                    "engines": engines,
                    "defaults": {"engine": self.default_engine},
                    "selected_engine": self.default_engine,
                },
                "source": "local_config"
            }
        except Exception as e:
            logger.error(f"[TextCorrector] Error loading local models: {e}")
            return {
                "status": "error",
                "error": f"Failed to load models: {str(e)}"
            }


# Create a single shared instance for the whole app
text_corrector_service = TextCorrectorService()

