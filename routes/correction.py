"""
API routes for text correction operations.
Provides endpoints to get available spell-checking and typo correction models.
"""
import logging
from flask import Blueprint, jsonify
from services.text_corrector_service import text_corrector_service

logger = logging.getLogger(__name__)

correction_bp = Blueprint('correction', __name__, url_prefix='/api/correction')


@correction_bp.route('/models', methods=['GET'])
def get_available_models():
    """
    Get the list of available text correction models from the correction service.

    Returns a list of supported spell-checking and typo correction models.
    This endpoint is useful for populating UI dropdowns or validating model selections.

    The response includes:
    - models: List of available correction models with id and name
    - default: Default model selection
    - source: Whether the data came from 'correction_service' or 'local_config'
    """
    try:
        logger.info("[Correction] Fetching available models")

        result = text_corrector_service.get_available_models()

        if result.get('status') == 'error':
            logger.warning(f"[Correction] Models fetch returned error: {result.get('error')}")
            return jsonify(result), 500

        logger.info(f"[Correction] Successfully fetched models from {result.get('source', 'unknown')}")
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"[Correction] Unexpected error fetching models: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500
