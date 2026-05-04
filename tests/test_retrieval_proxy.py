import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

@pytest.fixture
def app():
    a = Flask(__name__); a.config['TESTING'] = True; a.config['UPLOAD_FOLDER'] = '/tmp'
    from routes.retrieval import retrieval_bp; a.register_blueprint(retrieval_bp); return a

@pytest.fixture
def c(app):
    with app.test_client() as cl: yield cl

@pytest.fixture
def mock_svc():
    with patch('routes.retrieval.faiss_service') as m:
        m.search_text.return_value = {'status': 'success', 'products': []}
        m.search_late_fusion.return_value = {'status': 'success', 'products': []}
        m.search_early_fusion.return_value = {'status': 'success', 'products': []}
        m.search_image.return_value = {'status': 'success', 'products': []}
        m.search_image_by_text.return_value = {'status': 'success', 'products': []}
        m.search_text_by_image.return_value = {'status': 'success', 'products': []}
        m.add_product.return_value = {'status': 'success', 'details': {}}
        m.update_product.return_value = {'status': 'success', 'details': {}}
        m.delete_product.return_value = {'status': 'success'}
        m.get_index_stats.return_value = {'status': 'success', 'data': {}, 'indices': {}}
        m.get_available_models.return_value = {'status': 'success', 'data': {}}
        m.clear_index.return_value = {'status': 'success', 'details': {}}
        m.add_test_product.return_value = {'status': 'success', 'details': {}}
        m.get_available_model_ids.return_value = ['ViT-B/32', 'ViT-L/14']
        yield m

class TestRetrievalProxy:
    def test_search_text(self, mock_svc, c):
        assert c.post('/api/retrieval/search/text', json={'text':'q'}).status_code == 200
        assert c.post('/api/retrieval/search/text', json={}).status_code == 400

    def test_late_fusion(self, mock_svc, c):
        assert c.post('/api/retrieval/search/late', json={'text':'q','image':'/t.jpg'}).status_code == 200
        assert c.post('/api/retrieval/search/late', json={'image':'/t.jpg'}).status_code == 400

    def test_early_fusion(self, mock_svc, c):
        assert c.post('/api/retrieval/search/early', json={'text':'q','image':'/t.jpg'}).status_code == 200
        assert c.post('/api/retrieval/search/early', json={'image':'/t.jpg'}).status_code == 400

    def test_stats_endpoint(self, mock_svc, c):
        assert c.get('/api/retrieval/stats').status_code == 200

    def test_exception_handlers(self, mock_svc, c):
        mock_svc.search_text.side_effect = Exception('err')
        assert c.post('/api/retrieval/search/text', json={'text':'q'}).status_code == 500

    def test_validation_errors(self, mock_svc, c):
        assert c.post('/api/retrieval/search/text', json={}).status_code == 400
        assert c.post('/api/retrieval/add-product', json={'id':'1'}).status_code == 400
        assert c.post('/api/retrieval/add-product', json={'id':'1','name':'T','price':'bad'}).status_code == 400
        mock_svc.search_text.return_value = {'status':'error','error':'x'}
        assert c.post('/api/retrieval/search/text', json={'text':'q'}).status_code == 500

    def test_image_search(self, mock_svc, c):
        assert c.post('/api/retrieval/search/image', json={'image':'/t.jpg'}).status_code == 200
        assert c.post('/api/retrieval/search/image', json={}).status_code == 400

    def test_add_update_delete_product(self, mock_svc, c):
        assert c.post('/api/retrieval/add-product', json={'id':'1','name':'T'}).status_code == 200
        assert c.post('/api/retrieval/add-product', json={}).status_code == 400
        assert c.put('/api/retrieval/update-product/1', json={'name':'U'}).status_code == 200
        assert c.delete('/api/retrieval/delete-product/1').status_code == 200

    def test_index_and_models(self, mock_svc, c):
        assert c.get('/api/retrieval/index-stats').status_code == 200
        assert c.get('/api/retrieval/models').status_code == 200
        assert c.get('/api/retrieval/stats').status_code == 200
        assert c.delete('/api/retrieval/clear-index').status_code == 200

    def test_validation_and_errors(self, mock_svc, c):
        assert c.post('/api/retrieval/search/text', data='{}', content_type='application/json').status_code == 400
        assert c.post('/api/retrieval/search/late', data='{}', content_type='application/json').status_code == 400
        assert c.post('/api/retrieval/search/early', data='{}', content_type='application/json').status_code == 400
        assert c.post('/api/retrieval/search/image', data='{}', content_type='application/json').status_code == 400
        assert c.post('/api/retrieval/add-product', json={'id':'1'}).status_code == 400
        assert c.post('/api/retrieval/add-product', json={'id':'1','name':'T','price':'bad'}).status_code == 400
        mock_svc.search_text.return_value = {'status':'error','error':'x'}
        assert c.post('/api/retrieval/search/text', json={'text':'q'}).status_code == 500

    def test_selected_models(self, mock_svc, c):
        assert c.get('/api/retrieval/selected-models').status_code == 200
        r = c.post('/api/retrieval/selected-models', json={'textual_model':'ViT-B/32','visual_model':'ViT-B/32'})
        assert r.status_code == 200

    def test_fusion_endpoint(self, mock_svc, c):
        assert c.get('/api/retrieval/fusion-endpoint').status_code == 200
        assert c.post('/api/retrieval/fusion-endpoint', json={}).status_code == 400
        assert c.post('/api/retrieval/fusion-endpoint', json={'fusion_endpoint':'bad'}).status_code == 400
        with patch('routes.retrieval.save_selected_fusion_endpoint'):
            assert c.post('/api/retrieval/fusion-endpoint', json={'fusion_endpoint':'early'}).status_code == 200
