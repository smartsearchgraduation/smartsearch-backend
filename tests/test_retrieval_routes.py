from unittest.mock import patch

import pytest
from flask import Flask

from routes.retrieval import retrieval_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(retrieval_bp)

    with app.test_client() as test_client:
        yield test_client


@patch("models.product.Product")
@patch("sqlalchemy.orm.joinedload", side_effect=lambda value: value)
@patch("routes.retrieval.faiss_service.clear_index")
@patch("routes.retrieval.faiss_service.get_available_models")
@patch("routes.retrieval.get_selected_fusion_endpoint", return_value="late")
@patch("routes.retrieval.save_selected_models")
def test_save_and_rebuild_accepts_model_advertised_by_faiss(
    mock_save_selected_models,
    mock_get_selected_fusion_endpoint,
    mock_get_available_models,
    mock_clear_index,
    mock_joinedload,
    mock_product,
    client,
):
    model_id = "Marqo/marqo-ecommerce-embeddings-L"
    mock_get_available_models.return_value = {
        "status": "success",
        "data": {
            "textual_models": [{"id": model_id, "name": model_id}],
            "visual_models": [{"id": model_id, "name": model_id}],
        },
    }
    mock_clear_index.return_value = {"status": "success"}
    mock_product.query.filter_by.return_value.options.return_value.all.return_value = []

    response = client.post(
        "/api/retrieval/selected-models/save-and-rebuild",
        json={
            "textual_model": model_id,
            "visual_model": model_id,
            "fusion_endpoint": "late",
            "wait_duration_seconds": 0,
        },
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "status": "error",
        "error": "No products found in database",
    }
    mock_save_selected_models.assert_called_once_with(model_id, model_id, "late", model_id)


@patch("routes.retrieval.save_selected_models")
@patch("routes.retrieval.faiss_service.get_available_models")
def test_selected_models_accepts_fused_model_advertised_by_faiss(
    mock_get_available_models,
    mock_save_selected_models,
    client,
):
    textual_model = "BAAI/bge-large-en-v1.5"
    visual_model = "facebook/dinov3-vit7b16-pretrain-lvd1689m"
    fused_model = "Marqo/marqo-ecommerce-embeddings-L"
    mock_get_available_models.return_value = {
        "status": "success",
        "data": {
            "textual_models": [{"id": textual_model, "name": textual_model}],
            "visual_models": [{"id": visual_model, "name": visual_model}],
            "fused_models": [{"id": fused_model, "name": fused_model}],
        },
    }

    response = client.post(
        "/api/retrieval/selected-models",
        json={
            "textual_model": textual_model,
            "visual_model": visual_model,
            "fused_model": fused_model,
            "fusion_endpoint": "early",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["data"] == {
        "textual_model": textual_model,
        "visual_model": visual_model,
        "fused_model": fused_model,
        "fusion_endpoint": "early",
    }
    mock_save_selected_models.assert_called_once_with(
        textual_model, visual_model, "early", fused_model
    )
