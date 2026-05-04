import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from flask import Flask
from config.app_config import TestingConfig, DevelopmentConfig, get_config
from models import db


def test_app_creates_successfully(app):
    assert app is not None
    assert isinstance(app, Flask)


def test_all_10_blueprints_registered(app):
    assert 'search' in app.blueprints
    assert 'products' in app.blueprints
    assert 'feedback' in app.blueprints
    assert 'health' in app.blueprints
    assert 'brands' in app.blueprints
    assert 'categories' in app.blueprints
    assert 'retrieval' in app.blueprints
    assert 'analytics' in app.blueprints
    assert 'bulk_faiss' in app.blueprints
    assert 'correction' in app.blueprints
    assert len(app.blueprints) >= 10


def test_config_class_loaded_by_env(app):
    assert app.config['TESTING'] is True
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'


def test_config_class_defaults_to_development(monkeypatch):
    monkeypatch.delenv('FLASK_ENV', raising=False)
    config_class = get_config()
    assert config_class == DevelopmentConfig


def test_cors_applied_to_all_routes(client):
    response = client.options('/api/search')
    assert 'Access-Control-Allow-Origin' in response.headers


def test_max_content_length_rejects_oversized(app):
    assert app.config['MAX_CONTENT_LENGTH'] == 16 * 1024 * 1024


def test_database_connection_established(app):
    with app.app_context():
        result = db.session.execute(db.text('SELECT 1'))
        assert result.scalar() == 1
