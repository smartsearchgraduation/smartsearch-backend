from io import BytesIO
import os, sys, tempfile
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from unittest.mock import patch
import pytest
from flask import Flask
from routes.search import search_bp, save_search_image, save_base64_image

@pytest.fixture
def c():
    a = Flask(__name__); a.config["TESTING"] = True; a.register_blueprint(search_bp)
    with a.test_client() as cl: yield cl

@pytest.fixture
def search_app():
    a = Flask(__name__); a.config["TESTING"] = True; a.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
    a.register_blueprint(search_bp)
    with a.app_context(): yield a
    import shutil; shutil.rmtree(a.config['UPLOAD_FOLDER'], ignore_errors=True)

class TestSearch:
    @patch("routes.search.get_selected_fusion_endpoint", return_value="late")
    @patch("routes.search.save_search_image")
    @patch("routes.search.SearchService.execute_search")
    def test_search_text_and_image(self, me, ms, mf, c):
        me.return_value = {"search_id": 42}; ms.return_value = "uploads/products/t.jpg"
        r = c.post("/api/search", data={"raw_text": "t", "images": (BytesIO(b"f"), "q.jpg")}, content_type="multipart/form-data")
        assert r.status_code == 201

    @patch("routes.search.get_selected_fusion_endpoint", return_value="late")
    @patch("routes.search.SearchService.execute_search")
    def test_search_text_only(self, me, mf, c):
        me.return_value = {"search_id": 1}
        assert c.post("/api/search", data={"raw_text": "t"}, content_type="multipart/form-data").status_code == 201

    @patch("routes.search.get_selected_fusion_endpoint", return_value="late")
    @patch("routes.search.SearchService.execute_search")
    def test_search_base64(self, me, mf, c):
        import base64
        me.return_value = {"search_id": 1}
        b64 = f"data:image/png;base64,{base64.b64encode(b'f').decode()}"
        assert c.post("/api/search", data={"raw_text": "t", "image_base64": b64}, content_type="multipart/form-data").status_code == 201

    def test_search_validation(self, c):
        assert c.post("/api/search", data={}, content_type="multipart/form-data").status_code == 400
        assert c.post("/api/search", data={"search_mode": "invalid", "raw_text":"t"}, content_type="multipart/form-data").status_code == 400
        assert c.post("/api/search", data={"search_mode": "iwt"}, content_type="multipart/form-data").status_code == 400
        assert c.post("/api/search", data={"raw_text":"t", "search_mode":"twi"}, content_type="multipart/form-data").status_code == 400

    @patch("routes.search.SearchService.get_search_by_id")
    def test_get_search(self, mg, c):
        mg.return_value = {"search_id": 1, "products": []}
        assert c.get("/api/search/1").status_code == 200
        mg.return_value = None
        assert c.get("/api/search/999").status_code == 404

    @patch("routes.search.SearchService.execute_db_fallback_search")
    def test_db_fallback(self, mf, c):
        mf.return_value = {"products": []}
        assert c.post("/api/search/db-fallback", json={"search_id": 1}).status_code == 200
        assert c.post("/api/search/db-fallback", json={}).status_code == 400

    def test_save_search_image(self, search_app):
        from werkzeug.datastructures import FileStorage
        f = FileStorage(stream=BytesIO(b'd'), filename='t.png', content_type='image/png')
        p = save_search_image(f)
        assert p and os.path.exists(p); os.unlink(p)
        assert save_search_image(None) is None
        f = FileStorage(stream=BytesIO(b''), filename='', content_type='image/png')
        assert save_search_image(f) is None

    def test_search_value_error_returns_404(self, c):
        with patch("routes.search.get_selected_fusion_endpoint", return_value="late"), \
             patch("routes.search.SearchService.execute_search") as me:
            me.side_effect = ValueError("invalid")
            assert c.post("/api/search", data={"raw_text":"t"}, content_type="multipart/form-data").status_code == 404

    def test_search_generic_error_returns_500(self, c):
        with patch("routes.search.get_selected_fusion_endpoint", return_value="late"), \
             patch("routes.search.SearchService.execute_search") as me:
            me.side_effect = Exception("server err")
            assert c.post("/api/search", data={"raw_text":"t"}, content_type="multipart/form-data").status_code == 500

    def test_image_validation_error(self, c):
        with patch("routes.search.get_selected_fusion_endpoint", return_value="late"), \
             patch("routes.search.save_search_image") as ms:
            ms.side_effect = ValueError("bad image")
            assert c.post("/api/search", data={"raw_text":"t","images":(BytesIO(b"x"),"q.txt")}, content_type="multipart/form-data").status_code == 400

    def test_get_search_by_id_error(self, c):
        with patch("routes.search.SearchService.get_search_by_id") as mg:
            mg.side_effect = Exception("err")
            assert c.get("/api/search/1").status_code == 500

    def test_save_base64_image(self, search_app):
        import base64
        b = base64.b64encode(b'data').decode()
        p = save_base64_image(f'data:image/png;base64,{b}')
        assert p and os.path.exists(p); os.unlink(p)
        assert save_base64_image(None) is None
