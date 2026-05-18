"""
Locust performance scaffolding for the Backend (Flask orchestrator).

Targets the running Flask backend on its public HTTP host. All cross-service
calls (Correction, Retrieval) are exercised through the real Backend routes,
so this file does NOT mock anything itself — production deployment topology
applies.

Deliverable rows targeted by this file
--------------------------------------
The pytest suite (Backend/tests/integration/test_performance.py) handles
single-request latency assertions; this Locust file is here to cover the
rows that pytest currently SKIPS (concurrency / pool exhaustion / sustained
throughput) and to give a one-knob load generator for sequential baselines.

  PERF-BE-001..009, 011, 012, 013   single-user sequential
                                      run with --users 1 -t 60s
                                      (see "Single-user baseline" below)
  PERF-BE-010                       concurrent pool exhaustion
                                      run with --users 10 -r 10 -t 60s
                                      against a backend started with
                                      SQLALCHEMY_ENGINE_OPTIONS pool_size=2,
                                      max_overflow=0
                                      (see "Pool exhaustion scenario" below)

Any concurrent scenario other than the pool-exhaustion run is OUT OF SCOPE
per the deliverable's Scope Limitation note (CI hardware does not represent
production load).

Run commands
------------
Single-user baseline (PERF-BE-001..009, 011..013):

    cd Backend
    locust -f perf/locustfile.py --headless \\
        -u 1 -r 1 -t 60s \\
        --host http://localhost:5000 \\
        --csv perf/out/be_baseline

Pool exhaustion scenario (PERF-BE-010 only):

    # 1. Start the backend with a tiny pool, e.g.
    #    SQLALCHEMY_ENGINE_OPTIONS='{"pool_size": 2, "max_overflow": 0,
    #                                 "pool_timeout": 5}' python app.py
    # 2. Drive it past saturation:
    cd Backend
    locust -f perf/locustfile.py --headless \\
        -u 10 -r 10 -t 60s \\
        --host http://localhost:5000 \\
        --csv perf/out/be_pool_exhaustion

Notes
-----
- pg_stat_statements query-level analysis is enabled at the PostgreSQL
  database (shared_preload_libraries) and inspected out-of-band — it is NOT
  configured from this file. See the deliverable's PERF-BE-013 row.
- Tasks mirror the rows in performance_testing.md. Weights are tuned so
  /api/search dominates the workload (real production mix) while CRUD and
  the DB-fallback path still get exercised for latency sampling.
- The POST /api/products task uploads a tiny synthetic JPEG byte literal.
  It assumes the test fixture has pre-seeded at least one Brand named
  "perf-brand" (otherwise the route's auto-create-brand path will run, which
  is fine but creates noise in pg_stat_statements). Pre-seed via fixture.
"""

import io
import os
import random

from locust import HttpUser, task, between

# ---------------------------------------------------------------------------
# Optional Prometheus integration (gated by ImportError so locust still works
# even if prometheus_client is absent). The harness sets LOCUST_PROM_PORT
# from the run_all_perf.bat. Defaults to 9301 (Backend slot).
# ---------------------------------------------------------------------------

try:
    from prometheus_client import Counter, Histogram, start_http_server
    _PROM_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dep
    _PROM_AVAILABLE = False

_PROM_PORT = int(os.environ.get("LOCUST_PROM_PORT", "9301"))

if _PROM_AVAILABLE:
    REQ_LATENCY = Histogram(
        "locust_request_duration_seconds",
        "Locust request latency",
        ["endpoint", "method", "status"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    )
    REQ_TOTAL = Counter(
        "locust_request_total",
        "Locust request count",
        ["endpoint", "method", "status"],
    )

    from locust import events as _events

    @_events.init.add_listener
    def _start_prom(environment, **kwargs):  # noqa: D401
        try:
            start_http_server(_PROM_PORT)
        except OSError:
            # Already running on rerun.
            pass

    @_events.request.add_listener
    def _record_request(
        request_type,
        name,
        response_time,
        response_length,
        response,
        context,
        exception,
        start_time,
        url,
        **kwargs,
    ):
        status = "fail" if exception else "ok"
        REQ_LATENCY.labels(
            endpoint=name, method=request_type, status=status
        ).observe(response_time / 1000.0)
        REQ_TOTAL.labels(
            endpoint=name, method=request_type, status=status
        ).inc()


# ---------------------------------------------------------------------------
# Test-data fixtures (in-file; no disk I/O)
# ---------------------------------------------------------------------------

# Representative raw_text values mirroring the SymSpell/ByT5 row coverage.
# Mix of clean queries, single typos, multi-typo, and brand-masked queries.
SAMPLE_QUERIES = [
    "running shoes",
    "runing shoes",          # single typo
    "wireles bluetoth headphones",  # multi typo
    "leather wallet",
    "smart watch black",
    "winter jacet",          # single typo
    "lightweght laptop",     # single typo
    "office chair ergonomic",
    "kahve makinesi",        # turkish — exercises model-agnostic path
    "phone case",
]

# 5 KB synthetic JPEG payload (smallest valid JPEG, padded to ~5 KB).
# This is intentionally NOT a real product image — production runs that need
# fusion-quality images should swap this for a real fixture.
_TINY_JPEG_HEADER = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000"
    "ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432"
    "ffc00011080001000103012200021101031101"
    "ffc4001f0000010501010101010100000000000000000102030405060708090a0b"
    "ffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9fa"
    "ffc4001f0100030101010101010101010000000000000102030405060708090a0b"
    "ffc400b51100020102040403040705040400010277000102031104052131061241510761711322328108144291a1b1c109233352f0156272d10a162434e125f11718191a262728292a35363738393a434445464748494a535455565758595a636465666768696a737475767778797a82838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae2e3e4e5e6e7e8e9eaf2f3f4f5f6f7f8f9fa"
    "ffda000c03010002110311003f00fb0028a28a00ffd9"
)
TINY_JPEG_BYTES = _TINY_JPEG_HEADER + (b"\x00" * (5 * 1024 - len(_TINY_JPEG_HEADER)))


