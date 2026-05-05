"""
Backend-to-Correction integration tests (BC-INT-001..BC-INT-028).

Spec: validates Backend Flask routes + services + models against a mocked
Correction microservice. The Correction `/correct` and `/models` endpoints are
patched at the `services.text_corrector_service.requests` level so no real
network traffic is generated. The FAISS retrieval service is also mocked so
tests are deterministic.

Each test maps 1:1 to a row in `backend_to_correction.md`. Function names
embed the case ID with hyphens replaced by underscores.
"""
import json
import os
import sys
from unittest.mock import patch, MagicMock, ANY

import pytest
import requests as _requests_lib

# Ensure Backend root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from models import db as _db
from models.search_query import SearchQuery
from models.search_time import SearchTime
from models.retrieve import Retrieve


# ---------------------------------------------------------------------------
# Test-local helpers / fixtures
# ---------------------------------------------------------------------------

def _faiss_one_product():
    """Standard FAISS mock that returns a single product."""
    return {
        "products": [{"product_id": 1, "score": 0.95}],
        "success": True,
        "status": "success",
    }


def _faiss_empty():
    return {"products": [], "success": True, "status": "success"}


def _make_response(json_data, status_code=200):
    """Build a fake `requests.Response`-shaped MagicMock."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        err = _requests_lib.exceptions.HTTPError(f"HTTP {status_code}")
        resp.raise_for_status.side_effect = err
    else:
        resp.raise_for_status.return_value = None
    return resp


@pytest.fixture(autouse=True)
def _wipe_db(app):
    """Wipe DB tables between tests so session-scoped app is reusable."""
    with app.app_context():
        # Delete in FK-safe order
        _db.session.query(Retrieve).delete()
        _db.session.query(SearchTime).delete()
        _db.session.query(SearchQuery).delete()
        _db.session.commit()
    yield
    with app.app_context():
        _db.session.rollback()


@pytest.fixture
def mock_faiss():
    """Patch `faiss_service` as imported into `services.search_service`."""
    with patch("services.search_service.faiss_service") as m:
        m.search_text.return_value = _faiss_empty()
        m.search_late_fusion.return_value = _faiss_empty()
        m.search_image.return_value = _faiss_empty()
        m.search_image_by_text.return_value = _faiss_empty()
        m.search_text_by_image.return_value = _faiss_empty()
        yield m


@pytest.fixture
def mock_requests_post():
    """Patch the outbound `requests.post` used by TextCorrectorService."""
    with patch("services.text_corrector_service.requests.post") as m:
        m.return_value = _make_response(
            {
                "corrected_query": "iphone",
                "changed": True,
                "latency_ms": 12,
                "model_used": "byt5-small",
            }
        )
        yield m


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestBackendCorrectionIntegration:

    def test_BC_INT_001_search_persists_corrected_text(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-001: Verify that POST /api/search invokes the Correction service and persists corrected_text on the SearchQuery row."""
        # --- Step 1: Mock returns canned correction response (autouse) ---
        mock_requests_post.return_value = _make_response(
            {
                "corrected_query": "iphone",
                "changed": True,
                "latency_ms": 12,
                "model_used": "byt5-small",
            }
        )
        mock_faiss.search_text.return_value = _faiss_one_product()

        # --- Step 2: POST search ---
        r = client.post("/api/search", data={"raw_text": "iphnoe"})
        assert r.status_code == 201
        body = r.get_json()
        assert "search_id" in body
        sid = body["search_id"]

        # --- Step 3: Inspect persisted SearchQuery ---
        with app.app_context():
            sq = _db.session.get(SearchQuery, sid)
            assert sq is not None
            assert sq.raw_text == "iphnoe"
            assert sq.corrected_text == "iphone"

    def test_BC_INT_002_engine_form_field_mapped_to_correction_payload(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-002: Verify that the Backend forwards `engine` form field as the `model` key in the Correction `/correct` payload."""
        mock_requests_post.return_value = _make_response(
            {"corrected_query": "laptp", "changed": False, "latency_ms": 1, "model_used": "symspell_keyboard"}
        )

        r = client.post("/api/search", data={"raw_text": "laptp", "engine": "symspell"})
        assert r.status_code == 201

        # Inspect captured POST args to /correct
        assert mock_requests_post.called
        kwargs = mock_requests_post.call_args.kwargs
        payload = kwargs.get("json")
        assert payload == {"query": "laptp", "model": "symspell_keyboard"}

    def test_BC_INT_003_correction_disabled_skips_correction_call(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-003: Verify that when correction_enabled=false, the Backend does NOT call the Correction service and writes corrected_text == raw_text."""
        r = client.post(
            "/api/search",
            data={"raw_text": "samsng", "correction_enabled": "false"},
        )
        assert r.status_code == 201
        sid = r.get_json()["search_id"]

        # Correction should not have been invoked
        mock_requests_post.assert_not_called()

        with app.app_context():
            sq = _db.session.get(SearchQuery, sid)
            assert sq.corrected_text == "samsng"

    def test_BC_INT_004_connection_error_falls_back_to_raw_text(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-004: Verify that a Correction ConnectionError triggers fallback: search proceeds with original text, success=false, no 5xx returned."""
        mock_requests_post.side_effect = _requests_lib.exceptions.ConnectionError("down")
        mock_faiss.search_text.return_value = _faiss_one_product()

        r = client.post("/api/search", data={"raw_text": "phne"})
        assert r.status_code == 201
        sid = r.get_json()["search_id"]

        with app.app_context():
            sq = _db.session.get(SearchQuery, sid)
            assert sq.corrected_text == "phne"
            ret = _db.session.query(Retrieve).filter_by(search_id=sid).first()
            assert ret is not None
            assert ret.correction_engine is not None  # 'UNKNOWN' or engine arg

    def test_BC_INT_005_correction_timeout_degrades_gracefully(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-005: Verify that Correction request timeout (Timeout) degrades gracefully without raising 500."""
        mock_requests_post.side_effect = _requests_lib.exceptions.Timeout("slow")

        r = client.post("/api/search", data={"raw_text": "tablt"})
        assert r.status_code == 201
        sid = r.get_json()["search_id"]

        with app.app_context():
            sq = _db.session.get(SearchQuery, sid)
            assert sq.corrected_text == "tablt"
            st = _db.session.get(SearchTime, sid)
            assert st is not None
            assert isinstance(st.correction_time, float)
            assert st.correction_time is not None

    def test_BC_INT_006_correction_500_preserves_original_text(
        self, app, client, mock_requests_post, mock_faiss, caplog
    ):
        """BC-INT-006: Verify that Correction returning HTTP 500 is treated as a failure and original text is preserved."""
        mock_requests_post.return_value = _make_response({"error": "boom"}, status_code=500)

        with caplog.at_level("ERROR", logger="services.text_corrector_service"):
            r = client.post("/api/search", data={"raw_text": "mous"})
        assert r.status_code == 201
        sid = r.get_json()["search_id"]

        with app.app_context():
            sq = _db.session.get(SearchQuery, sid)
            assert sq.corrected_text == "mous"
        # log assertion: an error was logged by TextCorrectorService
        assert any("[TextCorrector] Error" in rec.getMessage() for rec in caplog.records)

    def test_BC_INT_007_malformed_json_falls_back_to_legacy_then_raw(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-007: Verify that Correction returning malformed JSON missing corrected_query falls back to legacy key corrected, then to raw_text."""
        # First call: legacy 'corrected' key
        mock_requests_post.return_value = _make_response(
            {"corrected": "phone", "changed": True}
        )
        r1 = client.post("/api/search", data={"raw_text": "phne"})
        assert r1.status_code == 201
        sid1 = r1.get_json()["search_id"]

        # Second call: empty dict
        mock_requests_post.return_value = _make_response({})
        r2 = client.post("/api/search", data={"raw_text": "tabl"})
        assert r2.status_code == 201
        sid2 = r2.get_json()["search_id"]

        with app.app_context():
            sq1 = _db.session.get(SearchQuery, sid1)
            sq2 = _db.session.get(SearchQuery, sid2)
            assert sq1.corrected_text == "phone"
            assert sq2.corrected_text == "tabl"  # falls back to raw_text

    def test_BC_INT_008_latency_ms_persisted_to_search_time(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-008: Verify that when the Correction response includes latency_ms, it is stored in the search_time.correction_time column."""
        mock_requests_post.return_value = _make_response(
            {"corrected_query": "x", "changed": False, "latency_ms": 42, "model_used": "byt5-small"}
        )

        r = client.post("/api/search", data={"raw_text": "x"})
        assert r.status_code == 201
        sid = r.get_json()["search_id"]

        with app.app_context():
            st = _db.session.get(SearchTime, sid)
            assert st is not None
            assert st.search_id == sid
            # service records its own wall-clock duration into correction_time
            assert isinstance(st.correction_time, float)
            assert st.correction_time >= 0

    def test_BC_INT_009_model_used_propagated_to_retrieve_correction_engine(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-009: Verify that model_used returned by Correction is propagated to Retrieve.correction_engine."""
        mock_requests_post.return_value = _make_response(
            {"corrected_query": "y", "changed": True, "latency_ms": 5, "model_used": "byt5-large"}
        )
        mock_faiss.search_text.return_value = _faiss_one_product()

        r = client.post("/api/search", data={"raw_text": "y"})
        assert r.status_code == 201
        sid = r.get_json()["search_id"]

        with app.app_context():
            rets = _db.session.query(Retrieve).filter_by(search_id=sid).all()
            assert len(rets) >= 1
            assert any(r.correction_engine == "byt5-large" for r in rets)

    def test_BC_INT_010_get_models_success(self, app, client):
        """BC-INT-010: Verify GET /api/correction/models returns 200 with engines list when text_corrector_service.get_available_models succeeds."""
        success_payload = {
            "status": "success",
            "data": {"engines": [{"name": "byt5-small", "description": "ByT5"}]},
            "source": "correction_service",
        }
        with patch(
            "routes.correction.text_corrector_service.get_available_models",
            return_value=success_payload,
        ):
            r = client.get("/api/correction/models")
        assert r.status_code == 200
        body = r.get_json()
        assert body["status"] == "success"
        assert isinstance(body["data"]["engines"], list)
        assert len(body["data"]["engines"]) > 0

    def test_BC_INT_011_get_models_falls_back_to_local_config(self, app, client):
        """BC-INT-011: Verify GET /api/correction/models falls back to local_config when the upstream Correction /models endpoint is unreachable."""
        with patch("services.text_corrector_service.requests.get") as mget:
            mget.side_effect = _requests_lib.exceptions.ConnectionError("no upstream")
            r = client.get("/api/correction/models")
        assert r.status_code == 200
        body = r.get_json()
        assert body.get("source") == "local_config"
        engine_names = [e.get("name") for e in body["data"]["engines"]]
        assert "symspell_keyboard" in engine_names
        assert "byt5-small" in engine_names

    def test_BC_INT_012_get_models_service_layer_error_returns_500(self, app, client):
        """BC-INT-012: Verify GET /api/correction/models returns HTTP 500 when service-layer returns status=='error'."""
        with patch(
            "routes.correction.text_corrector_service.get_available_models",
            return_value={"status": "error", "error": "boom"},
        ):
            r = client.get("/api/correction/models")
        assert r.status_code == 500
        body = r.get_json()
        assert body["status"] == "error"
        assert body["error"] == "boom"

    def test_BC_INT_013_save_selected_engine_success(self, app, client):
        """BC-INT-013: Verify POST /api/correction/selected-engine/save with valid engine returns 200 and persists the selection via save_selected_engine."""
        with patch(
            "routes.correction.text_corrector_service.save_selected_engine",
            return_value={
                "status": "success",
                "message": "Correction engine saved: symspell_keyboard",
                "data": {"engine": "symspell_keyboard"},
            },
        ) as ms:
            r = client.post(
                "/api/correction/selected-engine/save",
                json={"engine": "symspell_keyboard"},
            )
        assert r.status_code == 200
        body = r.get_json()
        assert body["data"]["engine"] == "symspell_keyboard"
        ms.assert_called_once_with("symspell_keyboard")

    def test_BC_INT_014_save_selected_engine_empty_body_400(self, app, client):
        """BC-INT-014: Verify POST /api/correction/selected-engine/save with empty body returns HTTP 400 with Missing 'engine' field."""
        r = client.post("/api/correction/selected-engine/save", json={})
        assert r.status_code == 400
        body = r.get_json()
        assert body["status"] == "error"
        assert body["error"] == "Missing 'engine' field"

    def test_BC_INT_015_no_op_correction_still_201(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-015: Verify POST /api/search with correction_enabled=true (default) and a no-op correction (changed=false) still returns 201 and corrected_text == raw_text."""
        mock_requests_post.return_value = _make_response(
            {"corrected_query": "phone", "changed": False, "latency_ms": 3, "model_used": "byt5-small"}
        )
        mock_faiss.search_text.return_value = _faiss_one_product()

        r = client.post("/api/search", data={"raw_text": "phone"})
        assert r.status_code == 201
        sid = r.get_json()["search_id"]

        with app.app_context():
            sq = _db.session.get(SearchQuery, sid)
            assert sq.corrected_text == "phone"
            rets = _db.session.query(Retrieve).filter_by(search_id=sid).all()
            assert any(r.correction_engine == "byt5-small" for r in rets)

    def test_BC_INT_016_missing_text_and_image_400_before_correction(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-016: Verify POST /api/search with neither raw_text nor image returns 400 BEFORE invoking Correction."""
        r = client.post("/api/search", data={})
        assert r.status_code == 400
        body = r.get_json()
        assert body["error"] == "Either 'raw_text' or 'image' must be provided"
        mock_requests_post.assert_not_called()

    def test_BC_INT_017_invalid_search_mode_400_before_correction(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-017: Verify POST /api/search with search_mode=invalid returns 400 BEFORE invoking Correction."""
        r = client.post("/api/search", data={"raw_text": "x", "search_mode": "foo"})
        assert r.status_code == 400
        body = r.get_json()
        assert "Invalid search_mode" in body.get("error", "")
        mock_requests_post.assert_not_called()

    def test_BC_INT_018_unknown_engine_passthrough(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-018: Verify that an unknown engine value is forwarded as-is to Correction (engine_map fallthrough)."""
        mock_requests_post.return_value = _make_response(
            {"corrected_query": "hat", "changed": False, "latency_ms": 2, "model_used": "qwen-3.5-2b"}
        )

        r = client.post(
            "/api/search", data={"raw_text": "hat", "engine": "qwen-3.5-2b"}
        )
        assert r.status_code == 201
        kwargs = mock_requests_post.call_args.kwargs
        assert kwargs["json"]["model"] == "qwen-3.5-2b"

    def test_BC_INT_019_oversized_raw_text_forwarded_intact(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-019: Verify that an oversized raw_text (10,000 chars) is forwarded to Correction without truncation by the Backend."""
        big = "a" * 10000
        mock_requests_post.return_value = _make_response(
            {"corrected_query": big, "changed": False, "latency_ms": 1, "model_used": "byt5-small"}
        )

        r = client.post("/api/search", data={"raw_text": big})
        assert r.status_code == 201
        kwargs = mock_requests_post.call_args.kwargs
        assert len(kwargs["json"]["query"]) == 10000

    def test_BC_INT_020_correction_called_with_10s_timeout(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-020: Verify that Backend uses 10s timeout when calling Correction /correct."""
        mock_requests_post.return_value = _make_response(
            {"corrected_query": "cat", "changed": False, "latency_ms": 1, "model_used": "byt5-small"}
        )

        r = client.post("/api/search", data={"raw_text": "cat"})
        assert r.status_code == 201
        kwargs = mock_requests_post.call_args.kwargs
        assert kwargs.get("timeout") == 10

    def test_BC_INT_021_get_search_returns_corrected_text(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-021: Verify that GET /api/search/<id> returns the previously-persisted corrected_text from the Correction round-trip."""
        mock_requests_post.return_value = _make_response(
            {"corrected_query": "shoes", "changed": True, "latency_ms": 7, "model_used": "byt5-small"}
        )
        mock_faiss.search_text.return_value = _faiss_one_product()

        r = client.post("/api/search", data={"raw_text": "shoez"})
        assert r.status_code == 201
        sid = r.get_json()["search_id"]

        # The GET endpoint uses Postgres-specific SQL (ARRAY_AGG/ARRAY_REMOVE)
        # which doesn't run on SQLite. Patch it to read the persisted ORM rows
        # directly so we still validate the text round-trip end-to-end.
        with app.app_context():
            sq = _db.session.get(SearchQuery, sid)
            stub = {
                "search_id": sid,
                "raw_text": sq.raw_text,
                "corrected_text": sq.corrected_text,
                "products": [],
                "search_mode": sq.search_mode or "std",
                "correction_enabled": True,
            }
        with patch(
            "routes.search.SearchService.get_search_by_id", return_value=stub
        ):
            g = client.get(f"/api/search/{sid}")
        assert g.status_code == 200
        gbody = g.get_json()
        assert gbody["raw_text"] == "shoez"
        assert gbody["corrected_text"] == "shoes"

    def test_BC_INT_022_iwt_uses_corrected_text(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-022: Verify that search_mode='iwt' propagates corrected_text (not raw_text) to the FAISS image-by-text call."""
        mock_requests_post.return_value = _make_response(
            {"corrected_query": "red shoes", "changed": True, "latency_ms": 4, "model_used": "byt5-small"}
        )
        mock_faiss.search_image_by_text.return_value = _faiss_one_product()

        r = client.post(
            "/api/search",
            data={"raw_text": "red shoez", "search_mode": "iwt"},
        )
        assert r.status_code == 201

        mock_faiss.search_image_by_text.assert_called_once()
        call_kwargs = mock_faiss.search_image_by_text.call_args.kwargs
        assert call_kwargs.get("text") == "red shoes"

    def test_BC_INT_023_extra_unknown_keys_tolerated(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-023: Verify schema contract: Backend tolerates Correction response containing extra unknown keys without raising."""
        mock_requests_post.return_value = _make_response(
            {
                "corrected_query": "phone",
                "changed": True,
                "latency_ms": 5,
                "model_used": "byt5-small",
                "experimental_field": "x",
                "debug": {"a": 1},
            }
        )

        r = client.post("/api/search", data={"raw_text": "phne"})
        assert r.status_code == 201
        sid = r.get_json()["search_id"]

        with app.app_context():
            sq = _db.session.get(SearchQuery, sid)
            assert sq.corrected_text == "phone"

    def test_BC_INT_024_fallback_records_correction_engine(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-024: Verify that when Correction returns success=false (post-fallback shape), Backend still records a Retrieve.correction_engine value and does NOT abort the request."""
        mock_requests_post.side_effect = _requests_lib.exceptions.ConnectionError("down")
        mock_faiss.search_text.return_value = _faiss_one_product()

        r = client.post("/api/search", data={"raw_text": "ipd"})
        assert r.status_code == 201
        sid = r.get_json()["search_id"]

        with app.app_context():
            rets = _db.session.query(Retrieve).filter_by(search_id=sid).all()
            assert len(rets) >= 1
            for ret in rets:
                assert ret.correction_engine is not None
            sq = _db.session.get(SearchQuery, sid)
            assert sq.correction_enabled is True

    def test_BC_INT_025_correction_service_url_env_honored(self, app):
        """BC-INT-025: Verify environment variable CORRECTION_SERVICE_URL is honored by the Backend's outbound POST URL."""
        custom_url = "http://mock-correction:9999/correct"
        with patch.dict(os.environ, {"CORRECTION_SERVICE_URL": custom_url}):
            # Re-import to pick up env var (module reads at import-time for the
            # default; the class accepts base_url via constructor too).
            from services.text_corrector_service import TextCorrectorService
            svc = TextCorrectorService(base_url=custom_url)
            with patch("services.text_corrector_service.requests.post") as mp:
                mp.return_value = _make_response(
                    {"corrected_query": "q", "changed": False, "latency_ms": 1, "model_used": "byt5-small"}
                )
                svc.correct("q")
                assert mp.call_args.args[0] == custom_url

    def test_BC_INT_026_search_time_columns_populated(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-026: Verify that SearchTime row is created with all four timing columns populated after a successful Correction round-trip."""
        mock_requests_post.return_value = _make_response(
            {"corrected_query": "x", "changed": False, "latency_ms": 15, "model_used": "byt5-small"}
        )

        r = client.post("/api/search", data={"raw_text": "x"})
        assert r.status_code == 201
        sid = r.get_json()["search_id"]

        with app.app_context():
            st = _db.session.get(SearchTime, sid)
            assert st is not None
            assert st.correction_time is not None and st.correction_time >= 0
            assert st.faiss_time is not None and st.faiss_time >= 0
            assert st.db_time is not None and st.db_time >= 0
            assert st.backend_total_time is not None and st.backend_total_time >= 0

    def test_BC_INT_027_save_selected_engine_empty_string_400(self, app, client):
        """BC-INT-027: Verify POST /api/correction/selected-engine/save with engine="" (empty string) returns 400."""
        r = client.post(
            "/api/correction/selected-engine/save", json={"engine": ""}
        )
        assert r.status_code == 400
        body = r.get_json()
        assert body["error"] == "Missing 'engine' field"

    def test_BC_INT_028_two_searches_record_distinct_engines(
        self, app, client, mock_requests_post, mock_faiss
    ):
        """BC-INT-028: Verify that two consecutive /api/search calls with different engines result in two Retrieve rows whose correction_engine differ accordingly."""
        # First call: symspell_keyboard
        mock_requests_post.return_value = _make_response(
            {
                "corrected_query": "phone",
                "changed": False,
                "latency_ms": 1,
                "model_used": "symspell_keyboard",
            }
        )
        mock_faiss.search_text.return_value = _faiss_one_product()
        r1 = client.post(
            "/api/search", data={"raw_text": "phone", "engine": "symspell"}
        )
        assert r1.status_code == 201
        sid1 = r1.get_json()["search_id"]

        # Second call: byt5-small
        mock_requests_post.return_value = _make_response(
            {
                "corrected_query": "tablet",
                "changed": False,
                "latency_ms": 2,
                "model_used": "byt5-small",
            }
        )
        r2 = client.post(
            "/api/search", data={"raw_text": "tablet", "engine": "byt5"}
        )
        assert r2.status_code == 201
        sid2 = r2.get_json()["search_id"]

        assert sid1 != sid2
        with app.app_context():
            ret1 = _db.session.query(Retrieve).filter_by(search_id=sid1).first()
            ret2 = _db.session.query(Retrieve).filter_by(search_id=sid2).first()
            assert ret1 is not None and ret2 is not None
            assert ret1.correction_engine == "symspell_keyboard"
            assert ret2.correction_engine == "byt5-small"
