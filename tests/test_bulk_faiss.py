import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from config.app_config import TestingConfig
from models import db, Product, Brand


@pytest.fixture(scope='module')
def bulk_app():
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    app.config['TESTING'] = True
    app.config['UPLOAD_FOLDER'] = '/tmp/test_uploads'
    db.init_app(app)

    from routes.bulk_faiss import bulk_faiss_bp
    app.register_blueprint(bulk_faiss_bp)

    with app.app_context():
        db.create_all()
    yield app


@pytest.fixture
def client(bulk_app):
    with bulk_app.test_client() as c:
        with bulk_app.app_context():
            yield c


@pytest.fixture
def ctx(bulk_app):
    with bulk_app.app_context():
        yield


class TestBulkFAISS:

    @patch('routes.bulk_faiss.faiss_service')
    @patch('time.sleep', return_value=None)
    def test_bulk_add_all_iterates_products(self, mock_sleep, mock_faiss, ctx, client):
        mock_faiss.get_available_models.return_value = {
            'status': 'success',
            'data': {
                'defaults': {'textual': 'ViT-B/32', 'visual': 'ViT-B/32'},
            },
        }
        mock_faiss.get_available_model_ids.return_value = ['ViT-B/32']
        mock_faiss.clear_index.return_value = {'status': 'success', 'details': {}}
        mock_faiss.add_product.return_value = {
            'status': 'success',
            'details': {'textual_vector_id': 'abc', 'visual_vector_ids': ['v1']},
        }

        Brand.query.delete()
        Product.query.delete()
        db.session.commit()
        brand = Brand(name='Test Brand')
        db.session.add(brand)
        db.session.flush()
        product = Product(name='Test Product', price=10.0, brand_id=brand.brand_id)
        db.session.add(product)
        db.session.commit()

        response = client.post('/api/bulk-faiss/add-all', json={
            'wait_duration_seconds': 0,
        })
        assert response.status_code == 200, response.get_json()
        data = response.get_json()
        assert data['details']['successful_count'] >= 1

    @patch('routes.bulk_faiss.faiss_service')
    @patch('time.sleep', return_value=None)
    def test_bulk_rebuild_with_test_clears_and_readds(self, mock_sleep, mock_faiss, ctx, client):
        mock_faiss.get_available_models.return_value = {
            'status': 'success',
            'data': {
                'defaults': {'textual': 'ViT-B/32', 'visual': 'ViT-B/32'},
            },
        }
        mock_faiss.get_available_model_ids.return_value = ['ViT-B/32']
        mock_faiss.add_test_product.return_value = {'status': 'success', 'details': {}}
        mock_faiss.add_product.return_value = {
            'status': 'success',
            'details': {'textual_vector_id': 'abc', 'visual_vector_ids': ['v1']},
        }

        Brand.query.delete()
        Product.query.delete()
        db.session.commit()
        brand = Brand(name='Test Brand')
        db.session.add(brand)
        db.session.flush()
        product = Product(name='Test Product', price=10.0, brand_id=brand.brand_id)
        db.session.add(product)
        db.session.commit()

        response = client.post('/api/bulk-faiss/rebuild-with-test', json={
            'wait_duration_seconds': 0,
            'wait_after_first': False,
        })
        assert response.status_code == 200, response.get_json()
        data = response.get_json()
        assert 'steps' in data

    @patch('requests.get')
    def test_bulk_stats_returns_import_statistics(self, mock_get, ctx, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        Brand.query.delete()
        Product.query.delete()
        db.session.commit()
        brand = Brand(name='Stats Brand')
        db.session.add(brand)
        db.session.flush()
        product = Product(name='Stats Product', price=10.0, brand_id=brand.brand_id)
        db.session.add(product)
        db.session.commit()

        response = client.get('/api/bulk-faiss/stats')
        assert response.status_code == 200
        data = response.get_json()
        assert 'total_products' in data
        assert 'total_images' in data
        assert 'faiss_available' in data

    def test_models_endpoint(self, ctx, client):
        r = client.get('/api/bulk-faiss/models')
        assert r.status_code == 200
        data = r.get_json()
        assert 'models' in data
        assert 'defaults' in data

    def test_stats_faiss_unavailable(self, ctx, client):
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception('refused')
            r = client.get('/api/bulk-faiss/stats')
            assert r.status_code == 200
            assert r.get_json()['faiss_available'] is False

    def test_web_ui_page(self, ctx, client):
        r = client.get('/api/bulk-faiss/')
        assert r.status_code == 200
        assert 'text/html' in r.content_type

    def test_stats_faiss_unavailable_exception(self, ctx, client):
        with patch('requests.get') as mg: mg.side_effect = Exception('err')
        r = client.get('/api/bulk-faiss/stats')
        assert r.status_code == 200 and r.get_json()['faiss_available'] is False

    def test_web_ui_contains_models(self, ctx, client):
        html = client.get('/api/bulk-faiss/').get_data(as_text=True)
        assert 'ViT-B/32' in html
