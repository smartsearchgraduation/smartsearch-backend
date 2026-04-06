"""
Product model.
"""
from datetime import datetime, timezone
from . import db


class Product(db.Model):
    """Product model representing items in the catalog."""
    
    __tablename__ = 'product'
    
    product_id = db.Column(db.BigInteger, primary_key=True)
    brand_id = db.Column(
        db.BigInteger, 
        db.ForeignKey('brand.brand_id', ondelete='SET NULL'),
        nullable=True
    )
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    brand = db.relationship('Brand', back_populates='products')
    images = db.relationship('ProductImage', back_populates='product', lazy='select', cascade='all, delete-orphan')
    categories = db.relationship(
        'Category',
        secondary='product_category',
        back_populates='products',
        lazy='dynamic'
    )
    retrieves = db.relationship('Retrieve', back_populates='product', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Product {self.name}>'
    
    def to_dict(self, include_brand=True, include_categories=True, include_images=True):
        """
        Convert product object to dictionary.
        
        Args:
            include_brand (bool): Whether to include brand details.
            include_categories (bool): Whether to include category details.
            include_images (bool): Whether to include product images.
            
        Returns:
            dict: Dictionary containing product details.
        """
        result = {
            'product_id': self.product_id,
            'brand_id': self.brand_id,
            'name': self.name,
            'description': self.description,
            'price': float(self.price) if self.price else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_brand and self.brand:
            result['brand'] = self.brand.to_dict()
        
        if include_categories:
            result['categories'] = [c.to_dict(include_parent=True) for c in self.categories]
        
        if include_images:
            result['images'] = [img.to_dict() for img in self.images]
        
        return result
