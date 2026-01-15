"""
Analytics endpoint for receiving client-side metrics.
"""
from flask import Blueprint, request, jsonify
from services.search_service import SearchService
from models.search_time import SearchTime
import logging

analytics_bp = Blueprint('analytics', __name__)
logger = logging.getLogger(__name__)

@analytics_bp.route('/search-duration', methods=['POST'])
def record_search_duration():
    """
    Record client-side search performance metrics.
    
    Expected JSON body:
    {
        "search_id": 123,
        "search_duration": 1234,      # ms
        "product_load_duration": 12345 # ms
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        search_id = data.get('search_id')
        search_duration = data.get('search_duration')
        product_load_duration = data.get('product_load_duration')
        
        if search_id is None or search_duration is None or product_load_duration is None:
            return jsonify({'error': 'Missing required fields'}), 400
            
        success = SearchService.update_client_metrics(
            search_id=search_id,
            search_duration=float(search_duration),
            product_load_duration=float(product_load_duration)
        )
        
        if success:
            return jsonify({'status': 'success', 'message': 'Metrics updated'}), 200
        else:
            return jsonify({'error': 'Failed to update metrics', 'details': 'Search ID not found or error'}), 404
            
    except Exception as e:
        logger.error(f"Error in analytics endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@analytics_bp.route('/logs', methods=['GET'])
def get_all_logs():
    """
    Get all search time logs.
    """
    try:
        logs = SearchTime.query.all()
        return jsonify([log.to_dict() for log in logs]), 200
    except Exception as e:
        logger.error(f"Error fetching all logs: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@analytics_bp.route('/logs/<int:search_id>', methods=['GET'])
def get_log_by_id(search_id):
    """
    Get search time log by search_id.
    """
    try:
        log = SearchTime.query.get(search_id)
        if not log:
            return jsonify({'error': 'Log not found'}), 404
            
        return jsonify(log.to_dict()), 200
    except Exception as e:
        logger.error(f"Error fetching log for {search_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500