class BackendUser(HttpUser):
    """
    Simulated client of the Backend Flask orchestrator.

    Weights reflect production traffic mix as documented in
    performance_testing.md:
      search:          5  (PERF-BE-001..006)
      list products:   2  (PERF-BE-007)
      create product:  1  (PERF-BE-008)
      db-fallback:     1  (PERF-BE-009 / PERF-BE-011)
    """

    # Small think-time so we don't pathologically hammer a single endpoint.
    # For the pool-exhaustion run, drop this to between(0, 0) on the CLI via
    # an env var if you want maximum pressure.
    wait_time = between(0.1, 0.5)

    # Cache one search_id so the db-fallback task has something to work with.
    _last_search_id = None

    @task(5)
    def search(self):
        """POST /api/search — multipart form (raw_text + correction toggle)."""
        raw_text = random.choice(SAMPLE_QUERIES)
        # Vary correction_enabled so we exercise both paths.
        correction_enabled = "true" if random.random() < 0.8 else "false"
        engine = random.choice(["symspell", "byt5"])

        with self.client.post(
            "/api/search",
            data={
                "raw_text": raw_text,
                "search_mode": "std",
                "engine": engine,
                "correction_enabled": correction_enabled,
            },
            name="POST /api/search",
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                try:
                    payload = resp.json()
                    sid = payload.get("search_id")
                    if sid is not None:
                        type(self)._last_search_id = sid
                    resp.success()
                except Exception:
                    resp.failure("invalid JSON in 201 response")
            elif resp.status_code in (400, 404):
                # Validation / not-found are legitimate route responses for
                # some payloads; do not fail the load test for them.
                resp.success()
            else:
                resp.failure(f"unexpected status {resp.status_code}")

    @task(2)
    def list_products(self):
        """GET /api/products — listing endpoint (PERF-BE-007)."""
        self.client.get("/api/products", name="GET /api/products")

    @task(1)
    def create_product(self):
        """
        POST /api/products — multipart create (PERF-BE-008).

        Uses a 5 KB synthetic JPEG payload. The route auto-creates the brand
        if missing; for clean pg_stat_statements rows pre-seed a "perf-brand"
        Brand row in the test fixture before running this scenario.
        """
        suffix = random.randint(1, 1_000_000)
        files = {
            "images": (
                f"perf_{suffix}.jpg",
                io.BytesIO(TINY_JPEG_BYTES),
                "image/jpeg",
            ),
        }
        data = {
            "name": f"perf-product-{suffix}",
            "price": "9.99",
            "brand": "perf-brand",
            "description": "synthetic locust load fixture",
        }
        with self.client.post(
            "/api/products",
            data=data,
            files=files,
            name="POST /api/products",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201):
                resp.success()
            elif resp.status_code in (400, 409):
                # Validation errors are acceptable under perf load.
                resp.success()
            else:
                resp.failure(f"unexpected status {resp.status_code}")

    @task(1)
    def db_fallback(self):
        """
        POST /api/search/db-fallback — fallback path (PERF-BE-009, 011).

        Requires a prior search_id; falls through silently if none is cached
        yet (cold start of the locust process).
        """
        sid = type(self)._last_search_id
        if sid is None:
            return
        self.client.post(
            "/api/search/db-fallback",
            json={"search_id": sid},
            name="POST /api/search/db-fallback",
        )
