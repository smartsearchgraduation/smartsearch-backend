"""
Retrieve model for storing search results/logs.
"""
from . import db


class Retrieve(db.Model):
    """Retrieve model for logging search results and user interactions."""
    
    __tablename__ = 'retrieve'
    
    search_id = db.Column(
        db.BigInteger, 
        db.ForeignKey('search_query.search_id', ondelete='CASCADE'),
        primary_key=True
    )
    product_id = db.Column(
        db.BigInteger, 
        db.ForeignKey('product.product_id', ondelete='CASCADE'),
        primary_key=True
    )
    rank = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=True)  # similarity score
    explain = db.Column(db.Text, nullable=True)  # explanation JSON
    is_relevant = db.Column(db.Boolean, nullable=True)  # user feedback
    is_clicked = db.Column(db.Boolean, nullable=True)  # click tracking
    embedding_id = db.Column(db.String(100), nullable=True)
    

    
    # Raw text search tracking
    rawtext_used = db.Column(db.Boolean, nullable=True, default=False)
    new_search_id = db.Column(
        db.BigInteger,
        db.ForeignKey('search_query.search_id', ondelete='SET NULL'),
        nullable=True
    )

    # Model tracking - which models were used for this retrieval
    textual_model_name = db.Column(db.String(100), nullable=True)
    visual_model_name = db.Column(db.String(100), nullable=True)
    
    # Correction engine tracking - which spell correction engine was used
    correction_engine = db.Column(db.String(50), nullable=True)
    
    # Relationships
    search_query = db.relationship(
        'SearchQuery', 
        back_populates='retrieves',
        foreign_keys='Retrieve.search_id'
    )
    new_search = db.relationship(
        'SearchQuery',
        foreign_keys='Retrieve.new_search_id'
    )
    product = db.relationship('Product', back_populates='retrieves')
    
    def __repr__(self):
        return f'<Retrieve search={self.search_id} product={self.product_id} rank={self.rank}>'
    
    def to_dict(self, include_product=False):
        """
        Convert retrieve object to dictionary.

        Args:
            include_product (bool): Whether to include product details.

        Returns:
            dict: Dictionary containing retrieval details.
        """
        result = {
            'search_id': self.search_id,
            'product_id': self.product_id,
            'rank': self.rank,
            'weight': self.weight,
            'explain': self.explain,
            'is_relevant': self.is_relevant,
            'is_clicked': self.is_clicked,
            'embedding_id': self.embedding_id,
            'rawtext_used': self.rawtext_used,
            'new_search_id': self.new_search_id,
            'textual_model_name': self.textual_model_name,
            'visual_model_name': self.visual_model_name,
            'correction_engine': self.correction_engine
        }

        if include_product and self.product:
            result['product'] = self.product.to_dict(include_images=False)

        return result
