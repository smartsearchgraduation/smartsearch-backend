# Backend — Locust performance scaffolding

This directory contains the Locust load-generator script for the Backend
Flask orchestrator. It is supplemental to the pytest suite at
`Backend/tests/integration/test_performance.py`; pytest covers single-call
latency assertions, this Locust file covers the rows pytest currently
skips (concurrency / pool exhaustion / sustained throughput).

## Deliverable rows covered

| Row(s)                              | Scenario                  | Locust args               |
|-------------------------------------|---------------------------|---------------------------|
| PERF-BE-001..009, 011, 012, 013     | sequential single-user    | `-u 1 -r 1 -t 60s`        |
| PERF-BE-010                         | DB pool exhaustion        | `-u 10 -r 10 -t 60s`      |

Any other concurrent run is OUT OF SCOPE per the deliverable's Scope
Limitation note (CI hardware is not representative of production load).

## Run commands

Single-user baseline:

```
cd Backend
locust -f perf/locustfile.py --headless \
    -u 1 -r 1 -t 60s \
    --host http://localhost:5000 \
    --csv perf/out/be_baseline
```

Pool exhaustion (start the backend with `pool_size=2, max_overflow=0` first,
e.g. via `SQLALCHEMY_ENGINE_OPTIONS`):

```
cd Backend
locust -f perf/locustfile.py --headless \
    -u 10 -r 10 -t 60s \
    --host http://localhost:5000 \
    --csv perf/out/be_pool_exhaustion
```

## Prerequisites

- Backend Flask app running on `http://localhost:5000` (or pass `--host`).
- PostgreSQL reachable with the schema migrated and at least one Brand row
  named `perf-brand` pre-seeded (the `POST /api/products` task references
  it). Other Brand names trigger the route's auto-create-brand path, which
  is functional but adds noise to `pg_stat_statements`.
- Correction and Retrieval reachable from the Backend (the `/api/search`
  task drives the full chain end-to-end). Run those services with their
  normal configuration; this file does not mock them.
- For PERF-BE-010 specifically: start the backend with a tiny pool and a
  short `pool_timeout` so saturation surfaces quickly.

## Output

`--csv perf/out/<run-name>` writes:

- `<run-name>_stats.csv`              aggregate per-task stats
- `<run-name>_stats_history.csv`      per-second timeseries
- `<run-name>_failures.csv`           non-2xx responses
- `<run-name>_exceptions.csv`         locust-side exceptions

Feed `<run-name>_stats_history.csv` into the deliverable's analysis tool to
compute p50/p95 per row.
