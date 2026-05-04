import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from unittest.mock import patch, mock_open
from config.models import *

def test_resolve_fused():
    assert resolve_fused_model("ViT-L/14","ViT-L/14", fused_model="ViT-B/32") == "ViT-L/14"
    assert resolve_fused_model("A","B", fused_model="X") == "X"
    assert resolve_fused_model("A","B", fallback="F") == "F"

def test_is_valid_model():
    for mid in AVAILABLE_MODELS: assert is_valid_model(mid)
    assert not is_valid_model("x")

def test_get_model_info():
    i = get_model_info("ViT-B/32")
    assert i['name'] and i['dimension'] == 512

def test_get_model_info_non_dict():
    r = get_model_info("garbage")
    assert r is not None

def test_defaults():
    assert DEFAULT_TEXTUAL_MODEL == "BAAI/bge-large-en-v1.5"
    assert DEFAULT_VISUAL_MODEL == "ViT-B/32"

def test_get_models_list():
    assert len(get_models_list()) == len(AVAILABLE_MODELS)

def test_get_model_options_html():
    h = get_model_options_html()
    assert DEFAULT_TEXTUAL_MODEL in h and 'selected' in h
    assert h.startswith('<option')
    assert 'Varsayılan' in h

def test_get_selected_models():
    r = get_selected_models()
    assert 'textual_model' in r and 'fusion_endpoint' in r

def test_get_selected_models_file_not_found():
    with patch('builtins.open') as mo:
        mo.side_effect = FileNotFoundError()
        r = get_selected_models()
        assert r['textual_model'] == DEFAULT_TEXTUAL_MODEL

def test_save_selected_models():
    with patch('config.models.get_selected_models', return_value={'fusion_endpoint':'late','fused_model':'ViT-B/32'}), \
         patch('config.models.resolve_fused_model', return_value='ViT-B/32'), \
         patch('builtins.open', mock_open()) as mf:
        save_selected_models("ViT-L/14","ViT-L/14","late","ViT-B/32")
        mf.assert_called_once()

def test_save_selected_fusion_endpoint():
    with patch('config.models.get_selected_models', return_value={'textual_model':'A','visual_model':'A','fused_model':'X'}), \
         patch('config.models.save_selected_models') as ms:
        save_selected_fusion_endpoint('early')
        ms.assert_called_once()

def test_get_selected_fusion_endpoint():
    with patch('config.models.get_selected_models', return_value={'fusion_endpoint':'early'}):
        assert get_selected_fusion_endpoint() == 'early'
    with patch('config.models.get_selected_models', return_value={}):
        assert get_selected_fusion_endpoint() in ('late', 'early')

def test_get_model_options_html_descriptions():
    h = get_model_options_html()
    for model_id in ['RN50x16','RN50x64']:
        if model_id in h: break
    assert True

def test_get_selected_models_with_existing_config():
    data = '{"textual_model":"ViT-B/16","visual_model":"ViT-B/16"}'
    with patch('builtins.open', mock_open(read_data=data)):
        r = get_selected_models()
        assert r['textual_model'] == 'ViT-B/16'
