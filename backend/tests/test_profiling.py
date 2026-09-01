"""Profiler tests: role detection, null_ratio and cardinality against hand-computed values."""

import pandas as pd

from app.core.profiling.profiler import profile_dataframe


def _make_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "transaction_date": [
                "2024-01-01",
                "2024-01-02",
                "2024-01-03",
                "2024-01-04",
                "2024-01-05",
                None,  # 1 null out of 6
            ],
            "revenue": [100.0, 250.0, None, 100.0, 300.0, 120.0],  # 1 null, 100.0 repeats
            "customer_segment": [
                "Consumer",
                "Enterprise",
                "Consumer",
                "SMB",
                "Consumer",
                "Enterprise",
            ],
            "transaction_id": ["T001", "T002", "T003", "T004", "T005", "T006"],  # fully unique
        }
    )


def test_row_count_and_column_set():
    profile = profile_dataframe(_make_df())
    assert profile["row_count"] == 6
    names = [col["name"] for col in profile["columns"]]
    assert names == ["transaction_date", "revenue", "customer_segment", "transaction_id"]


def test_temporal_detection():
    profile = profile_dataframe(_make_df())
    col = profile["columns"][0]
    # 5 non-null values, all parse as dates -> temporal
    assert col["detected_role"] == "temporal"
    assert col["null_count"] == 1
    assert abs(col["null_ratio"] - 1 / 6) < 1e-4  # hand-computed: 1/6, rounded to 4dp
    assert col["cardinality"] == 5


def test_numerical_detection():
    profile = profile_dataframe(_make_df())
    col = profile["columns"][1]
    assert col["detected_role"] == "numerical"
    assert col["null_ratio"] == round(1 / 6, 4)  # hand-computed: 1/6
    assert col["cardinality"] == 4  # 100, 250, 300, 120 (100.0 repeats)
    assert col["is_unique"] is False


def test_categorical_detection():
    profile = profile_dataframe(_make_df())
    col = profile["columns"][2]
    assert col["detected_role"] == "categorical"
    assert col["null_ratio"] == 0.0
    assert col["cardinality"] == 3  # Consumer, Enterprise, SMB
    assert col["is_unique"] is False


def test_identifier_detection():
    profile = profile_dataframe(_make_df())
    col = profile["columns"][3]
    # cardinality 6 of 6 non-null -> ratio 1.0 > 0.95 -> identifier
    assert col["detected_role"] == "identifier"
    assert col["cardinality"] == 6
    assert col["is_unique"] is True
    assert col["null_ratio"] == 0.0


def test_samples_are_first_five_non_null():
    profile = profile_dataframe(_make_df())
    col = profile["columns"][2]
    assert col["sample_values"] == ["Consumer", "Enterprise", "Consumer", "SMB", "Consumer"]
    assert len(profile["columns"][0]["sample_values"]) == 5  # temporal col has 5 non-null


def test_deterministic_output():
    """Same input -> identical output on repeated calls."""
    first = profile_dataframe(_make_df())
    second = profile_dataframe(_make_df())
    assert first == second


def test_empty_dataframe():
    df = pd.DataFrame({"a": pd.Series([], dtype="float64")})
    profile = profile_dataframe(df)
    assert profile["row_count"] == 0
    assert profile["columns"][0]["null_ratio"] == 0.0
    assert profile["columns"][0]["cardinality"] == 0
    assert profile["columns"][0]["sample_values"] == []
