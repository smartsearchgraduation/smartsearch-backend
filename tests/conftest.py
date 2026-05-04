import os
import sys
import pytest
from flask import Flask
from flask_cors import CORS
from sqlalchemy import BigInteger, Integer, event

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.app_config import TestingConfig
from models import db as _db


# Fix BigInteger autoincrement for SQLite - must be set up before any create_all()
@event.listens_for(_db.metadata, 'before_create')
def _bigint_to_int_for_sqlite(target, connection, **kw):
    if connection.engine.dialect.name == 'sqlite':
        for table in target.tables.values():
            for column in table.columns:
                if isinstance(column.type, BigInteger):
                    column.type = Integer()


@pytest.fixture(scope='session')
def app():
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    app.config['UPLOAD_FOLDER'] = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'test_uploads'
    )
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    _db.init_app(app)
    CORS(app, origins="*")

    from routes import (
        search_bp, products_bp, feedback_bp, health_bp,
        brands_bp, categories_bp, retrieval_bp, analytics_bp,
        bulk_faiss_bp, correction_bp
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

    @app.route('/uploads/products/<filename>')
    def serve_product_image(filename):
        from flask import send_from_directory
        upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads/products')
        return send_from_directory(upload_folder, filename)

    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(scope='function')
def db_session(app):
    with app.app_context():
        yield _db.session
