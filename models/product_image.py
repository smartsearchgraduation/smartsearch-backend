"""
ProductImage model.
"""
from datetime import datetime
from . import db


class ProductImage(db.Model):
    """Product image model for storing product images."""
    
    __tablename__ = 'product_image'
    
    image_no = db.Column(db.BigInteger, primary_key=True)
    product_id = db.Column(
        db.BigInteger, 
        db.ForeignKey('product.product_id', ondelete='CASCADE'),
        nullable=False
    )
    url = db.Column(db.Text, nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Relationships
    product = db.relationship('Product', back_populates='images')
    
    def __repr__(self):
        return f'<ProductImage {self.image_no} for Product {self.product_id}>'
    
    def to_dict(self):
        """
        Convert product image object to dictionary.
        
        Returns:
            dict: Dictionary containing image details.
        """
        return {
            'image_no': self.image_no,
            'product_id': self.product_id,
            'url': self.url,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }
