import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from unittest.mock import patch, MagicMock
from services.text_corrector_service import TextCorrectorService

@pytest.fixture
def s(): return TextCorrectorService(base_url='http://m:5001/correct')

class TestTextCorrector:
    def test_correct_success(self, s):
        with patch('services.text_corrector_service.requests.post') as mp:
            mr = MagicMock(); mr.json.return_value = {'corrected_query':'iphone','changed':True,'latency_ms':10,'model_used':'b'}
            mp.return_value = mr
            r = s.correct("iphone")
            assert r['corrected_text'] == 'iphone' and r['success'] is True

    def test_correct_errors(self, s):
        for error in ['connection','timeout','generic']:
            with patch('services.text_corrector_service.requests.post') as mp:
                if error == 'connection':
                    from requests.exceptions import ConnectionError; mp.side_effect = ConnectionError()
                elif error == 'timeout':
                    from requests.exceptions import Timeout; mp.side_effect = Timeout()
                else:
                    mr = MagicMock(); mr.raise_for_status.side_effect = Exception('x'); mp.return_value = mr
                r = s.correct("test")
                assert r['success'] is False and r['corrected_text'] == 'test'

    def test_available_models(self, s):
        with patch('services.text_corrector_service.requests.get') as mp:
            mr = MagicMock(); mr.status_code = 200; mr.json.return_value = {'data':{'correction_models':[]}}
            mp.return_value = mr
            assert s.get_available_models()['status'] == 'success'

    def test_correct_no_changed(self, s):
        with patch('services.text_corrector_service.requests.post') as mp:
            mr = MagicMock(); mr.json.return_value = {'corrected_query':'x','changed':False}
            mp.return_value = mr
            assert s.correct("x")['changed'] is False

    def test_get_available_models_no_requests(self, s):
        with patch('services.text_corrector_service.HAS_REQUESTS', False):
            assert s.get_available_models()['status'] == 'success'

    def test_available_models_fallback(self, s):
        with patch('services.text_corrector_service.requests.get') as mp:
            mp.side_effect = Exception('err')
            assert s.get_available_models()['source'] == 'local_config'

    def test_save_engine(self, s):
        assert s.save_selected_engine('symspell')['status'] == 'success'
