"""
Routes package - Flask Blueprints.
"""
from .search import search_bp
from .products import products_bp
from .feedback import feedback_bp
from .health import health_bp
from .brands import brands_bp
from .categories import categories_bp
from .retrieval import retrieval_bp
from .analytics import analytics_bp

__all__ = [
    'search_bp',
    'products_bp',
    'feedback_bp',
    'health_bp',
    'brands_bp',
    'categories_bp',
    'retrieval_bp',
    'analytics_bp'
]
