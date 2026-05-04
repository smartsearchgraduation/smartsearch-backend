import os, sys, tempfile, json, base64
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from io import BytesIO
from unittest.mock import patch
from flask import Flask
from config.app_config import TestingConfig
from models import db, Product, Brand, ProductImage

@pytest.fixture(scope='module')
def app():
    a = Flask(__name__)
    a.config.from_object(TestingConfig)
    a.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
    a.config['TESTING'] = True
    a.config['ALLOWED_EXTENSIONS'] = {'png','jpg','jpeg','gif','webp'}
    db.init_app(a)
    from routes.products import products_bp
    a.register_blueprint(products_bp)
    @a.route('/uploads/products/<f>')
    def _(f): from flask import send_from_directory; return send_from_directory(a.config['UPLOAD_FOLDER'], f)
    with a.app_context(): db.create_all()
    yield a
    import shutil; shutil.rmtree(a.config['UPLOAD_FOLDER'], ignore_errors=True)

@pytest.fixture
def c(app): 
    with app.test_client() as cl, app.app_context(): yield cl

@pytest.fixture
def ctx(app):
    with app.app_context(): yield

def _p(name='P', price=10.0, **kw):
    p = Product(name=name, price=price, **kw)
    db.session.add(p); db.session.flush(); return p

