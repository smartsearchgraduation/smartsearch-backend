import os, sys, tempfile, base64
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from io import BytesIO
from flask import Flask
from config.app_config import TestingConfig
from models import db

@pytest.fixture(scope='module')
def app():
    a = Flask(__name__); a.config.from_object(TestingConfig); a.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
    db.init_app(a)
    from routes.products import products_bp; a.register_blueprint(products_bp)
    @a.route('/uploads/products/<f>')
    def _(f): from flask import send_from_directory; return send_from_directory(a.config['UPLOAD_FOLDER'], f)
    with a.app_context(): db.create_all()
    yield a
    import shutil; shutil.rmtree(a.config['UPLOAD_FOLDER'], ignore_errors=True)

@pytest.fixture
def ctx(app):
    with app.app_context(): yield

def test_save_uploaded_image(app, ctx):
    from routes.products import save_uploaded_image
    from werkzeug.datastructures import FileStorage
    f = FileStorage(stream=BytesIO(b'd'), filename='t.png', content_type='image/png')
    url = save_uploaded_image(f, 1)
    assert url and url.startswith('/uploads/products/')
    f2 = FileStorage(stream=BytesIO(b'd'), filename='t.txt', content_type='text/plain')
    assert save_uploaded_image(f2, 1) is None

def test_save_base64_image(app, ctx):
    from routes.products import save_base64_image
    d = base64.b64encode(b'fake').decode()
    assert save_base64_image(f'data:image/png;base64,{d}', product_id=1) is not None
    assert save_base64_image('bad', product_id=1) is None

def test_get_image_as_base64(app, ctx):
    from routes.products import get_image_as_base64
    uf = app.config['UPLOAD_FOLDER']
    with open(os.path.join(uf, 'test.png'), 'wb') as f: f.write(b'PNG')
    r = get_image_as_base64('/uploads/products/test.png')
    assert r and r.startswith('data:image/')

def test_allowed_file(app, ctx):
    from routes.products import allowed_file
    for ext in ['png','jpg','jpeg','gif','webp']: assert allowed_file(f'f.{ext}')
    assert not allowed_file('f.txt') and not allowed_file('f')
