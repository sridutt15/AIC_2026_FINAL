"""KPI discovery tests: 2 measures x 1 slice dimension -> expected unique candidates."""

import pandas as pd

from app.core.kpi_engine.discovery import discover_kpis


def _canonical_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=30, freq="D"),
            "region": ["north", "south"] * 15,
            "revenue": [float(i) for i in range(30)],
            "orders": [float(i * 2) for i in range(30)],
            "order_id": [f"O{i}" for i in range(30)],
        }
    )


def _contract() -> dict:
    return {
        "kpi_definitions": [
            {"column": "revenue", "aggregation": "sum", "sliceable_by": ["region"]},
            {"column": "orders", "aggregation": "sum", "sliceable_by": ["region"]},
        ]
    }


def test_two_measures_one_slice_yields_expected_candidates():
    candidates = discover_kpis(_canonical_df(), [_contract()])
    # 2 measures -> 2 KPIs (slice is stored as metadata, not exploded per value)
    assert len(candidates) == 2
    names = {c["name"] for c in candidates}
    assert names == {"sum(revenue) by region", "sum(orders) by region"}
    for c in candidates:
        assert c["time_column"] == "date"
        assert c["slice_columns"] == ["region"]


def test_duplicate_definitions_deduplicated():
    # Same definition twice (e.g. from two merged contracts) -> one candidate
    candidates = discover_kpis(_canonical_df(), [_contract(), _contract()])
    assert len(candidates) == 2

    # Same measure but different aggregation -> distinct
    contract_a = {
        "kpi_definitions": [
            {"column": "revenue", "aggregation": "sum", "sliceable_by": ["region"]},
        ]
    }
    contract_b = {
        "kpi_definitions": [
            {"column": "revenue", "aggregation": "avg", "sliceable_by": ["region"]},
        ]
    }
    both = discover_kpis(_canonical_df(), [contract_a, contract_b])
    assert len(both) == 2
    assert both[0]["name"] != both[1]["name"]


def test_missing_measure_column_filtered_out():
    contract = {
        "kpi_definitions": [
            {"column": "nonexistent_measure", "aggregation": "sum", "sliceable_by": []},
            {"column": "revenue", "aggregation": "sum", "sliceable_by": []},
        ]
    }
    candidates = discover_kpis(_canonical_df(), [contract])
    assert len(candidates) == 1
    assert candidates[0]["measure"] == "revenue"


def test_slice_columns_filtered_to_existing():
    contract = {
        "kpi_definitions": [
            {
                "column": "revenue",
                "aggregation": "sum",
                "sliceable_by": ["region", "missing_dim", "date"],
            }
        ]
    }
    candidates = discover_kpis(_canonical_df(), [contract])
    # missing_dim dropped; time column never a slice
    assert candidates[0]["slice_columns"] == ["region"]


def test_deterministic_order_and_content():
    first = discover_kpis(_canonical_df(), [_contract()])
    second = discover_kpis(_canonical_df(), [_contract()])
    assert first == second
