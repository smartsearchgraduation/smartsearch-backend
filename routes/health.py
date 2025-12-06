"""
Health check route blueprint.
"""
from flask import Blueprint, jsonify
from datetime import datetime

from models import db

health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    
    # Check database connection
    db_status = 'healthy'
    try:
        db.session.execute(db.text('SELECT 1'))
    except Exception as e:
        db_status = f'unhealthy: {str(e)}'
    
    return jsonify({
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'service': 'smartsearch-backend',
        'database': db_status,
        'timestamp': datetime.now().isoformat()
    }), 200 if db_status == 'healthy' else 503
