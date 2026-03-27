"""
SmartSearch Backend - the main Flask application.
This is the middle layer that connects the frontend UI to the FAISS-based
product search pipeline.
"""
import os
import logging
import sys
from flask import Flask, send_from_directory
from flask_cors import CORS

from config import get_config
from models import db

# Configure logging to show all service logs in console
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Make sure our service loggers are enabled
logging.getLogger('services.search_service').setLevel(logging.INFO)
logging.getLogger('services.faiss_retrieval_service').setLevel(logging.INFO)
logging.getLogger('services.text_corrector_service').setLevel(logging.INFO)


def create_app(config_class=None):
    """Create and configure the Flask app."""
    app = Flask(__name__)
    
    # Load config from environment or use defaults
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)
    
    # Set up database and allow cross-origin requests
    db.init_app(app)
    CORS(app, origins="*")
    
    # Let the frontend access uploaded product images directly
    @app.route('/uploads/products/<filename>')
    def serve_product_image(filename):
        """Let users view uploaded product images."""
        upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads/products')
        return send_from_directory(upload_folder, filename)
    
    # Hook up all our API route handlers
    from routes import (
        search_bp,
        products_bp,
        feedback_bp,
        health_bp,
        brands_bp,
        categories_bp,
        retrieval_bp,
        analytics_bp,
        bulk_faiss_bp,
        correction_bp
    )

    app.register_blueprint(search_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(brands_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(retrieval_bp)
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(bulk_faiss_bp)
    app.register_blueprint(correction_bp)
    
    # Create database tables if they don't exist
    with app.app_context():
        # In production, you'd use Flask-Migrate for database migrations
        # db.create_all()  # Uncomment if you want auto-create tables
        pass
    
    return app


# Create the app instance for when this file is run directly
app = create_app()


if __name__ == '__main__':
    print(" Starting SmartSearch Backend...")
    print(" Available endpoints:")
    print("   POST   /api/search")
    print("   GET    /api/search/<id>")
    print("   POST   /api/feedback")
    print("   POST   /api/click")
    print("   GET    /api/metrics")
    print("   GET    /api/products")
    print("   POST   /api/products")
    print("   GET    /api/products/<id>")
    print("   PUT    /api/products/<id>")
    print("   DELETE /api/products/<id>")
    print("   GET    /api/products/<id>/images")
    print("   POST   /api/products/<id>/images   (file upload)")
    print("   DELETE /api/products/<id>/images/<image_no>")
    print("   GET    /api/brands")
    print("   POST   /api/brands")
    print("   GET    /api/categories")
    print("   POST   /api/categories")
    print("   POST   /api/retrieval/add-product   (FAISS)")
    print("   PUT    /api/retrieval/update-product/<product_id>   (FAISS)")
    print("   DELETE /api/retrieval/delete-product/<product_id>   (FAISS)")
    print("   GET    /api/retrieval/index-stats   (FAISS Index Statistics)")
    print("   GET    /api/retrieval/stats         (System Statistics)")
    print("   GET    /api/retrieval/models        (Available Models)")
    print("   POST   /api/retrieval/search/text   (FAISS Text)")
    print("   POST   /api/retrieval/search/late   (FAISS Late Fusion)")
    print("   DELETE /api/retrieval/clear-index   (FAISS Clear Index)")
    print("   POST   /api/retrieval/test-product  (FAISS Test Product)")
    print("   GET    /api/correction/models       (Correction Models)")
    print("   POST   /api/analytics/search-duration (Client Metrics)")
    print("   GET    /api/bulk-faiss/             (Web UI - FAISS Bulk Import)")
    print("   GET    /api/bulk-faiss/stats        (Get Import Stats)")
    print("   POST   /api/bulk-faiss/add-all      (Add All Products to FAISS)")
    print("   POST   /api/bulk-faiss/rebuild-with-test (Rebuild Index + Test)")
    print("   GET    /health")
    print("   GET    /uploads/products/<filename>   (serve images)")
    print(f" Database: {app.config['SQLALCHEMY_DATABASE_URI'].split('@')[1] if '@' in app.config['SQLALCHEMY_DATABASE_URI'] else 'N/A'}")
    app.run(debug=True, host='0.0.0.0', port=5000)
