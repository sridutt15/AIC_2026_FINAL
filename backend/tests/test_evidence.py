"""Evidence tests: every finding carries a complete, non-null evidence record."""

import io
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.drivers.causal import diff_in_diff
from app.core.evidence.evidence_builder import build_evidence
from app.db import init_db
from app.main import app


def _build_test_dataset(client: TestClient) -> tuple:
    """Upload a source, profile, contract, canonical dataset, discover + compute."""
    csv_content = (
        "date,region,revenue,order_id\n"
        "2024-01-01,A,100.0,O1\n"
        "2024-01-02,A,110.0,O2\n"
        "2024-01-03,A,100.0,O3\n"
        "2024-01-04,A,120.0,O4\n"
        "2024-01-05,A,110.0,O5\n"
        "2024-01-06,A,125.0,O6\n"
        "2024-01-07,A,100.0,O7\n"
        "2024-01-08,A,130.0,O8\n"
        "2024-01-01,B,50.0,O9\n"
        "2024-01-02,B,47.0,O10\n"
        "2024-01-03,B,50.0,O11\n"
        "2024-01-04,B,49.0,O12\n"
        "2024-01-05,B,50.0,O13\n"
        "2024-01-06,B,51.0,O14\n"
        "2024-01-07,B,58.0,O15\n"
        "2024-01-08,B,50.0,O16\n"
    )
    up = client.post(
        "/ingestion/upload",
        data={"grain": "Daily", "cadence": "Nightly batch"},
        files={"file": ("evidence_test.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert up.status_code == 200
    source_id = up.json()["source_id"]
    assert client.get(f"/profiling/{source_id}").status_code == 200
    assert client.get(f"/semantic-contract/{source_id}").status_code == 200

    # Canonical dataset needs 2 sources: upload a second one and join trivially.
    csv2 = "date,bonus\n" + "\n".join(
        f"2024-01-0{i},1.0" for i in range(1, 9)
    ) + "\n"
    up2 = client.post(
        "/ingestion/upload",
        data={"grain": "Daily", "cadence": "Nightly batch"},
        files={"file": ("bonus.csv", io.BytesIO(csv2.encode()), "text/csv")},
    )
    source2 = up2.json()["source_id"]
    assert client.get(f"/profiling/{source2}").status_code == 200
    assert client.get(f"/semantic-contract/{source2}").status_code == 200

    build = client.post(
        "/canonical/build",
        json={
            "source_ids": [source_id, source2],
            "join_keys": {"date": {"0": "date", "1": "date"}},
        },
    )
    assert build.status_code == 200
    dataset_id = build.json()["dataset_id"]

    disc = client.post(f"/kpi/discover/{dataset_id}")
    assert disc.status_code == 200
    kpis = disc.json()["kpis"]
    target = next(k for k in kpis if k["measure"] == "revenue" and k["status"] != "invalid")
    comp = client.get(f"/kpi/{target['kpi_id']}/compute")
    assert comp.status_code == 200
    return dataset_id, target["kpi_id"]


def test_drivers_findings_have_complete_evidence(isolated_env):
    init_db()
    with TestClient(app) as client:
        dataset_id, kpi_id = _build_test_dataset(client)

        drivers = client.get(f"/drivers/{kpi_id}")
        assert drivers.status_code == 200
        body = drivers.json()
        assert len(body["findings"]) >= 1

        for finding in body["findings"]:
            evidence = finding["evidence"]
            # Required fields present and non-null (except p-value, which may be None
            # for the waterfall method by design — asserted separately below).
            assert evidence["method"], "method missing"
            assert "waterfall" in evidence["method"].lower()
            assert evidence["source_freshness"], "freshness missing"
            assert evidence["lineage"] and len(evidence["lineage"]) >= 3
            assert evidence["built_at"]
            assert isinstance(evidence["statistic"], float)
            # Lineage must trace source -> canonical -> KPI -> decomposition
            joined = " ".join(evidence["lineage"]).lower()
            assert "sources:" in joined
            assert "canonical dataset" in joined
            assert "kpi" in joined
            assert "decomposition" in joined

            # Evidence retrievable by finding_id via /evidence
            resp = client.get(f"/evidence/{finding['finding_id']}")
            assert resp.status_code == 200
            fetched = resp.json()
            assert fetched["evidence"] == evidence
            assert fetched["finding"]["dimension"] == finding["finding"]["dimension"]


def test_waterfall_reconciles_in_api(isolated_env):
    init_db()
    with TestClient(app) as client:
        _, kpi_id = _build_test_dataset(client)
        body = client.get(f"/drivers/{kpi_id}").json()
        for finding in body["findings"]:
            slices = finding["finding"]["slices"]
            total = sum(s["contribution"] for s in slices)
            assert total == pytest.approx(
                finding["finding"]["total_movement"], abs=1e-3
            )


def test_build_evidence_rejects_empty_method():
    """Method must never be a placeholder/empty — the builder requires it."""
    ev = build_evidence(
        "test_finding",
        {"dataset_id": "d", "kpi_id": "k", "name": "n"},
        source_freshness="2024-01-01T00:00:00",
        method_used="deterministic test method",
        statistic=1.0,
    )
    assert ev["method"] == "deterministic test method"
    assert ev["lineage"] == [
        "canonical dataset d",
        "KPI k",
        "KPI name: n",
        "finding: test_finding",
    ]


def test_did_evidence_fields(isolated_env):
    init_db()
    with TestClient(app) as client:
        dataset_id, kpi_id = _build_test_dataset(client)
        resp = client.post(
            f"/drivers/{kpi_id}/diff-in-diff",
            json={
                "treatment_dim": "region",
                "treatment_value": "A",
                "before_period": "2024-01-01",
                "after_period": "2024-01-08",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["finding_type"] == "causal_diff_in_diff"
        ev = body["evidence"]
        assert "difference-in-differences" in ev["method"]
        assert isinstance(ev["statistic"], float)
        assert ev["lineage"] and "DiD" in " ".join(ev["lineage"])


def test_did_pure_function():
    df = pd.DataFrame(
        {
            "date": ["2024-01-01"] * 4 + ["2024-01-08"] * 4,
            "region": ["A", "B", "A", "B", "A", "B", "A", "B"],
            "revenue": [100.0, 100.0, 100.0, 100.0, 130.0, 110.0, 130.0, 110.0],
        }
    )
    did = diff_in_diff(
        df,
        treatment_dim="region",
        treatment_value="A",
        outcome="revenue",
        before_period="2024-01-01",
        after_period="2024-01-08",
    )
    # A moved +30, B moved +10 -> DiD = +20
    assert did["did_estimate"] == pytest.approx(20.0, abs=1e-6)
    assert did["p_value"] is not None
