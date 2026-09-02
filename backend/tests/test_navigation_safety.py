"""Navigation-safety tests: batch endpoints are explicit-POST only.

The sidebar must never trigger discovery/calculation. Backend guarantees:
  - batch endpoints are POST (a GET from page navigation cannot run them —
    FastAPI answers 405 for GET)
  - a second batch call serves cached per-KPI results (no recalculation)
  - re-running with a fresh dataset is possible (Refresh semantics)
"""

import io

from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

CSV_1 = (
    "date,region,revenue,order_id\n"
    + "".join(
        f"2026-04-{d:02d},{r},{100 + d}.0,O{d}{r}\n"
        for d in range(1, 29)
        for r in ("A", "B")
    )
)
CSV_2 = "date,bonus\n" + "".join(f"2026-04-{d:02d},{d}.0\n" for d in range(1, 29))


def _upload(client, name, content) -> str:
    resp = client.post(
        "/ingestion/upload",
        files={"file": (name, io.BytesIO(content.encode()), "text/csv")},
        data={"grain": "Daily", "cadence": "Nightly batch"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["source_id"]


def _seeded_dataset(client) -> str:
    s1 = _upload(client, "sales.csv", CSV_1)
    s2 = _upload(client, "bonus.csv", CSV_2)
    for sid in (s1, s2):
        assert client.get(f"/profiling/{sid}").status_code == 200
        assert client.get(f"/semantic-contract/{sid}").status_code == 200
    build = client.post(
        "/canonical/build",
        json={"source_ids": [s1, s2], "join_keys": {"date": {"0": "date", "1": "date"}}},
    )
    assert build.status_code == 200, build.text
    ds = build.json()["dataset_id"]
    assert client.post(f"/kpi/discover/{ds}").status_code == 200
    return ds


def test_batch_endpoints_reject_get(isolated_env):
    """GET (what navigation could issue) must 405 — only explicit POST runs."""
    init_db()
    with TestClient(app) as client:
        for path in (
            "/kpi/compute-all/x",
            "/anomaly/run-all/x",
            "/drivers/run-all/x",
        ):
            resp = client.get(path)
            assert resp.status_code == 405, f"GET {path} unexpectedly allowed"


def test_batch_second_call_serves_cache_not_recalculation(isolated_env):
    """The frontend cache shows stored results; the backend must agree:
    a repeated batch call is fully cached (server-side per-KPI caches)."""
    init_db()
    with TestClient(app) as client:
        ds = _seeded_dataset(client)

        first = client.post(f"/kpi/compute-all/{ds}").json()
        assert first["computed"] > 0
        assert not all(r["cached"] for r in first["results"])

        second = client.post(f"/kpi/compute-all/{ds}").json()
        assert all(r["cached"] for r in second["results"]), (
            "second call must reuse stored computations, not recalculate"
        )
        assert second["computed"] == first["computed"]

        anomalies_first = client.post(f"/anomaly/run-all/{ds}").json()
        anomalies_second = client.post(f"/anomaly/run-all/{ds}").json()
        assert all(r["cached"] for r in anomalies_second["results"])
        assert anomalies_second["processed"] == anomalies_first["processed"]


def test_refresh_reruns_discovery_and_recomputation(isolated_env):
    """Refresh semantics: re-discovery + re-compute produces fresh results
    (the explicit button path), distinct from the cached render path."""
    init_db()
    with TestClient(app) as client:
        ds = _seeded_dataset(client)
        first = client.post(f"/kpi/compute-all/{ds}").json()

        # Refresh = explicit re-discovery, then re-compute-all.
        assert client.post(f"/kpi/discover/{ds}").status_code == 200
        refreshed = client.post(f"/kpi/compute-all/{ds}").json()
        assert refreshed["computed"] == first["computed"]
        assert refreshed["failed"] == 0
        # Same dataset + same deterministic engine -> identical values.
        for a, b in zip(first["results"], refreshed["results"]):
            assert a["kpi_id"] == b["kpi_id"]
            if a["computation"]:
                assert a["computation"]["value"] == b["computation"]["value"]
