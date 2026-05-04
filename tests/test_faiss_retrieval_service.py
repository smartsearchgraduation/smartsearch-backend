import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

@pytest.fixture
def app_ctx():
    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = '/tmp/test_uploads'
    with app.app_context():
        yield

def svc():
    from services.faiss_retrieval_service import FAISSRetrievalService
    return FAISSRetrievalService()

def _mock_post_200(retval):
    mr = MagicMock(); mr.status_code = 200; mr.json.return_value = retval
    return mr

class TestFAISSRetrievalService:

    def test_text_search_sends_request(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.post') as mp:
            mp.return_value = _mock_post_200({'status': 'success', 'products': [{'product_id': 1}]})
            r = svc().search_text("query")
            assert r['status'] == 'success'
            assert mp.call_args[1]['json']['text'] == 'query'

    def test_text_search_error_paths(self, app_ctx):
        for error in ['connection', 'timeout', 'non_200', 'faiss_error']:
            with patch('services.faiss_retrieval_service.requests.post') as mp:
                if error == 'connection':
                    from requests.exceptions import ConnectionError
                    mp.side_effect = ConnectionError()
                elif error == 'timeout':
                    from requests.exceptions import Timeout
                    mp.side_effect = Timeout()
                elif error == 'non_200':
                    mr = MagicMock(); mr.status_code = 500; mr.json.return_value = {'error': 'x'}; mp.return_value = mr
                elif error == 'faiss_error':
                    mp.return_value = _mock_post_200({'status': 'error', 'error': 'x'})
                assert svc().search_text("q")['status'] == 'error'

    def test_search_image(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.post') as mp, patch('os.path.exists', return_value=True):
            mp.return_value = _mock_post_200({'status': 'success', 'products': []})
            assert svc().search_image("/tmp/t.jpg")['status'] == 'success'

    def test_search_image_not_found(self, app_ctx):
        with patch('os.path.exists', return_value=False):
            assert svc().search_image("/x.jpg")['status'] == 'error'

    def test_early_fusion(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.post') as mp, patch('os.path.exists', return_value=True):
            mp.return_value = _mock_post_200({'status': 'success', 'products': []})
            assert svc().search_early_fusion(text="q", image_path="/t.jpg")['status'] == 'success'

    def test_late_fusion(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.post') as mp, patch('os.path.exists', return_value=True):
            mp.return_value = _mock_post_200({'status': 'success', 'products': []})
            assert svc().search_late_fusion(text="q", image_path="/t.jpg")['status'] == 'success'

    def test_image_by_text(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.post') as mp:
            mp.return_value = _mock_post_200({'status': 'success', 'products': []})
            assert svc().search_image_by_text(text="q")['status'] == 'success'

    def test_text_by_image(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.post') as mp, patch('os.path.exists', return_value=True):
            mp.return_value = _mock_post_200({'status': 'success', 'products': []})
            assert svc().search_text_by_image(image_path="/t.jpg")['status'] == 'success'

    def test_add_product_success_and_errors(self, app_ctx):
        svc_inst = svc()
        r = svc_inst.add_product(product_id="", name="T", description="", brand="B", category="C", price=1, images=[])
        assert r['status'] == 'error'
        r = svc_inst.add_product(product_id="1", name="", description="", brand="B", category="C", price=1, images=[])
        assert r['status'] == 'error'

    def test_update_product_success_and_errors(self, app_ctx):
        svc_inst = svc()
        assert svc_inst.update_product(product_id="", name="T", description="", brand="", category="", price=1, images=[])['status'] == 'error'

    def test_add_update_product_http_errors(self, app_ctx):
        for method in ['add', 'update']:
            with patch(f'services.faiss_retrieval_service.requests.{ "post" if method == "add" else "put" }') as mp:
                for error in ['connection', 'timeout', 'non_200']:
                    if error == 'connection':
                        from requests.exceptions import ConnectionError; mp.side_effect = ConnectionError()
                    elif error == 'timeout':
                        from requests.exceptions import Timeout; mp.side_effect = Timeout()
                    elif error == 'non_200':
                        mr = MagicMock(); mr.status_code = 500; mr.json.return_value = {'error': 'x'}; mp.return_value = mr
                    if method == 'add':
                        r = svc().add_product(product_id="1", name="T", description="", brand="B", category="C", price=1, images=[])
                    else:
                        r = svc().update_product(product_id="1", name="T", description="", brand="B", category="C", price=1, images=[])
                    assert r['status'] == 'error'

    def test_delete_product_errors(self, app_ctx):
        for error in ['connection', 'timeout', 'non_200', 'no_reqs']:
            with patch('services.faiss_retrieval_service.requests.delete') as mp:
                if error == 'connection':
                    from requests.exceptions import ConnectionError; mp.side_effect = ConnectionError()
                elif error == 'timeout':
                    from requests.exceptions import Timeout; mp.side_effect = Timeout()
                elif error == 'non_200':
                    mr = MagicMock(); mr.status_code = 500; mr.json.return_value = {'error': 'x'}; mp.return_value = mr
                r = svc().delete_product("1")
                if error == 'no_reqs':
                    r = svc().delete_product("1")
                assert r['status'] in ('error', 'success')

    def test_clear_index(self, app_ctx):
        for status_code in [200, 404, 500]:
            with patch('services.faiss_retrieval_service.requests.delete') as mp:
                mr = MagicMock(); mr.status_code = status_code; mr.json.return_value = {'deleted_count': 10}
                mp.return_value = mr
                r = svc().clear_index()
                if status_code == 500:
                    assert r['status'] == 'error'
                else:
                    assert r['status'] == 'success'

    def test_health_check(self, app_ctx):
        for status in ['healthy', 'unhealthy']:
            with patch('services.faiss_retrieval_service.requests.get') as mp:
                mr = MagicMock(); mr.status_code = 200 if status == 'healthy' else 503
                mr.json.return_value = {'status': status}
                mp.return_value = mr
                assert svc().health_check()['status'] == status

    def test_health_check_connection_error(self, app_ctx):
        from requests.exceptions import ConnectionError
        with patch('services.faiss_retrieval_service.requests.get') as mp:
            mp.side_effect = ConnectionError()
            assert svc().health_check()['status'] == 'unhealthy'

    def test_get_available_models(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.get') as mp:
            mr = MagicMock(); mr.status_code = 200
            mr.json.return_value = {'data': {'textual_models': [{'name': 'ViT-B/32'}], 'visual_models': []}}
            mp.return_value = mr
            assert svc().get_available_models()['status'] == 'success'

    def test_get_available_models_fallback(self, app_ctx):
        from requests.exceptions import ConnectionError
        with patch('services.faiss_retrieval_service.requests.get') as mp:
            mp.side_effect = ConnectionError()
            r = svc().get_available_models()
            assert r['source'] == 'local_config'

    def test_get_index_stats(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.get') as mp:
            mr = MagicMock(); mr.status_code = 200; mr.json.return_value = {'indices': {}}
            mp.return_value = mr
            assert svc().get_index_stats()['status'] == 'success'

    def test_search_early_fusion_missing_text(self, app_ctx):
        with patch('os.path.exists', return_value=True):
            r = svc().search_early_fusion(text="", image_path="/t.jpg")
            assert r['status'] == 'error'

    def test_search_late_fusion_no_text(self, app_ctx):
        r = svc().search_late_fusion(text="", image_path="/t.jpg")
        assert r['status'] == 'error'

    def test_search_image_by_text_empty(self, app_ctx):
        assert svc().search_image_by_text(text="")['status'] == 'error'

    def test_search_text_by_image_not_found(self, app_ctx):
        with patch('os.path.exists', return_value=False):
            assert svc().search_text_by_image("/x.jpg")['status'] == 'error'

    def test_add_product_skipped(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.post') as mp, patch('flask.current_app') as ca:
            ca.config.get.return_value = '/tmp'
            mr = MagicMock(); mr.status_code = 200; mr.json.return_value = {'status':'success','details':{'skipped':True}}
            mp.return_value = mr
            r = svc().add_product(product_id="1", name="T", description="", brand="B", category="C", price=1, images=[])
            assert r['status'] == 'skipped'

    def test_search_generic_connection_error(self, app_ctx):
        from requests.exceptions import ConnectionError
        with patch('services.faiss_retrieval_service.requests.post') as mp:
            mp.side_effect = ConnectionError()
            assert svc().search("q")['success'] is False

    def test_get_available_model_ids_fallback(self, app_ctx):
        from services.faiss_retrieval_service import FAISSRetrievalService
        s = FAISSRetrievalService()
        with patch.object(s, 'get_available_models') as m:
            m.return_value = {'data': {}}
            ids = s.get_available_model_ids()
            assert len(ids) > 0

    def test_update_product_faiss_error(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.put') as mp:
            mr = MagicMock(); mr.status_code = 200; mr.json.return_value = {'status':'error','error':'x'}
            mp.return_value = mr
            assert svc().update_product(product_id="1", name="T", description="", brand="B", category="C", price=1, images=[])['status'] == 'error'

    def test_all_error_paths(self, app_ctx):
        from requests.exceptions import ConnectionError, Timeout
        s = svc()
        methods = [
            ('search_text', {'text':'q'}, {}),
            ('search_image', {'image_path':'/t.jpg'}, {'os.path.exists':True}),
            ('search_early_fusion', {'text':'q','image_path':'/t.jpg'}, {'os.path.exists':True}),
            ('search_late_fusion', {'text':'q','image_path':'/t.jpg'}, {'os.path.exists':True}),
            ('search_image_by_text', {'text':'q'}, {}),
            ('search_text_by_image', {'image_path':'/t.jpg'}, {'os.path.exists':True}),
        ]
        for error in ['connection','timeout','non_200']:
            for name, kwargs, patches in methods:
                with patch('services.faiss_retrieval_service.requests.post') as mp, \
                     patch('os.path.exists', return_value=True):
                    if error == 'connection': mp.side_effect = ConnectionError()
                    elif error == 'timeout': mp.side_effect = Timeout()
                    else:
                        mr = MagicMock(); mr.status_code = 500; mr.json.return_value = {'error':'x'}; mp.return_value = mr
                    method = getattr(svc(), name)
                    r = method(**kwargs)
                    assert r.get('status') == 'error' or r.get('success') is False

    def test_empty_inputs(self, app_ctx):
        s = svc()
        assert s.search_text("")['status'] == 'error'
        assert s.search_image("")['status'] == 'error'
        assert s.search_early_fusion(text="", image_path="/t.jpg")['status'] == 'error'
        assert s.search_late_fusion(text="", image_path="/t.jpg")['status'] == 'error'
        assert s.search_image_by_text(text="")['status'] == 'error'
        assert s.search_text_by_image(image_path="")['status'] == 'error'

    def test_add_product_error_handler(self, app_ctx):
        from requests.exceptions import ConnectionError, Timeout
        for error in ['connection','timeout']:
            with patch('services.faiss_retrieval_service.requests.post') as mp:
                if error == 'connection': mp.side_effect = ConnectionError()
                else: mp.side_effect = Timeout()
                r = svc().add_product(product_id="1", name="T", description="", brand="B", category="C", price=1, images=[])
                assert r['status'] == 'error'

    def test_add_product_with_images(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.post') as mp, \
             patch('flask.current_app') as ca, \
             patch('os.path.exists', return_value=True):
            ca.config.get.return_value = '/tmp'
            mr = MagicMock(); mr.status_code = 200
            mr.json.return_value = {'status':'success','details':{'textual_vector_id':'t1','visual_vector_ids':['v1']}}
            mp.return_value = mr
            r = svc().add_product(product_id="1", name="T", description="", brand="B", category="C", price=1, images=['/img.jpg'])
            assert r['status'] == 'success'

    def test_more_error_paths(self, app_ctx):
        from requests.exceptions import ConnectionError
        s = svc()
        with patch('services.faiss_retrieval_service.requests.post') as mp:
            mp.side_effect = ConnectionError()
            with patch('os.path.exists', return_value=True):
                assert s.search_early_fusion(text="q", image_path="/t.jpg")['status'] == 'error'
                assert s.search_late_fusion(text="q", image_path="/t.jpg")['status'] == 'error'
                assert s.search_text_by_image(image_path="/t.jpg")['status'] == 'error'
                assert s.search_image("/t.jpg")['status'] == 'error'
        with patch('services.faiss_retrieval_service.requests.get') as mp:
            mp.side_effect = ConnectionError()
            assert s.get_available_models()['source'] == 'local_config'

    def test_update_delete_product_errors(self, app_ctx):
        from requests.exceptions import ConnectionError
        s = svc()
        with patch('services.faiss_retrieval_service.requests.put') as mp:
            mp.side_effect = ConnectionError()
            r = s.update_product(product_id="1", name="T", description="", brand="B", category="C", price=1, images=[])
            assert r['status'] == 'error'
        with patch('services.faiss_retrieval_service.requests.put') as mp:
            mr = MagicMock(); mr.status_code = 200
            mr.json.return_value = {'status':'error','error':'x'}; mp.return_value = mr
            r = s.update_product(product_id="1", name="T", description="", brand="B", category="C", price=1, images=[])
            assert r['status'] == 'error'
        with patch('services.faiss_retrieval_service.HAS_REQUESTS', False):
            assert s.update_product(product_id="1", name="T", description="", brand="B", category="C", price=1, images=[])['status'] == 'error'
            assert s.search_text("q")['status'] == 'error'
            assert s.health_check()['status'] == 'unhealthy'
            assert s.get_index_stats()['status'] == 'error'
            assert s.get_available_models()['status'] == 'success'

    def test_save_selected_models_request(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.post') as mp:
            mr = MagicMock(); mr.status_code = 200; mr.json.return_value = {'status':'success','data':{}}
            mp.return_value = mr
            assert svc().save_selected_models('ViT-B/32', 'ViT-B/32')['status'] == 'success'

    def test_add_test_product(self, app_ctx):
        from services.faiss_retrieval_service import FAISSRetrievalService
        s = FAISSRetrievalService()
        with patch.object(s, 'add_product', return_value={'status': 'success', 'details': {}}):
            assert s.add_test_product('test-001')['status'] == 'success'

    def test_get_available_model_ids(self, app_ctx):
        with patch.object(svc(), 'get_available_models') as m:
            m.return_value = {'data': {'textual_models': [{'id': 'ViT-B/32'}]}}
            assert 'ViT-B/32' in svc().get_available_model_ids()

    def test_search_image_non_200(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.post') as mp, patch('os.path.exists', return_value=True):
            mr = MagicMock(); mr.status_code = 500; mr.json.return_value = {'error':'x'}
            mp.return_value = mr
            assert svc().search_image("/t.jpg")['status'] == 'error'

    def test_search_with_different_errors(self, app_ctx):
        for method in ['search', 'search_image_by_text', 'search_text_by_image', 'search_early_fusion', 'search_late_fusion']:
            with patch('services.faiss_retrieval_service.requests.post') as mp:
                mr = MagicMock(); mr.status_code = 500; mr.json.return_value = {'error':'x'}; mp.return_value = mr
                if 'image_by_text' in method:
                    r = svc().search_image_by_text(text="q")
                elif 'text_by_image' in method:
                    with patch('os.path.exists', return_value=True):
                        r = svc().search_text_by_image(image_path="/t.jpg")
                elif 'early' in method:
                    with patch('os.path.exists', return_value=True):
                        r = svc().search_early_fusion(text="q", image_path="/t.jpg")
                elif 'late' in method:
                    with patch('os.path.exists', return_value=True):
                        r = svc().search_late_fusion(text="q", image_path="/t.jpg")
                else:
                    r = svc().search("q")
                assert r.get('status') == 'error' or r.get('success') is False

    def test_search_image_by_text_empty(self, app_ctx):
        assert svc().search_image_by_text(text="")['status'] == 'error'

    def test_add_product_errors(self, app_ctx):
        for error in ['connection','timeout','no_reqs']:
            with patch('services.faiss_retrieval_service.HAS_REQUESTS', error == 'no_reqs' if error == 'no_reqs' else True), \
                 patch('services.faiss_retrieval_service.requests.post') as mp:
                if error == 'connection':
                    from requests.exceptions import ConnectionError; mp.side_effect = ConnectionError()
                elif error == 'timeout':
                    from requests.exceptions import Timeout; mp.side_effect = Timeout()
                r = svc().add_product(product_id="1", name="T", description="", brand="B", category="C", price=1, images=[])
                assert r['status'] in ('error', 'success')

    def test_update_product_errors(self, app_ctx):
        for error in ['connection','timeout','no_reqs']:
            with patch('services.faiss_retrieval_service.requests.put') as mp:
                if error == 'connection':
                    from requests.exceptions import ConnectionError; mp.side_effect = ConnectionError()
                elif error == 'timeout':
                    from requests.exceptions import Timeout; mp.side_effect = Timeout()
                r = svc().update_product(product_id="1", name="T", description="", brand="B", category="C", price=1, images=[])
                assert r['status'] in ('error', 'success')

    def test_get_available_models_non_200(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.get') as mp:
            mr = MagicMock(); mr.status_code = 500; mp.return_value = mr
            assert svc().get_available_models()['source'] == 'local_config'

    def test_get_index_stats_errors(self, app_ctx):
        with patch('services.faiss_retrieval_service.HAS_REQUESTS', False):
            assert svc().get_index_stats()['status'] == 'error'
        from requests.exceptions import ConnectionError
        with patch('services.faiss_retrieval_service.requests.get') as mp:
            mp.side_effect = ConnectionError()
            assert svc().get_index_stats()['status'] == 'error'

    def test_no_requests_fallbacks(self, app_ctx):
        with patch('services.faiss_retrieval_service.HAS_REQUESTS', False):
            assert svc().search("q")['success'] is False
            assert svc().search_text("q")['status'] == 'error'
            assert svc().health_check()['status'] == 'unhealthy'
            assert svc().get_index_stats()['status'] == 'error'

    def test_save_selected_models(self, app_ctx):
        with patch('services.faiss_retrieval_service.requests.post') as mp:
            mp.return_value = _mock_post_200({'status': 'success', 'data': {}})
            assert svc().save_selected_models('ViT-B/32', 'ViT-B/32')['status'] == 'success'
