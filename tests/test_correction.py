import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from unittest.mock import patch
from flask import Flask

@pytest.fixture
def c():
    a = Flask(__name__); a.config['TESTING'] = True
    from routes.correction import correction_bp; a.register_blueprint(correction_bp)
    with a.test_client() as cl: yield cl

class TestCorrection:
    @patch('routes.correction.text_corrector_service.get_available_models')
    def test_models_error(self, mg, c):
        mg.return_value = {'status':'error','error':'x'}
        assert c.get('/api/correction/models').status_code == 500
    @patch('routes.correction.text_corrector_service.get_available_models')
    def test_models(self, mg, c):
        mg.return_value = {'status':'success','data':{'engines':[]},'source':'local'}
        assert c.get('/api/correction/models').status_code == 200

    @patch('routes.correction.text_corrector_service.get_available_models')
    def test_models_exception(self, mg, c):
        mg.side_effect = Exception('err')
        assert c.get('/api/correction/models').status_code == 500

    @patch('routes.correction.text_corrector_service.save_selected_engine')
    def test_save_engine(self, ms, c):
        ms.return_value = {'status':'success','message':'ok','data':{'engine':'s'}}
        assert c.post('/api/correction/selected-engine/save', json={'engine':'s'}).status_code == 200
        assert c.post('/api/correction/selected-engine/save', json={}).status_code == 400


        ms.return_value = {'status':'success','message':'ok','data':{'engine':'s'}}
        assert c.post('/api/correction/selected-engine/save', json={'engine':'s'}).status_code == 200
        assert c.post('/api/correction/selected-engine/save', json={}).status_code == 400
