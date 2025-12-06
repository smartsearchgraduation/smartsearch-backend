"""
ProductCategory association table model.
"""
from . import db


class ProductCategory(db.Model):
    """Association table for Product-Category many-to-many relationship."""
    
    __tablename__ = 'product_category'
    
    product_id = db.Column(
        db.BigInteger, 
        db.ForeignKey('product.product_id', ondelete='CASCADE'),
        primary_key=True
    )
    category_id = db.Column(
        db.BigInteger, 
        db.ForeignKey('category.category_id', ondelete='CASCADE'),
        primary_key=True
    )
    
    def __repr__(self):
        return f'<ProductCategory product={self.product_id} category={self.category_id}>'
