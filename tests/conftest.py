import os
import re
import sys
import pytest
from flask import Flask
from flask_cors import CORS
from sqlalchemy import BigInteger, Integer, event

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.app_config import TestingConfig
from models import db as _db


_TEST_CASE_PATTERN = re.compile(
    r"^\|\s*(BU-[A-Z0-9]+-\d+)\s*\|.*?Run `([^`]+)` with pytest",
    re.MULTILINE,
)


def _load_backend_test_case_ids():
    backend_doc_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'backend.md')
    )

    try:
        with open(backend_doc_path, encoding='utf-8') as backend_doc:
            content = backend_doc.read()
    except OSError:
        return {}

    return {
        nodeid.replace('\\', '/'): test_id
        for test_id, nodeid in _TEST_CASE_PATTERN.findall(content)
    }


def _get_selected_test_ids(config):
    selected_test_ids = set()
    for test_id_arg in config.getoption('test_ids') or []:
        selected_test_ids.update(
            test_id.strip() for test_id in test_id_arg.split(',') if test_id.strip()
        )
    return selected_test_ids


def pytest_addoption(parser):
    parser.addoption(
        '--test-id',
        action='append',
        dest='test_ids',
        metavar='ID',
        help='Run only tests linked to the given backend.md test-case ID',
    )


def pytest_configure(config):
    config.addinivalue_line(
        'markers',
        'test_id(id): backend.md test-case ID linked to this pytest case',
    )


def pytest_collection_modifyitems(config, items):
    test_case_ids = _load_backend_test_case_ids()
    selected_test_ids = _get_selected_test_ids(config)
    selected_items = []
    deselected_items = []

    for item in items:
        nodeid = item.nodeid.replace('\\', '/').split('[', 1)[0]
        test_id = test_case_ids.get(nodeid)
        if test_id:
            item.add_marker(pytest.mark.test_id(test_id))
            item.user_properties.append(('test_id', test_id))

        if not selected_test_ids:
            continue

        if test_id in selected_test_ids:
            selected_items.append(item)
        else:
            deselected_items.append(item)

    if selected_test_ids:
        config.hook.pytest_deselected(items=deselected_items)
        items[:] = selected_items


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
