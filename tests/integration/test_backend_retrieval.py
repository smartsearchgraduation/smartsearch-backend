"""
Backend-to-Retrieval integration tests (BR-INT-001..BR-INT-030).

Spec: validates Backend (Flask) routes + services against a mocked FAISS
Retrieval microservice. The downstream FAISS service is patched at the
`requests.post/get/put/delete` boundary inside
`Backend/services/faiss_retrieval_service.py` — no real network calls. Where a
test exercises the full search orchestration (`/api/search`), the SearchService
collaborator services (`text_corrector_service`, `faiss_service`) are patched
directly.

Each test function maps 1:1 to a row in `backend_to_retrieval.md`. Function
names embed the case ID with hyphens replaced by underscores.
"""
import json
import os
import sys
from unittest.mock import patch, MagicMock, ANY

import pytest

# Ensure Backend root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from models import db as _db
from models.search_query import SearchQuery
from models.search_time import SearchTime
from models.retrieve import Retrieve


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(json_data, status_code=200):
    """Build a fake `requests.Response`-shaped MagicMock."""
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is None:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = json_data
    resp.text = json.dumps(json_data) if json_data is not None else ""
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _wipe_db(app):
    """Wipe DB tables between tests so session-scoped app stays clean."""
    with app.app_context():
        _db.session.query(Retrieve).delete()
        _db.session.query(SearchTime).delete()
        _db.session.query(SearchQuery).delete()
        _db.session.commit()
    yield
    with app.app_context():
        _db.session.rollback()


@pytest.fixture
def mock_faiss_post():
    """Patch outbound `requests.post` used by faiss_retrieval_service."""
    with patch("services.faiss_retrieval_service.requests.post") as m:
        yield m


@pytest.fixture
def mock_faiss_get():
    with patch("services.faiss_retrieval_service.requests.get") as m:
        yield m


@pytest.fixture
def mock_faiss_put():
    with patch("services.faiss_retrieval_service.requests.put") as m:
        yield m


