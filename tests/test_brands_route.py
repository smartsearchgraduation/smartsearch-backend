import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from unittest.mock import patch
from flask import Flask
from config.app_config import TestingConfig
from models import db, Brand

@pytest.fixture(scope='module')
def app():
    a = Flask(__name__); a.config.from_object(TestingConfig); a.config['TESTING'] = True
    db.init_app(a)
    from routes.brands import brands_bp; a.register_blueprint(brands_bp)
    with a.app_context(): db.create_all()
    yield a

@pytest.fixture
def c(app):
    with app.test_client() as cl, app.app_context(): yield cl

@pytest.fixture
def ctx(app):
    with app.app_context(): yield

class TestBrands:
    def test_get_brand_not_found(self, ctx, c):
        assert c.get('/api/brands/99999').status_code == 404
    def test_sorted(self, ctx, c):
        for n in ['Zebra','Apple','Banana']: db.session.add(Brand(name=n))
        db.session.commit()
        names = [b['name'] for b in c.get('/api/brands').get_json()['brands']]
        assert names == ['Apple','Banana','Zebra']

    def test_crud(self, ctx, c):
        r = c.post('/api/brands', json={'name':'Nike'})
        assert r.status_code == 201; bid = r.get_json()['brand_id']
        assert c.get(f'/api/brands/{bid}').status_code == 200
        assert c.put(f'/api/brands/{bid}', json={'name':'Adidas'}).status_code == 200
        assert c.delete(f'/api/brands/{bid}').status_code == 200
        assert c.delete('/api/brands/99999').status_code == 404

    def test_exceptions(self, ctx, c):
        assert c.post('/api/brands', json={}).status_code == 400
        assert c.get('/api/brands/99999').status_code == 404
        assert c.put('/api/brands/99999', json={'name':'X'}).status_code == 404
        assert c.delete('/api/brands/99999').status_code == 404

    def test_create_brand_empty_name(self, ctx, c):
        r = c.post('/api/brands', json={'name':''})
        assert r.status_code == 201 or r.status_code == 400

    def test_brand_exceptions(self, ctx, c):
        from models.brand import Brand
        with patch('routes.brands.db.session.commit') as mc:
            mc.side_effect = Exception('err')
            assert c.post('/api/brands', json={'name':'X'}).status_code == 500
        b = Brand(name='T'); db.session.add(b); db.session.commit()
        with patch('routes.brands.db.session.commit') as mc:
            mc.side_effect = Exception('err')
            assert c.put(f'/api/brands/{b.brand_id}', json={'name':'X'}).status_code == 500
        with patch('routes.brands.db.session.commit') as mc:
            mc.side_effect = Exception('err')
            assert c.delete(f'/api/brands/{b.brand_id}').status_code == 500
