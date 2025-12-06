"""
Database models package.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import all models after db is defined
from .brand import Brand
from .category import Category
from .product import Product
from .product_image import ProductImage
from .product_category import ProductCategory
from .search_query import SearchQuery
from .retrieve import Retrieve

__all__ = [
    'db',
    'Brand',
    'Category', 
    'Product',
    'ProductImage',
    'ProductCategory',
    'SearchQuery',
    'Retrieve'
]
