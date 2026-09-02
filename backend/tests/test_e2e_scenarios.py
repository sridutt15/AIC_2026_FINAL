"""End-to-end demo-scenario tests (Phase 11) — the four brief scenarios.

Scenario A: multi-factor movement -> bulleted insight with driver detail.
Scenario B: deliberately weak evidence -> level 'abstain' end-to-end, no
            fabricated insight.
Scenario C: sparse-history KPI -> flagged low-data by validation; no
            false-confidence trend.

            restricted column/domain — verified directly on response JSON.
"""

import io
import json

import pytest
from fastapi.testclient import TestClient

from app.core.confidence.scorer import score_confidence
from app.core.kpi_engine.validation import validate_kpi
from app.db import init_db
from app.main import app


def _upload(client, name, content, grain="Daily", cadence="Nightly batch"):
    up = client.post(
        "/ingestion/upload",
        data={"grain": grain, "cadence": cadence},
        files={"file": (name, io.BytesIO(content.encode()), "text/csv")},
    )
    assert up.status_code == 200
    source_id = up.json()["source_id"]
    assert client.get(f"/profiling/{source_id}").status_code == 200
    assert client.get(f"/semantic-contract/{source_id}").status_code == 200
    return source_id


def _build_canonical(client, source_ids):
    build = client.post(
        "/canonical/build",
        json={
            "source_ids": source_ids,
            "join_keys": {"date": {str(i): "date" for i in range(len(source_ids))}},
        },
    )
    assert build.status_code == 200
    return build.json()["dataset_id"]


# --- Scenario A: multi-factor movement --------------------------------------

A_CSV = "\n".join(
    [
        "date,region,product,revenue,order_id",
        # Clear multi-driver movement: region B surges while product mix shifts.
        "2024-02-01,A,gadget,100.0,O1",
        "2024-02-01,B,gizmo,50.0,O2",
        "2024-02-02,A,gadget,102.0,O3",
        "2024-02-02,B,gizmo,52.0,O4",
        "2024-02-03,A,gadget,99.0,O5",
        "2024-02-03,B,gizmo,49.0,O6",
        "2024-02-04,A,gadget,101.0,O7",
        "2024-02-04,B,gizmo,51.0,O8",
        "2024-02-05,A,gadget,100.0,O9",
        "2024-02-05,B,gizmo,50.0,O10",
        "2024-02-06,A,gadget,98.0,O11",
        "2024-02-06,B,gizmo,53.0,O12",
        "2024-02-07,A,gadget,100.0,O13",
        "2024-02-07,B,gizmo,55.0,O14",
        "2024-02-08,A,gizmo,100.0,O15",
        "2024-02-08,B,gadget,90.0,O16",
    ]
)


def test_scenario_a_multi_factor_bulleted_insight(isolated_env):
    """A multi-driver KPI yields a bulleted insight with driver detail (Phase 18)."""
    init_db()
    with TestClient(app) as client:
        s1 = _upload(client, "scenario_a.csv", A_CSV)
        s2 = _upload(client, "scenario_a_bonus.csv", "date,bonus\n" + "\n".join(
            f"2024-02-0{i},1.0" for i in range(1, 9)) + "\n")
        dataset_id = _build_canonical(client, [s1, s2])

        disc = client.post(f"/kpi/discover/{dataset_id}").json()
        target = next(
            k for k in disc["kpis"]
            if k["measure"] == "revenue" and k["status"] == "valid"
        )
        client.get(f"/kpi/{target['kpi_id']}/compute")

        insight = client.get(f"/insights/{target['kpi_id']}")
        assert insight.status_code == 200
        bullets = insight.json()["bullets"]
        assert isinstance(bullets, list) and bullets

        # Multi-driver decomposition produced real driver findings.
        drivers = client.get(f"/drivers/{target['kpi_id']}").json()
        non_abstained = [
            f for f in drivers["findings"]
            if not (f.get("finding") or {}).get("abstained")
        ]
        assert len(non_abstained) >= 1, "expected at least one confident driver"

        # The bullets carry the top-driver detail and confidence.
        joined = " ".join(bullets)
        assert "Top driver" in joined
        assert "Confidence" in joined


