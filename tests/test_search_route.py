from io import BytesIO
from unittest.mock import patch

import pytest
from flask import Flask

from routes.search import search_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(search_bp)

    with app.test_client() as test_client:
        yield test_client


@patch("routes.search.get_selected_fusion_endpoint", return_value="late")
@patch("routes.search.build_query_image_response")
@patch("routes.search.save_search_image")
@patch("routes.search.SearchService.execute_search")
def test_search_returns_query_image_for_uploaded_file(
    mock_execute_search,
    mock_save_search_image,
    mock_build_query_image_response,
    mock_get_selected_fusion_endpoint,
    client,
):
    mock_execute_search.return_value = {"search_id": 42}
    mock_save_search_image.return_value = "uploads/products/search_test.jpg"
    mock_build_query_image_response.return_value = {
        "filename": "search_test.jpg",
        "url": "/uploads/products/search_test.jpg",
        "data_url": "data:image/jpeg;base64,ZmFrZQ==",
    }

    response = client.post(
        "/api/search",
        data={
            "raw_text": "telefon",
            "images": (BytesIO(b"fake-image-bytes"), "query.jpg"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert response.get_json() == {
        "search_id": 42,
        "query_image": {
            "filename": "search_test.jpg",
            "url": "/uploads/products/search_test.jpg",
            "data_url": "data:image/jpeg;base64,ZmFrZQ==",
        },
    }

    mock_save_search_image.assert_called_once()
    mock_execute_search.assert_called_once_with(
        "telefon",
        "uploads/products/search_test.jpg",
        engine=None,
        semantic_search_enabled=True,
        correction_enabled=True,
        search_mode="std",
    )
    mock_build_query_image_response.assert_called_once_with(
        "uploads/products/search_test.jpg"
    )


@patch("routes.search.SearchService.get_search_by_id")
def test_get_search_returns_persisted_query_image(mock_get_search_by_id, client):
    mock_get_search_by_id.return_value = {
        "search_id": 42,
        "raw_text": "telefon",
        "corrected_text": "telefon",
        "query_image": {
            "filename": "search_test.jpg",
            "url": "/uploads/products/search_test.jpg",
            "data_url": "data:image/jpeg;base64,ZmFrZQ==",
        },
        "products": [],
    }

    response = client.get("/api/search/42")

    assert response.status_code == 200
    assert response.get_json()["query_image"] == {
        "filename": "search_test.jpg",
        "url": "/uploads/products/search_test.jpg",
        "data_url": "data:image/jpeg;base64,ZmFrZQ==",
    }
    mock_get_search_by_id.assert_called_once_with(42)
