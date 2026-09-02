"""Single-source end-to-end test (Phase 19): the full pipeline on one source.

Upload one synthetic source -> single-source canonical build (no merge) ->
KPI discovery -> compute -> anomaly detection -> driver decomposition ->
insight -> recommendation package. Every stage must return a valid,
non-empty result — proving single-source data flows the whole way.
"""

import io

from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

CSV = (
    "date,region,revenue,order_id\n"
    + "".join(
        f"2026-01-{d:02d},{r},{100 + d * 3}.0,O{d}{r}\n"
        for d in range(1, 29)
        for r in ("A", "B")
    )
)


def test_single_source_full_pipeline(isolated_env):
    init_db()
    with TestClient(app) as client:
        # 1. Upload ONE source only — no second file anywhere in this test.
        up = client.post(
            "/ingestion/upload",
            files={"file": ("monthly_sales.csv", io.BytesIO(CSV.encode()), "text/csv")},
            data={"grain": "Daily", "cadence": "Nightly batch"},
        )
        assert up.status_code == 200, up.text
        sid = up.json()["source_id"]

        # Prerequisites (own pages' steps).
        assert client.get(f"/profiling/{sid}").status_code == 200
        assert client.get(f"/semantic-contract/{sid}").status_code == 200

        # 2. Single-source canonical build — no join_keys at all.
        build = client.post(
            "/canonical/build",
            json={"source_ids": [sid], "target_cadence": "daily"},
        )
        assert build.status_code == 200, build.text
        ds = build.json()["dataset_id"]
        assert build.json()["row_count"] == 56  # 28 days x 2 regions, unmodified

        # 3. KPI discovery works on the single-source dataset.
        disc = client.post(f"/kpi/discover/{ds}")
        assert disc.status_code == 200, disc.text
        kpis = disc.json()["kpis"]
        assert kpis, "expected KPI candidates from a single source"
        valid = [k for k in kpis if k["status"] == "valid"]
        assert valid, "expected at least one valid KPI"
        kpi_id = valid[0]["kpi_id"]

        # 4. Computation.
        comp = client.get(f"/kpi/{kpi_id}/compute")
        assert comp.status_code == 200, comp.text
        computation = comp.json()["computation"]
        assert computation["value"] is not None
        assert len(computation["trend"]) > 0

        # 5. Anomaly detection.
        anom = client.get(f"/anomaly/{kpi_id}")
        assert anom.status_code == 200, anom.text
        assert "change_points" in anom.json()["anomalies"]

        # 6. Driver decomposition.
        drv = client.get(f"/drivers/{kpi_id}")
        assert drv.status_code == 200, drv.text
        assert drv.json()["findings"], "expected driver findings"

        # 7. Insight (bulleted, Phase 18 shape).
        insight = client.get(f"/insights/{kpi_id}")
        assert insight.status_code == 200, insight.text
        bullets = insight.json()["bullets"]
        assert isinstance(bullets, list) and bullets

        # 8. Recommendation package (deterministic, no LLM).
        package = client.get(f"/recommendations/{kpi_id}/package")
        assert package.status_code == 200, package.text
        assert package.json()["package"]["candidate_action"]