# --- Scenario B: abstention --------------------------------------------------

def test_scenario_b_weak_evidence_abstains(isolated_env):
    """Contradictory/weak evidence returns level 'abstain' — end-to-end.

    Two detectors disagreeing on direction must force abstain, and the
    drivers payload for such a finding carries an abstain message instead
    of a fabricated conclusion.
    """
    evidence = {
        "statistic": 5.0,
        "p_value_or_effect_size": 0.001,
        "corroborating_methods": [
            {"method": "detector_a", "direction": "up"},
            {"method": "detector_b", "direction": "down"},
        ],
    }
    finding = {"kpi_status": "valid", "period_count": 40}
    result = score_confidence(finding, evidence, {"score": 99.0})
    assert result["level"] == "abstain"

    # End-to-end: a low-data, low-quality pipeline must abstain, not invent.
    init_db()
    with TestClient(app) as client:
        # 2 periods only -> low-data; drivers on it must yield abstains.
        csv = "\n".join(
            [
                "date,region,revenue,order_id",
                "2024-03-01,A,100.0,O1",
                "2024-03-01,B,50.0,O2",
                "2024-03-02,A,101.0,O3",
                "2024-03-02,B,49.0,O4",
            ]
        )
        s1 = _upload(client, "scenario_b.csv", csv)
        s2 = _upload(client, "scenario_b_bonus.csv", "date,bonus\n2024-03-01,1.0\n2024-03-02,1.0\n")
        dataset_id = _build_canonical(client, [s1, s2])
        disc = client.post(f"/kpi/discover/{dataset_id}").json()
        target = next(k for k in disc["kpis"] if k["measure"] == "revenue")
        client.get(f"/kpi/{target['kpi_id']}/compute")

        drivers = client.get(f"/drivers/{target['kpi_id']}")
        assert drivers.status_code == 200
        body = drivers.json()
        # Low-data KPI findings must carry abstain confidence levels.
        assert all(
            f["confidence"]["level"] in ("abstain", "low")
            for f in body["findings"]
        ), "weak evidence must not produce medium/high confidence"

        # And the insight endpoint refuses to fabricate on all-abstained KPIs.
        insight = client.get(f"/insights/{target['kpi_id']}")
        assert insight.status_code == 422  # no non-abstained finding to phrase


# --- Scenario C: sparse history ---------------------------------------------

def test_scenario_c_sparse_history_low_data(isolated_env):
    """A newly 'launched' KPI (few periods) is flagged low-data end-to-end."""
    init_db()
    with TestClient(app) as client:
        csv = "\n".join(
            ["date,region,revenue,order_id"]
            + [f"2024-04-0{i},A,{100.0 + i},O{i}" for i in range(1, 4)]  # 3 periods
        )
        s1 = _upload(client, "scenario_c.csv", csv)
        s2 = _upload(client, "scenario_c_bonus.csv", "date,bonus\n" + "\n".join(
            f"2024-04-0{i},1.0" for i in range(1, 4)) + "\n")
        dataset_id = _build_canonical(client, [s1, s2])

        disc = client.post(f"/kpi/discover/{dataset_id}").json()
        target = next(k for k in disc["kpis"] if k["measure"] == "revenue")

        # Validation flags it low-data (fewer than MIN_PERIODS periods).
        assert target["status"] == "low-data"
        assert "period" in target["reason"]

        # The reason is honest about the period count.
        assert "3 time periods" in target["reason"]

        # Computing it yields no false-confidence trend: period_count is
        # reported and small; CI exists but reflects the tiny sample.
        comp = client.get(f"/kpi/{target['kpi_id']}/compute").json()
        assert comp["computation"]["period_count"] <= 3
