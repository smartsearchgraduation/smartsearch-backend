"""
Brand model.
"""
from . import db


class Brand(db.Model):
    """Brand model representing product brands."""
    
    __tablename__ = 'brand'
    
    brand_id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    
    # Relationships
    products = db.relationship('Product', back_populates='brand', lazy='dynamic')
    
    def __repr__(self):
        return f'<Brand {self.name}>'
    
    def to_dict(self):
        """
        Convert brand object to dictionary.
        
        Returns:
            dict: Dictionary containing brand_id and name.
        """
        return {
            'brand_id': self.brand_id,
            'name': self.name
        }