@pytest.fixture
def mock_faiss_delete():
    with patch("services.faiss_retrieval_service.requests.delete") as m:
        yield m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBackendRetrievalIntegration:

    # -------------------------------------------------------------------
    # /api/retrieval/search/text
    # -------------------------------------------------------------------
    def test_BR_INT_001_search_text_forwards_query(self, client, mock_faiss_post):
        """BR-INT-001: Verify that POST /api/retrieval/search/text forwards a valid text query to FAISS and returns its products payload."""
        # --- Step 1: Patch requests.post to return canned FAISS response
        mock_faiss_post.return_value = _make_response(
            {
                "status": "success",
                "products": [{"product_id": "p1", "score": 0.91}],
            }
        )

        # --- Step 2: POST text search request
        resp = client.post(
            "/api/retrieval/search/text",
            json={"text": "running shoes", "top_k": 5},
        )

        # --- Step 3: Assert HTTP 200 and JSON shape
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "success"
        assert isinstance(body["products"], list) and len(body["products"]) >= 1
        first = body["products"][0]
        assert "product_id" in first and "score" in first

    def test_BR_INT_002_search_text_empty_body(self, client):
        """BR-INT-002: Verify that POST /api/retrieval/search/text returns 400 when the request body is empty."""
        # --- Step 1: POST with empty JSON body (explicit content-type so
        # Flask's get_json() doesn't raise 415 on this empty payload)
        resp = client.post(
            "/api/retrieval/search/text",
            data="{}",
            content_type="application/json",
        )
        # --- Step 2: Assert HTTP 400 and `error` key
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get("status") == "error"
        assert body.get("error") == "Request body is required"

    def test_BR_INT_003_search_text_missing_text_field(self, client):
        """BR-INT-003: Verify that POST /api/retrieval/search/text returns 400 when the `text` field is missing."""
        # --- Step 1: POST with body lacking `text`
        resp = client.post("/api/retrieval/search/text", json={"top_k": 5})
        # --- Step 2: Assert HTTP 400
        assert resp.status_code == 400
        body = resp.get_json()
        assert "Missing required field: text" in body.get("error", "")

    # -------------------------------------------------------------------
    # /api/retrieval/search/late
    # -------------------------------------------------------------------
    def test_BR_INT_004_search_late_image_only(self, client):
        """BR-INT-004: Verify that POST /api/retrieval/search/late requires both text and image and returns 400 when image only is given."""
        # --- Step 1: POST late fusion with image-only body
        resp = client.post(
            "/api/retrieval/search/late",
            json={"image": "/tmp/q.jpg"},
        )
        # --- Step 2: Assert HTTP 400 and rejection message
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get("error") == "Text is required for late fusion search"

    def test_BR_INT_005_search_late_happy_path(self, client, mock_faiss_post, tmp_path):
        """BR-INT-005: Verify that POST /api/retrieval/search/late happy path forwards both modalities and returns the FAISS result."""
        # --- Step 1: Create temp image file
        image_path = tmp_path / "query.jpg"
        image_path.write_bytes(b"fakejpeg")

        # --- Step 2: Patch FAISS to return a late-fusion product
        mock_faiss_post.return_value = _make_response(
            {
                "status": "success",
                "products": [
                    {
                        "product_id": "p1",
                        "text_score": 0.7,
                        "image_score": 0.6,
                        "combined_score": 0.65,
                    }
                ],
            }
        )

        # --- Step 3: POST late fusion search
        resp = client.post(
            "/api/retrieval/search/late",
            json={
                "text": "red shoe",
                "image": str(image_path),
                "text_weight": 0.7,
            },
        )

        # --- Expected Output
        assert resp.status_code == 200
        body = resp.get_json()
        first = body["products"][0]
        assert first["text_score"] == 0.7
        assert first["image_score"] == 0.6
        assert first["combined_score"] == 0.65

    # -------------------------------------------------------------------
    # /api/retrieval/search/early
    # -------------------------------------------------------------------
    def test_BR_INT_006_search_early_image_only(self, client):
        """BR-INT-006: Verify that POST /api/retrieval/search/early returns 400 when only image is provided."""
        # --- Step 1: POST early fusion with image-only body
        resp = client.post(
            "/api/retrieval/search/early",
            json={"image": "/tmp/q.jpg"},
        )
        # --- Step 2: Assert HTTP 400
        assert resp.status_code == 400
        body = resp.get_json()
        assert "Missing required field: text" in body.get("error", "")

    # -------------------------------------------------------------------
    # /api/retrieval/search/image
    # -------------------------------------------------------------------
    def test_BR_INT_007_search_image_missing_image(self, client):
        """BR-INT-007: Verify that POST /api/retrieval/search/image returns 400 when `image` field is missing."""
        # --- Step 1: POST image search with body missing `image`
        resp = client.post(
            "/api/retrieval/search/image",
            json={"top_k": 5},
        )
        # --- Step 2: Assert HTTP 400
        assert resp.status_code == 400
        body = resp.get_json()
        assert "Missing required field: image" in body.get("error", "")

    # -------------------------------------------------------------------
    # /api/retrieval/search/image-by-text
    # -------------------------------------------------------------------
    def test_BR_INT_008_search_image_by_text_whitespace(self, client):
        """BR-INT-008: Verify that POST /api/retrieval/search/image-by-text rejects empty whitespace text with 400."""
        # --- Step 1: POST with whitespace-only text
        resp = client.post(
            "/api/retrieval/search/image-by-text",
            json={"text": "   "},
        )
        # --- Step 2: Assert HTTP 400
        assert resp.status_code == 400
        body = resp.get_json()
        assert "Missing required field: text" in body.get("error", "")

    # -------------------------------------------------------------------
    # /api/retrieval/search/text-by-image
    # -------------------------------------------------------------------
    def test_BR_INT_009_search_text_by_image_happy_path(
        self, client, mock_faiss_post, tmp_path
    ):
        """BR-INT-009: Verify that POST /api/retrieval/search/text-by-image forwards image path to FAISS and returns 200 with results."""
        # --- Step 1: Create temp image
        image_path = tmp_path / "tbi.jpg"
        image_path.write_bytes(b"fakejpeg")

        # --- Step 2: Patch FAISS to use the alternative `results` key
        mock_faiss_post.return_value = _make_response(
            {
                "status": "success",
                "results": [{"product_id": "p2", "score": 0.42}],
            }
        )

        # --- Step 3: POST text-by-image
        resp = client.post(
            "/api/retrieval/search/text-by-image",
            json={
                "image": str(image_path),
                "fused_model_name": "ViT-B/32",
                "top_k": 3,
            },
        )

        # --- Expected Output
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("status") == "success"
        # Either products or results may carry the entries
        entries = body.get("products") or body.get("results") or []
        assert len(entries) >= 1

    # -------------------------------------------------------------------
    # /api/retrieval/add-product
    # -------------------------------------------------------------------
    def test_BR_INT_010_add_product_happy_path(self, client, mock_faiss_post):
        """BR-INT-010: Verify that POST /api/retrieval/add-product happy path returns 200 with textual_vector_id and visual_vector_ids."""
        # --- Step 1: Patch FAISS to return vector ids
        mock_faiss_post.return_value = _make_response(
            {
                "status": "success",
                "details": {
                    "textual_vector_id": 42,
                    "visual_vector_ids": [1, 2, 3],
                },
            }
        )

        # --- Step 2: POST minimal valid product body
        resp = client.post(
            "/api/retrieval/add-product",
            json={
                "id": "sku-001",
                "name": "Cotton T-Shirt",
                "description": "Soft cotton tee",
                "brand": "Acme",
                "category": "Tops",
                "price": 19.99,
                "images": [],
            },
        )

        # --- Expected Output
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("status") == "success"
        details = body.get("details", {})
        assert details.get("textual_vector_id") == 42
        assert details.get("visual_vector_ids") == [1, 2, 3]
        assert details.get("images_processed") == 3

    def test_BR_INT_011_add_product_missing_id(self, client):
        """BR-INT-011: Verify that POST /api/retrieval/add-product returns 400 when `id` is missing."""
        # --- Step 1: POST without `id`
        resp = client.post(
            "/api/retrieval/add-product",
            json={"name": "X"},
        )
        # --- Step 2: Assert HTTP 400
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get("error") == "Missing required field: id"

    def test_BR_INT_012_add_product_missing_name(self, client):
        """BR-INT-012: Verify that POST /api/retrieval/add-product returns 400 when `name` is missing."""
        # --- Step 1: POST without `name`
        resp = client.post(
            "/api/retrieval/add-product",
            json={"id": "sku-001"},
        )
        # --- Step 2: Assert HTTP 400
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get("error") == "Missing required field: name"

    def test_BR_INT_013_add_product_invalid_price(self, client):
        """BR-INT-013: Verify that POST /api/retrieval/add-product returns 400 when `price` is not coercible to float."""
        # --- Step 1: POST with non-numeric price
        resp = client.post(
            "/api/retrieval/add-product",
            json={"id": "sku-1", "name": "X", "price": "not-a-number"},
        )
        # --- Step 2: Assert HTTP 400
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get("error") == "Invalid price value"

    def test_BR_INT_014_add_product_skipped(self, client, mock_faiss_post):
        """BR-INT-014: Verify that POST /api/retrieval/add-product returns the skipped shape when FAISS reports the product already has embeddings for the active model."""
        # --- Step 1: Patch FAISS to return skipped flag
        mock_faiss_post.return_value = _make_response(
            {
                "status": "success",
                "details": {"skipped": True},
            }
        )

        # --- Step 2: POST a valid body
        resp = client.post(
            "/api/retrieval/add-product",
            json={
                "id": "sku-001",
                "name": "Cotton T-Shirt",
                "price": 9.99,
            },
        )

        # --- Expected Output
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("status") == "skipped"
        assert "already has embeddings" in (body.get("message") or "")

    def test_BR_INT_015_add_product_missing_textual_vector_id(
        self, client, mock_faiss_post
    ):
        """BR-INT-015: Verify that POST /api/retrieval/add-product propagates HTTP 500 when FAISS returns success but no textual_vector_id."""
        # --- Step 1: Patch FAISS to return success with no textual_vector_id
        mock_faiss_post.return_value = _make_response(
            {
                "status": "success",
                "details": {"visual_vector_ids": [1]},
            }
        )

        # --- Step 2: POST a valid body
        resp = client.post(
            "/api/retrieval/add-product",
            json={
                "id": "sku-1",
                "name": "X",
                "price": 1.0,
            },
        )

        # --- Expected Output
        assert resp.status_code == 500
        body = resp.get_json()
        assert body.get("status") == "error"
        assert "textual vector" in (body.get("error") or "").lower()

    # -------------------------------------------------------------------
    # /api/retrieval/update-product/<id>
    # -------------------------------------------------------------------
    def test_BR_INT_016_update_product_url_contains_id(
        self, client, mock_faiss_put
    ):
        """BR-INT-016: Verify that PUT /api/retrieval/update-product/<id> builds the FAISS URL with the path parameter and returns 200 on success."""
        # --- Step 1: Patch FAISS PUT to return success
        mock_faiss_put.return_value = _make_response(
            {
                "status": "success",
                "details": {"updated": True},
            }
        )

        # --- Step 2: PUT to update-product/sku-9
        resp = client.put(
            "/api/retrieval/update-product/sku-9",
            json={"name": "X", "price": 1.0},
        )

        # --- Expected Output
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("details", {}).get("updated") is True

        # --- Step 3: Assert URL includes sku-9
        assert mock_faiss_put.called
        called_url = mock_faiss_put.call_args[0][0]
        assert "/update-product/sku-9" in called_url

    # -------------------------------------------------------------------
    # /api/retrieval/delete-product/<id>
    # -------------------------------------------------------------------
    def test_BR_INT_017_delete_product_404_translated(
        self, client, mock_faiss_delete
    ):
        """BR-INT-017: Verify that DELETE /api/retrieval/delete-product/<id> translates FAISS 404 into a 200 success with `not in FAISS index` message."""
        # --- Step 1: Patch FAISS DELETE to return 404
        mock_faiss_delete.return_value = _make_response({}, status_code=404)

        # --- Step 2: DELETE /delete-product/missing-sku
        resp = client.delete("/api/retrieval/delete-product/missing-sku")

        # --- Expected Output
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("status") == "success"
        assert "not in FAISS index" in (body.get("message") or "")

    def test_BR_INT_018_delete_product_500_propagated(
        self, client, mock_faiss_delete
    ):
        """BR-INT-018: Verify that DELETE /api/retrieval/delete-product/<id> propagates a FAISS 500 as an error response."""
        # --- Step 1: Patch FAISS DELETE to return 500
        mock_faiss_delete.return_value = _make_response(
            {"error": "boom"}, status_code=500
        )

        # --- Step 2: DELETE /delete-product/sku-9
        resp = client.delete("/api/retrieval/delete-product/sku-9")

        # --- Expected Output
        assert resp.status_code == 500
        body = resp.get_json()
        assert body.get("status") == "error"
        assert "FAISS Error (500)" in (body.get("error") or "")

    # -------------------------------------------------------------------
    # /api/retrieval/index-stats
    # -------------------------------------------------------------------
    def test_BR_INT_019_index_stats(self, client, mock_faiss_get):
        """BR-INT-019: Verify that GET /api/retrieval/index-stats returns the FAISS-provided data and indices payload."""
        # --- Step 1: Patch FAISS GET to return stats
        mock_faiss_get.return_value = _make_response(
            {
                "status": "success",
                "data": {"models": {"ViT-B/32": {"textual": 10}}},
            }
        )

        # --- Step 2: GET /index-stats
        resp = client.get("/api/retrieval/index-stats")

        # --- Expected Output
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("status") == "success"
        assert "data" in body
        assert "indices" in body

    # -------------------------------------------------------------------
    # /api/retrieval/models
    # -------------------------------------------------------------------
    def test_BR_INT_020_models_local_fallback(self, client, mock_faiss_get):
        """BR-INT-020: Verify that GET /api/retrieval/models falls back to local config when the FAISS service is offline."""
        # --- Step 1: Make requests.get raise ConnectionError
        import requests as _requests
        mock_faiss_get.side_effect = _requests.exceptions.ConnectionError("boom")

        # --- Step 2: GET /models
        resp = client.get("/api/retrieval/models")

        # --- Expected Output
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("status") == "success"
        assert body.get("source") == "local_config"
        assert len(body.get("data", {}).get("textual_models", [])) > 0

    # -------------------------------------------------------------------
    # /api/retrieval/selected-models  (POST validation)
    # -------------------------------------------------------------------
    def test_BR_INT_021_selected_models_invalid_textual(self, client):
        """BR-INT-021: Verify that POST /api/retrieval/selected-models rejects an unknown textual model name."""
        # --- Step 1: Patch faiss_service.get_available_model_ids to a known list
        with patch(
            "routes.retrieval.faiss_service.get_available_model_ids",
            return_value=["ViT-B/32", "ViT-L/14"],
        ):
            # --- Step 2: POST with a bogus textual model
            resp = client.post(
                "/api/retrieval/selected-models",
                json={"textual_model": "BOGUS", "visual_model": "ViT-B/32"},
            )

        # --- Expected Output
        assert resp.status_code == 400
        body = resp.get_json()
        assert "Invalid textual model: BOGUS" in (body.get("error") or "")

    # -------------------------------------------------------------------
    # /api/retrieval/fusion-endpoint  (POST validation)
    # -------------------------------------------------------------------
    def test_BR_INT_022_fusion_endpoint_invalid(self, client):
        """BR-INT-022: Verify that POST /api/retrieval/fusion-endpoint rejects a value outside {late, early}."""
        # --- Step 1: POST with invalid fusion_endpoint
        resp = client.post(
            "/api/retrieval/fusion-endpoint",
            json={"fusion_endpoint": "middle"},
        )

        # --- Step 2: Assert HTTP 400
        assert resp.status_code == 400
        body = resp.get_json()
        assert "Invalid fusion_endpoint: middle" in (body.get("error") or "")

    # -------------------------------------------------------------------
    # /api/retrieval/clear-index
    # -------------------------------------------------------------------
    def test_BR_INT_023_clear_index_success(self, client, mock_faiss_delete):
        """BR-INT-023: Verify that DELETE /api/retrieval/clear-index proxies a 200 success response with deleted_count."""
        # --- Step 1: Patch FAISS DELETE to return 200 with deleted_count
        mock_faiss_delete.return_value = _make_response({"deleted_count": 12})

        # --- Step 2: DELETE /clear-index
        resp = client.delete("/api/retrieval/clear-index")

        # --- Expected Output
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("status") == "success"
        assert body.get("details", {}).get("deleted_count") == 12

    def test_BR_INT_024_clear_index_endpoint_missing(
        self, client, mock_faiss_delete
    ):
        """BR-INT-024: Verify that DELETE /api/retrieval/clear-index returns success with note when FAISS responds 404."""
        # --- Step 1: Patch FAISS DELETE to return 404
        mock_faiss_delete.return_value = _make_response({}, status_code=404)

        # --- Step 2: DELETE /clear-index
        resp = client.delete("/api/retrieval/clear-index")

        # --- Expected Output
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("status") == "success"
        assert "endpoint" in (body.get("message") or "").lower()
        assert body.get("details", {}).get("deleted_count") == 0

    # -------------------------------------------------------------------
    # /api/search  (full orchestrator flow that calls FAISS)
    # -------------------------------------------------------------------
    def test_BR_INT_025_search_flow_text_only_persists(self, app, client):
        """BR-INT-025: Verify that the POST /api/search flow (text only) calls faiss_service.search_text and persists a SearchQuery row whose ID is returned."""
        # --- Step 1: Patch correction + FAISS service entry points
        with patch(
            "services.search_service.text_corrector_service.correct"
        ) as mock_correct, patch(
            "services.search_service.faiss_service"
        ) as mock_faiss:
            mock_correct.return_value = {
                "corrected_text": "laptop",
                "engine": "symspell",
                "latency_ms": 1.0,
            }
            mock_faiss.search_text.return_value = {
                "status": "success",
                "products": [{"product_id": 1, "score": 0.8}],
            }

            # --- Step 2: POST form-encoded search
            resp = client.post(
                "/api/search",
                data={
                    "raw_text": "laptop",
                    "search_mode": "std",
                    "correction_enabled": "true",
                },
                content_type="application/x-www-form-urlencoded",
            )

        # --- Step 3: Assertions
        assert resp.status_code == 201
        body = resp.get_json()
        search_id = body.get("search_id")
        assert isinstance(search_id, int)

        # Verify DB persistence
        with app.app_context():
            row = _db.session.get(SearchQuery, search_id)
            assert row is not None
            assert row.corrected_text == "laptop"
            retrieves = _db.session.query(Retrieve).filter_by(
                search_id=search_id
            ).all()
            assert len(retrieves) == 1
            assert retrieves[0].product_id == 1

    def test_BR_INT_026_search_flow_empty_no_db_fallback(self, app, client):
        """BR-INT-026: Verify that the POST /api/search flow returns empty results (no DB fallback) when FAISS reports an empty list."""
        # --- Step 1: Patch correction + FAISS to return empty
        with patch(
            "services.search_service.text_corrector_service.correct"
        ) as mock_correct, patch(
            "services.search_service.faiss_service"
        ) as mock_faiss:
            mock_correct.return_value = {
                "corrected_text": "zxcvbn",
                "engine": "symspell",
                "latency_ms": 1.0,
            }
            mock_faiss.search_text.return_value = {
                "products": [],
                "success": False,
            }

            # --- Step 2: POST search
            resp = client.post(
                "/api/search",
                data={"raw_text": "zxcvbn"},
                content_type="application/x-www-form-urlencoded",
            )
            assert resp.status_code == 201
            search_id = resp.get_json().get("search_id")

            # --- Step 3: GET /api/search/<id>
            get_resp = client.get(f"/api/search/{search_id}")

        # --- Expected Output
        assert get_resp.status_code == 200
        body = get_resp.get_json()
        assert body.get("products", []) == []

        with app.app_context():
            retrieves = _db.session.query(Retrieve).filter_by(
                search_id=search_id
            ).all()
            assert len(retrieves) == 0

    def test_BR_INT_027_search_flow_late_fusion_dispatch(
        self, app, client, tmp_path
    ):
        """BR-INT-027: Verify that the POST /api/search flow with both text and image dispatches to search_late_fusion when fusion_endpoint=='late'."""
        # --- Step 1: Build a real image file on disk
        image_path = tmp_path / "search.jpg"
        image_path.write_bytes(b"\xff\xd8\xff\xe0fake")  # JPEG magic header

        # --- Step 2: Patch fusion config + FAISS late-fusion entry point
        with patch(
            "services.search_service.get_selected_fusion_endpoint",
            return_value="late",
        ), patch(
            "services.search_service.text_corrector_service.correct"
        ) as mock_correct, patch(
            "services.search_service.faiss_service"
        ) as mock_faiss:
            mock_correct.return_value = {
                "corrected_text": "red shoe",
                "engine": "symspell",
                "latency_ms": 1.0,
            }
            mock_faiss.search_late_fusion.return_value = {
                "status": "success",
                "products": [
                    {
                        "product_id": 7,
                        "text_score": 0.71,
                        "image_score": 0.62,
                        "combined_score": 0.66,
                    }
                ],
            }

            # --- Step 3: POST multipart form with raw_text + uploaded image
            with open(image_path, "rb") as f:
                resp = client.post(
                    "/api/search",
                    data={
                        "raw_text": "red shoe",
                        "search_mode": "std",
                        "images": (f, "search.jpg"),
                    },
                    content_type="multipart/form-data",
                )

        # --- Expected Output
        assert resp.status_code == 201
        search_id = resp.get_json().get("search_id")

        with app.app_context():
            retrieves = _db.session.query(Retrieve).filter_by(
                search_id=search_id
            ).all()
            assert len(retrieves) >= 1
            r = retrieves[0]
            assert r.fusion_type == "late_fusion"
            assert r.text_score is not None
            assert r.image_score is not None

    def test_BR_INT_028_search_flow_iwt_dispatch(self, app, client):
        """BR-INT-028: Verify that the POST /api/search flow with search_mode=iwt calls faiss_service.search_image_by_text."""
        # --- Step 1: Patch correction + FAISS service
        with patch(
            "services.search_service.text_corrector_service.correct"
        ) as mock_correct, patch(
            "services.search_service.faiss_service"
        ) as mock_faiss:
            mock_correct.return_value = {
                "corrected_text": "blue jacket",
                "engine": "symspell",
                "latency_ms": 1.0,
            }
            mock_faiss.search_image_by_text.return_value = {
                "status": "success",
                "products": [{"product_id": 5, "score": 0.5}],
            }

            # --- Step 2: POST with search_mode=iwt
            resp = client.post(
                "/api/search",
                data={
                    "raw_text": "blue jacket",
                    "search_mode": "iwt",
                },
                content_type="application/x-www-form-urlencoded",
            )

            # --- Expected Output
            assert resp.status_code == 201
            mock_faiss.search_image_by_text.assert_called_once()
            call_kwargs = mock_faiss.search_image_by_text.call_args.kwargs
            # text= keyword should match the corrected text
            assert call_kwargs.get("text") == "blue jacket"

    def test_BR_INT_029_search_std_missing_text_and_image(self, client):
        """BR-INT-029: Verify that POST /api/search returns HTTP 400 when neither raw_text nor an image is provided in std mode."""
        # --- Step 1: POST empty form with std mode
        resp = client.post(
            "/api/search",
            data={"search_mode": "std"},
            content_type="application/x-www-form-urlencoded",
        )
        # --- Step 2: Assert HTTP 400
        assert resp.status_code == 400
        body = resp.get_json()
        assert "Either 'raw_text' or 'image' must be provided" in (
            body.get("error") or ""
        )

    # -------------------------------------------------------------------
    # /api/search/db-fallback
    # -------------------------------------------------------------------
    def test_BR_INT_030_db_fallback_missing_search_id(self, client):
        """BR-INT-030: Verify that POST /api/search/db-fallback returns 400 when the body lacks search_id."""
        # --- Step 1: POST with a body that lacks the search_id field
        # (a non-empty dict so the route reaches the search_id validation
        # branch instead of the empty-body guard)
        resp = client.post("/api/search/db-fallback", json={"_": "x"})
        # --- Step 2: Assert HTTP 400
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get("error") == "Missing required field: search_id"
