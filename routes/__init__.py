"""
Routes package - Flask Blueprints.
"""
from .search import search_bp
from .products import products_bp
from .feedback import feedback_bp
from .health import health_bp
from .brands import brands_bp
from .categories import categories_bp

__all__ = [
    'search_bp',
    'products_bp',
    'feedback_bp',
    'health_bp',
    'brands_bp',
    'categories_bp'
]
