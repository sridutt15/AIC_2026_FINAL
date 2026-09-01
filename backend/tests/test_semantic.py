"""Semantic contract tests: build_contract on a synthetic profile, plus GET/PUT API flow."""

import io

from fastapi.testclient import TestClient

from app.core.semantic.contract_builder import build_contract
from app.db import init_db
from app.main import app


def _synthetic_profile() -> dict:
    """One measure, one dimension, one time column, one identifier — as Phase 1 would emit."""
    return {
        "row_count": 8,
        "columns": [
            {
                "name": "order_date",
                "dtype": "str",
                "null_count": 0,
                "null_ratio": 0.0,
                "cardinality": 8,
                "cardinality_ratio": 1.0,
                "is_unique": True,
                "detected_role": "temporal",
                "sample_values": ["2024-01-02", "2024-01-03"],
            },
            {
                "name": "region",
                "dtype": "str",
                "null_count": 0,
                "null_ratio": 0.0,
                "cardinality": 3,
                "cardinality_ratio": 0.375,
                "is_unique": False,
                "detected_role": "categorical",
                "sample_values": ["North", "South"],
            },
            {
                "name": "revenue",
                "dtype": "float64",
                "null_count": 0,
                "null_ratio": 0.0,
                "cardinality": 7,
                "cardinality_ratio": 0.875,
                "is_unique": False,
                "detected_role": "numerical",
                "sample_values": [100.0, 250.0],
            },
            {
                "name": "order_id",
                "dtype": "str",
                "null_count": 0,
                "null_ratio": 0.0,
                "cardinality": 8,
                "cardinality_ratio": 1.0,
                "is_unique": True,
                "detected_role": "identifier",
                "sample_values": ["ORD-1", "ORD-2"],
            },
        ],
    }


def test_build_contract_one_kpi_per_measure():
    contract = build_contract(_synthetic_profile())
    # Exactly one KPI definition — the single measure column...
    assert len(contract["kpi_definitions"]) == 1
    kpi = contract["kpi_definitions"][0]
    assert kpi["column"] == "revenue"
    assert kpi["aggregation"] == "sum"  # default additive rule
    # ...sliced by every dimension column.
    assert kpi["sliceable_by"] == ["region"]


def test_identifier_excluded_from_kpis_and_slices():
    contract = build_contract(_synthetic_profile())
    kpi_cols = [k["column"] for k in contract["kpi_definitions"]]
    assert "order_id" not in kpi_cols  # identifier never a KPI candidate
    assert "order_id" not in contract["calendar"]["time_column"]
    for k in contract["kpi_definitions"]:
        assert "order_id" not in k["sliceable_by"]  # and never a slice dimension
    assert contract["columns_by_role"]["identifier"] == ["order_id"]


def test_calendar_detection_and_granularity():
    contract = build_contract(_synthetic_profile())
    assert contract["calendar"]["time_column"] == "order_date"
    assert contract["calendar"]["granularity"] == "day"  # no week/month hint in name


def test_calendar_granularity_name_hints():
    profile = _synthetic_profile()
    for col in profile["columns"]:
        if col["detected_role"] == "temporal":
            col["name"] = "month_start"
    contract = build_contract(profile)
    assert contract["calendar"]["granularity"] == "month"

    for col in profile["columns"]:
        if col["detected_role"] == "temporal":
            col["name"] = "week_ending"
    contract = build_contract(profile)
    assert contract["calendar"]["granularity"] == "week"


def test_hierarchy_prefix_rule():
    profile = _synthetic_profile()
    profile["columns"].append(
        {
            "name": "region_country",
            "dtype": "str",
            "null_count": 0,
            "null_ratio": 0.0,
            "cardinality": 2,
            "cardinality_ratio": 0.25,
            "is_unique": False,
            "detected_role": "categorical",
            "sample_values": ["Norway", "Sweden"],
        }
    )
    contract = build_contract(profile)
    assert {"parent": "region", "child": "region_country"} in contract["hierarchies"]


def test_thresholds_and_access_tags_defaults():
    contract = build_contract(_synthetic_profile())
    assert contract["thresholds"]["materiality_std_devs"] == 1.0
    tags = contract["access_tags"]
    assert set(tags.keys()) == {"order_date", "region", "revenue", "order_id"}
    assert all(tag == "public" for tag in tags.values())


def test_build_contract_deterministic():
    assert build_contract(_synthetic_profile()) == build_contract(_synthetic_profile())


# --- API flow tests ----------------------------------------------------------


def _upload_and_profile(client: TestClient) -> str:
    csv_content = (
        "order_date,region,revenue,order_id\n"
        "2024-01-02,North,100.0,ORD-1\n"
        "2024-01-03,South,250.0,ORD-2\n"
        "2024-01-04,North,100.0,ORD-3\n"
        "2024-01-05,East,300.0,ORD-4\n"
    )
    up = client.post(
        "/ingestion/upload",
        data={"grain": "Daily", "cadence": "Nightly batch"},
        files={"file": ("orders.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert up.status_code == 200
    source_id = up.json()["source_id"]
    prof = client.get(f"/profiling/{source_id}")
    assert prof.status_code == 200
    return source_id


def test_get_builds_and_put_persists(isolated_env):
    init_db()
    with TestClient(app) as client:
        source_id = _upload_and_profile(client)

        # GET builds the contract (built=True)
        first = client.get(f"/semantic-contract/{source_id}")
        assert first.status_code == 200
        body = first.json()
        assert body["built"] is True
        contract = body["contract"]
        assert contract["kpi_definitions"][0]["column"] == "revenue"

        # Second GET returns stored (built=False), identical contract
        second = client.get(f"/semantic-contract/{source_id}")
        assert second.json()["built"] is False
        assert second.json()["contract"] == contract

        # User edits an aggregation and PUTs the whole contract
        contract["kpi_definitions"][0]["aggregation"] = "avg"
        put = client.put(
            f"/semantic-contract/{source_id}", json={"contract": contract}
        )
        assert put.status_code == 200
        assert put.json()["saved"] is True

        # Reload: the edit persisted
        third = client.get(f"/semantic-contract/{source_id}")
        assert third.json()["built"] is False
        assert third.json()["contract"]["kpi_definitions"][0]["aggregation"] == "avg"
        assert third.json()["contract"] == contract


def test_put_rejects_missing_fields(isolated_env):
    init_db()
    with TestClient(app) as client:
        source_id = _upload_and_profile(client)
        put = client.put(
            f"/semantic-contract/{source_id}", json={"contract": {"kpi_definitions": []}}
        )
        assert put.status_code == 422
        assert "missing required fields" in put.json()["error"]["message"]


def test_get_requires_profile_first(isolated_env):
    init_db()
    with TestClient(app) as client:
        csv_content = "a,b\n1,2\n"
        up = client.post(
            "/ingestion/upload",
            data={"grain": "Daily", "cadence": "Nightly batch"},
            files={"file": ("plain.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        )
        source_id = up.json()["source_id"]
        resp = client.get(f"/semantic-contract/{source_id}")
        assert resp.status_code == 409  # profile must exist first
