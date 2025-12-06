"""
Category model with self-referencing hierarchy.
"""
from . import db


class Category(db.Model):
    """Category model with parent-child hierarchy."""
    
    __tablename__ = 'category'
    
    category_id = db.Column(db.BigInteger, primary_key=True)
    parent_category_id = db.Column(
        db.BigInteger, 
        db.ForeignKey('category.category_id', ondelete='SET NULL'),
        nullable=True
    )
    name = db.Column(db.String(255), nullable=False)
    
    # Self-referencing relationships
    parent = db.relationship(
        'Category', 
        remote_side=[category_id],
        backref=db.backref('children', lazy='dynamic')
    )
    
    # Many-to-many relationship with products
    products = db.relationship(
        'Product',
        secondary='product_category',
        back_populates='categories',
        lazy='dynamic'
    )
    
    def __repr__(self):
        return f'<Category {self.name}>'
    
    def to_dict(self, include_parent=False, include_children=False):
        """
        Convert category object to dictionary.
        
        Args:
            include_parent (bool): Whether to include parent category details.
            include_children (bool): Whether to include child categories.
            
        Returns:
            dict: Dictionary containing category details.
        """
        result = {
            'category_id': self.category_id,
            'parent_category_id': self.parent_category_id,
            'name': self.name
        }
        
        if include_parent and self.parent:
            result['parent'] = self.parent.to_dict()
        
        if include_children:
            result['children'] = [c.to_dict() for c in self.children]
        
        return result
