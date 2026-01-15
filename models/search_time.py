"""
SearchTime model for storing performance metrics.
"""
from . import db


class SearchTime(db.Model):
    """Model for logging search performance timing metrics."""
    
    __tablename__ = 'search_time'
    
    search_id = db.Column(
        db.BigInteger, 
        db.ForeignKey('search_query.search_id', ondelete='CASCADE'),
        primary_key=True
    )
    
    # Backend timings (server-side)
    correction_time = db.Column(db.Float, nullable=True)  # ms
    faiss_time = db.Column(db.Float, nullable=True)  # ms
    db_time = db.Column(db.Float, nullable=True)  # ms
    backend_total_time = db.Column(db.Float, nullable=True)  # ms
    
    # Frontend timings (client-side)
    search_duration = db.Column(db.Float, nullable=True)  # ms
    product_load_duration = db.Column(db.Float, nullable=True)  # ms
    
    # Relationships
    search_query = db.relationship(
        'SearchQuery', 
        backref=db.backref('time_metrics', uselist=False, cascade='all, delete-orphan')
    )
    
    def __repr__(self):
        return f'<SearchTime search_id={self.search_id}>'
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'search_id': self.search_id,
            'correction_time': self.correction_time,
            'faiss_time': self.faiss_time,
            'db_time': self.db_time,
            'backend_total_time': self.backend_total_time,
            'search_duration': self.search_duration,
            'product_load_duration': self.product_load_duration
        }
