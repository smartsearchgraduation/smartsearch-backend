import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from unittest.mock import patch
from flask import Flask
from config.app_config import TestingConfig
from models import db, Category

@pytest.fixture(scope='module')
def app():
    a = Flask(__name__); a.config.from_object(TestingConfig); a.config['TESTING'] = True
    db.init_app(a)
    from routes.categories import categories_bp; a.register_blueprint(categories_bp)
    with a.app_context(): db.create_all()
    yield a

@pytest.fixture
def c(app):
    with app.test_client() as cl, app.app_context(): yield cl

@pytest.fixture
def ctx(app):
    with app.app_context(): yield

class TestCategories:
    def test_crud(self, ctx, c):
        assert c.post('/api/categories', json={'name':'Root'}).status_code == 201
        p_id = c.get('/api/categories').get_json()['categories'][0]['category_id']
        assert c.get(f'/api/categories/{p_id}').status_code == 200
        assert c.put(f'/api/categories/{p_id}', json={'name':'Renamed'}).status_code == 200
        assert c.delete(f'/api/categories/{p_id}').status_code == 200

    def test_subcategory(self, ctx, c):
        r = c.post('/api/categories', json={'name':'Parent'}); pid = r.get_json()['category_id']
        r = c.post('/api/categories', json={'name':'Child','parent_category_id':pid})
        assert r.status_code == 201 and r.get_json()['parent_category_id'] == pid

    def test_tree(self, ctx, c):
        r = c.post('/api/categories', json={'name':'P'}); pid = r.get_json()['category_id']
        c.post('/api/categories', json={'name':'C','parent_category_id':pid})
        r = c.get('/api/categories?tree=true')
        assert any(x['name']=='P' and 'children' in x for x in r.get_json()['categories'])

    def test_parent_filter(self, ctx, c):
        r = c.post('/api/categories', json={'name':'P'}); pid = r.get_json()['category_id']
        c.post('/api/categories', json={'name':'C','parent_category_id':pid})
        assert len(c.get(f'/api/categories?parent_id={pid}').get_json()['categories']) == 1

    def test_validation(self, ctx, c):
        assert c.post('/api/categories', json={}).status_code == 400
        assert c.put('/api/categories/99999', json={'name':'X'}).status_code == 404
        assert c.delete('/api/categories/99999').status_code == 404
        assert c.post('/api/categories', json={'name':'X','parent_category_id':99999}).status_code == 400

    def test_suicide_parent(self, ctx, c):
        r = c.post('/api/categories', json={'name':'L'}); pid = r.get_json()['category_id']
        assert c.put(f'/api/categories/{pid}', json={'parent_category_id':pid}).status_code == 400

    def test_update_category_not_found(self, ctx, c):
        assert c.put('/api/categories/99999', json={'name':'X'}).status_code == 404

    def test_delete_category_not_found(self, ctx, c):
        assert c.delete('/api/categories/99999').status_code == 404

    def test_get_category_exception(self, ctx, c):
        with patch('routes.categories.Category') as mc:
            mc.query.get.side_effect = Exception('err')
            assert c.get('/api/categories/1').status_code == 500

    def test_create_category_exception(self, ctx, c):
        with patch('routes.categories.db.session.add') as ma:
            ma.side_effect = Exception('err')
            assert c.post('/api/categories', json={'name':'X'}).status_code == 500

    def test_update_category_not_found_parent(self, ctx, c):
        cat = Category(name='C'); db.session.add(cat); db.session.commit()
        r = c.put(f'/api/categories/{cat.category_id}', json={'parent_category_id': 99999})
        assert r.status_code == 400

    def test_get_category_not_found(self, ctx, c):
        assert c.get('/api/categories/99999').status_code == 404

    def test_delete_with_children(self, ctx, c):
        r = c.post('/api/categories', json={'name':'P'}); pid = r.get_json()['category_id']
        r = c.post('/api/categories', json={'name':'C','parent_category_id':pid}); cid = r.get_json()['category_id']
        c.delete(f'/api/categories/{pid}')
        db.session.expire_all()
        assert Category.query.get(cid) is not None
