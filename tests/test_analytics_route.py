import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from unittest.mock import patch
from flask import Flask
from config.app_config import TestingConfig
from models import db, SearchQuery, SearchTime

@pytest.fixture(scope='module')
def app():
    a = Flask(__name__); a.config.from_object(TestingConfig); a.config['TESTING'] = True
    db.init_app(a)
    from routes.analytics import analytics_bp; a.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    with a.app_context(): db.create_all()
    yield a

@pytest.fixture
def c(app):
    with app.test_client() as cl, app.app_context(): yield cl
@pytest.fixture
def ctx(app):
    with app.app_context(): yield

@pytest.fixture
def seed(ctx):
    sq = SearchQuery(raw_text='t', corrected_text='t'); db.session.add(sq); db.session.flush()
    st = SearchTime(search_id=sq.search_id); db.session.add(st); db.session.commit(); return sq.search_id

class TestAnalytics:
    def test_search_duration(self, ctx, c, seed):
        r = c.post('/api/analytics/search-duration', json={'search_id':seed,'search_duration':1,'product_load_duration':1})
        assert r.status_code == 200
        assert c.post('/api/analytics/search-duration', json={}).status_code == 400

    def test_search_duration_not_found(self, ctx, c):
        assert c.post('/api/analytics/search-duration', json={'search_id':99999,'search_duration':1,'product_load_duration':1}).status_code == 404

    def test_search_duration_internal_error(self, ctx, c):
        with patch('routes.analytics.SearchService.update_client_metrics') as mu:
            mu.side_effect = Exception('err')
            r = c.post('/api/analytics/search-duration', json={'search_id':1,'search_duration':1,'product_load_duration':1})
            assert r.status_code == 500

    def test_logs_exception(self, ctx, c):
        with patch('routes.analytics.SearchTime') as ms:
            ms.query.all.side_effect = Exception('err')
            assert c.get('/api/analytics/logs').status_code == 500
            ms.query.get.side_effect = Exception('err')
            assert c.get('/api/analytics/logs/1').status_code == 500

    def test_logs(self, ctx, c, seed):
        assert c.get('/api/analytics/logs').status_code == 200
        assert c.get(f'/api/analytics/logs/{seed}').status_code == 200
        assert c.get('/api/analytics/logs/99999').status_code == 404