class TestProducts:
    def test_list_active(self, ctx, c):
        _p('A1', is_active=True); _p('A2', is_active=True); _p('I1', is_active=False)
        db.session.commit()
        r = c.get('/api/products?is_active=true')
        assert r.status_code == 200 and r.get_json()['total'] == 2

    def test_create_success(self, ctx, c):
        with patch('routes.products.faiss_service') as m:
            m.add_product.return_value = {'status': 'success', 'details': {}}
            r = c.post('/api/products', data={'name':'N','price':'10','brand':'B','images':(BytesIO(b'd'),'t.png')}, content_type='multipart/form-data')
            assert r.status_code == 201

    def test_create_validation(self, ctx, c):
        assert c.post('/api/products', data={'price':'10','brand':'B','images':(BytesIO(b'd'),'t.png')}, content_type='multipart/form-data').status_code == 400
        assert c.post('/api/products', data={'name':'N','brand':'B','images':(BytesIO(b'd'),'t.png')}, content_type='multipart/form-data').status_code == 400
        assert c.post('/api/products', data={'name':'N','price':'abc','brand':'B','images':(BytesIO(b'd'),'t.png')}, content_type='multipart/form-data').status_code == 400
        assert c.post('/api/products', data={'name':'N','price':'10','brand':'B','images':(BytesIO(b'd'),'t.txt')}, content_type='multipart/form-data').status_code == 400

    def test_crud(self, ctx, c):
        b = Brand(name='B'); db.session.add(b); db.session.flush()
        p = _p('Test', brand_id=b.brand_id); db.session.commit()
        assert c.get(f'/api/products/{p.product_id}').status_code == 200
        assert c.get('/api/products/99999').status_code == 404
        assert c.put(f'/api/products/{p.product_id}', data={'name':'X','price':'5'}, content_type='multipart/form-data').status_code == 200
        with patch('routes.products.faiss_service') as m:
            m.delete_product.return_value = {'status': 'success'}
            assert c.delete(f'/api/products/{p.product_id}').status_code == 200

    def test_filters(self, ctx, c):
        from models.category import Category
        cat = Category(name='E'); db.session.add(cat); db.session.flush()
        b = Brand(name='N'); db.session.add(b); db.session.flush()
        p = _p('G'); p.categories.append(cat); p.brand_id = b.brand_id; db.session.commit()
        assert c.get(f'/api/products?category_id={cat.category_id}').get_json()['total'] >= 1
        assert c.get(f'/api/products?brand_id={b.brand_id}').get_json()['total'] >= 1
        assert c.get('/api/products?min_price=1&max_price=20').get_json()['total'] >= 1

    def test_image_upload(self, ctx, c):
        p = _p(); db.session.commit()
        assert c.post(f'/api/products/{p.product_id}/images', data={'file':(BytesIO(b'd'),'t.png')}, content_type='multipart/form-data').status_code == 201
        assert c.post(f'/api/products/{p.product_id}/images', data={'file':(BytesIO(b'd'),'t.txt')}, content_type='multipart/form-data').status_code == 400

    def test_images_list_and_delete(self, ctx, c):
        p = _p(); db.session.flush()
        img = ProductImage(product_id=p.product_id, url='/u/t.jpg'); db.session.add(img); db.session.commit()
        assert c.get(f'/api/products/{p.product_id}/images').status_code == 200
        assert c.delete(f'/api/products/{p.product_id}/images/{img.image_no}').status_code == 200

    def test_update_with_images(self, ctx, c):
        with patch('routes.products.faiss_service') as m:
            m.add_product.return_value = {'status': 'success', 'details': {}}
            m.delete_product.return_value = {'status': 'success'}
            p = _p(); db.session.commit()
            r = c.put(f'/api/products/{p.product_id}', data={'name':'U','images':(BytesIO(b'x'),'n.png')}, content_type='multipart/form-data')
            assert r.status_code == 200

    def test_image_endpoints(self, ctx, c):
        p = _p(); db.session.flush()
        img = ProductImage(product_id=p.product_id, url='/u/t.jpg'); db.session.add(img); db.session.commit()
        assert c.get('/api/products/99999/image').status_code == 404
        assert c.get('/api/products/99999/images').status_code == 404

    def test_upload_product_image_validation(self, ctx, c):
        p = _p(); db.session.commit()
        assert c.post('/api/products/99999/images', data={'file':(BytesIO(b'd'),'t.png')}, content_type='multipart/form-data').status_code == 404
        assert c.post(f'/api/products/{p.product_id}/images', data={}, content_type='multipart/form-data').status_code == 400

    def test_delete_product_not_found(self, ctx, c):
        assert c.delete('/api/products/99999').status_code == 404

    def test_put_product_not_found(self, ctx, c):
        assert c.put('/api/products/99999', data={'name':'X'}, content_type='multipart/form-data').status_code == 404

    def test_get_products_filters(self, ctx, c):
        from models.category import Category
        cat = Category(name='E'); db.session.add(cat); db.session.flush()
        b = Brand(name='N'); db.session.add(b); db.session.flush()
        p = _p('G'); p.categories.append(cat); p.brand_id = b.brand_id; db.session.commit()
        assert c.get(f'/api/products?category_id={cat.category_id}').get_json()['total'] >= 1
        assert c.get(f'/api/products?brand_id={b.brand_id}').get_json()['total'] >= 1
        assert c.get('/api/products?min_price=1&max_price=20').get_json()['total'] >= 1

    def test_put_product_faiss_error_ok(self, ctx, c):
        with patch('routes.products.faiss_service') as m:
            m.delete_product.return_value={'status':'success'}
            m.add_product.return_value={'status':'error','error':'FAISS err'}
            p = _p(); db.session.commit()
            assert c.put(f'/api/products/{p.product_id}', data={'name':'X'}, content_type='multipart/form-data').status_code == 200

    def test_put_product_general_exception(self, ctx, c):
        p = _p(); db.session.commit()
        with patch('routes.products.db.session.commit') as mc:
            mc.side_effect = Exception('err')
            assert c.put(f'/api/products/{p.product_id}', data={'name':'X'}, content_type='multipart/form-data').status_code == 500

    def test_delete_faiss_error_ok(self, ctx, c):
        with patch('routes.products.faiss_service') as m:
            m.delete_product.return_value={'status':'error','error':'FAISS err'}
            p = _p(); db.session.commit()
            assert c.delete(f'/api/products/{p.product_id}').status_code == 200

    def test_delete_product_general_exception(self, ctx, c):
        p = _p(); db.session.commit()
        with patch('routes.products.db.session.delete') as md:
            md.side_effect = Exception('err')
            assert c.delete(f'/api/products/{p.product_id}').status_code == 500

    def test_upload_image_exception(self, ctx, c):
        p = _p(); db.session.commit()
        with patch('routes.products.os.makedirs') as mm:
            mm.side_effect = Exception('IO err')
            r = c.post(f'/api/products/{p.product_id}/images', data={'file':(BytesIO(b'd'),'t.png')}, content_type='multipart/form-data')
            assert r.status_code == 500

    def test_delete_image_not_found(self, ctx, c):
        p = _p(); db.session.commit()
        assert c.delete(f'/api/products/{p.product_id}/images/999').status_code == 404

    def test_create_negative_price(self, ctx, c):
        with patch('routes.products.faiss_service') as mf:
            mf.add_product.return_value = {'status':'success','details':{}}
            r = c.post('/api/products', data={'name':'N','price':'-5','brand':'B','images':(BytesIO(b'd'),'t.png')}, content_type='multipart/form-data')
            assert r.status_code == 400

    def test_update_with_brand_and_active(self, ctx, c):
        p = _p(); db.session.commit()
        assert c.put(f'/api/products/{p.product_id}', data={'brand':'NewB','is_active':'false'}, content_type='multipart/form-data').status_code == 200
        db.session.expire_all()
        assert Product.query.get(p.product_id).is_active is False

    def test_upload_image_validation(self, ctx, c):
        p = _p(); db.session.commit()
        assert c.post('/api/products/99999/images', data={'file':(BytesIO(b'd'),'t.png')}, content_type='multipart/form-data').status_code == 404
        assert c.post(f'/api/products/{p.product_id}/images', data={}, content_type='multipart/form-data').status_code == 400
        assert c.post(f'/api/products/{p.product_id}/images', data={'file':(BytesIO(b'd'),'t.txt')}, content_type='multipart/form-data').status_code == 400

    def test_product_image_endpoints(self, ctx, c, app):
        p = _p(); db.session.flush()
        uf = app.config['UPLOAD_FOLDER']
        with open(os.path.join(uf, 't.jpg'), 'w') as f: f.write('')
        img = ProductImage(product_id=p.product_id, url='/uploads/products/t.jpg'); db.session.add(img); db.session.commit()
        assert c.get(f'/api/products/{p.product_id}/image').status_code == 200
        assert c.delete(f'/api/products/{p.product_id}/images/999').status_code == 404

    def test_get_first_image_no_images(self, ctx, c):
        p = _p(); db.session.commit()
        assert c.get(f'/api/products/{p.product_id}/image').status_code == 404

    def test_create_invalid_brand(self, ctx, c):
        with patch('routes.products.faiss_service') as mf:
            mf.add_product.return_value = {'status':'success','details':{}}
            r = c.post('/api/products', data={'name':'N','price':'10','brand':'B','category_ids':'abc','images':(BytesIO(b'd'),'t.png')}, content_type='multipart/form-data')
            assert r.status_code == 400

    def test_update_with_category_ids(self, ctx, c):
        from models.category import Category
        cat = Category(name='C'); db.session.add(cat); db.session.commit()
        p = _p(); db.session.commit()
        r = c.put(f'/api/products/{p.product_id}', data={'category_ids':str(cat.category_id)}, content_type='multipart/form-data')
        assert r.status_code == 200

    def test_delete_faiss_error_log(self, ctx, c):
        with patch('routes.products.faiss_service') as m:
            m.delete_product.return_value = {'status':'error','error':'FAISS err'}
            p = _p(); db.session.commit()
            assert c.delete(f'/api/products/{p.product_id}').status_code == 200

    def test_image_endpoint_not_found(self, ctx, c):
        p = _p(); db.session.flush()
        from models.product_image import ProductImage
        img = ProductImage(product_id=p.product_id, url='/uploads/products/t.jpg'); db.session.add(img); db.session.commit()
        with patch('routes.products.os.path.exists', return_value=False):
            assert c.delete(f'/api/products/{p.product_id}/images/{img.image_no}').status_code == 200

    def test_create_product_general_error(self, ctx, c):
        with patch('routes.products.Product') as mp:
            mp.side_effect = Exception('err')
            r = c.post('/api/products', data={'name':'N','price':'10','brand':'B','images':(BytesIO(b'd'),'t.png')}, content_type='multipart/form-data')
            assert r.status_code == 500

    def test_update_product_invalid_price(self, ctx, c):
        p = _p(); db.session.commit()
        assert c.put(f'/api/products/{p.product_id}', data={'price':'abc'}, content_type='multipart/form-data').status_code == 400

    def test_upload_image_no_file(self, ctx, c):
        p = _p(); db.session.commit()
        assert c.post(f'/api/products/{p.product_id}/images', data={}, content_type='multipart/form-data').status_code == 400
