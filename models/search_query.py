"""
SearchQuery model for logging search queries.
"""
from datetime import datetime, timezone
from . import db


class SearchQuery(db.Model):
    """Search query model for logging and analytics."""

    __tablename__ = 'search_query'

    search_id = db.Column(db.BigInteger, primary_key=True)
    raw_text = db.Column(db.Text, nullable=False)
    corrected_text = db.Column(db.Text, nullable=True)
    query_image_path = db.Column(db.Text, nullable=True)
    search_mode = db.Column(db.String(10), nullable=True, default='std')
    correction_enabled = db.Column(db.Boolean, nullable=True, default=True)
    type = db.Column(db.String(50), nullable=True)  # 'text', 'voice', 'image'
    time_to_retrieve = db.Column(db.Integer, nullable=True)  # ms
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    retrieves = db.relationship(
        'Retrieve', 
        back_populates='search_query', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='Retrieve.search_id'
    )

    def __repr__(self):
        return f'<SearchQuery {self.search_id}: {self.raw_text[:50]}...>'

    def to_dict(self, include_results=False):
        """
        Convert search query object to dictionary.
        
        Args:
            include_results (bool): Whether to include retrieval results.
            
        Returns:
            dict: Dictionary containing search query details.
        """
        result = {
            'search_id': self.search_id,
            'raw_text': self.raw_text,
            'corrected_text': self.corrected_text,
            'query_image_path': self.query_image_path,
            'search_mode': self.search_mode or 'std',
            'correction_enabled': True if self.correction_enabled is None else self.correction_enabled,
            'type': self.type,
            'time_to_retrieve': self.time_to_retrieve,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

        if include_results:
            result['results'] = [r.to_dict() for r in self.retrieves]

        return result
