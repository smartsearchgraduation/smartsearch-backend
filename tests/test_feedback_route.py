import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from unittest.mock import patch
from flask import Flask
from config.app_config import TestingConfig
from models import db, SearchQuery, Retrieve, Product

@pytest.fixture(scope='module')
def app():
    a = Flask(__name__); a.config.from_object(TestingConfig); a.config['TESTING'] = True
    db.init_app(a)
    from routes.feedback import feedback_bp; a.register_blueprint(feedback_bp)
    with a.app_context(): db.create_all()
    yield a

@pytest.fixture
def c(app):
    with app.test_client() as cl, app.app_context(): yield cl
@pytest.fixture
def ctx(app):
    with app.app_context(): yield

@pytest.fixture
def data(ctx):
    sq = SearchQuery(raw_text='t', corrected_text='t'); db.session.add(sq); db.session.flush()
    p = Product(name='P', price=1.0); db.session.add(p); db.session.flush()
    r = Retrieve(search_id=sq.search_id, product_id=p.product_id, rank=1)
    db.session.add(r); db.session.commit()
    return {'query_id': sq.search_id, 'product_id': p.product_id}

class TestFeedback:
    def test_feedback(self, ctx, c, data):
        assert c.post('/api/feedback', json={**data, 'is_relevant': True}).status_code == 200
        assert c.post('/api/feedback', json={}).status_code == 400
        assert c.post('/api/feedback', json={'query_id':99999,'product_id':99999,'is_relevant':True}).status_code == 404

    def test_click(self, ctx, c, data):
        assert c.post('/api/click', json=data).status_code == 200
        assert c.post('/api/click', json={}).status_code == 400
        assert c.post('/api/click', json={'query_id':99999,'product_id':99999}).status_code == 404

    def test_feedback_exception(self, ctx, c, data):
        with patch('routes.feedback.db.session.commit') as mc:
            mc.side_effect = Exception('err')
            assert c.post('/api/feedback', json={**data, 'is_relevant':True}).status_code == 500
            assert c.post('/api/click', json=data).status_code == 500

    def test_metrics_exception(self, ctx, c):
        with patch('routes.feedback.SearchQuery') as ms:
            ms.query.count.side_effect = Exception('err')
            assert c.get('/api/metrics').status_code == 500

    def test_metrics_zero_data(self, ctx, c):
        SearchQuery.query.delete(); Retrieve.query.delete(); db.session.commit()
        r = c.get('/api/metrics')
        assert r.status_code == 200 and r.get_json()['total_searches'] == 0

    def test_metrics(self, ctx, c, data):
        Retrieve.query.filter_by(search_id=data['query_id']).update({'is_clicked':True,'is_relevant':True})
        db.session.commit()
        r = c.get('/api/metrics')
        assert r.status_code == 200
        d = r.get_json()
        assert d['total_searches'] >= 1 and 'click_through_rate' in d
