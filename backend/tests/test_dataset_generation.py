"""Tests for the deterministic enterprise dataset generator.

The generator is the single reusable dataset for all phases; these tests pin
its ground truth so regressions are caught immediately.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Make scripts/ importable when pytest runs from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generate_enterprise_dataset import (  # noqa: E402
    ANOMALY_MANIFEST,
    DAYS,
    REGIONS,
    generate,
    validate,
)


@pytest.fixture(scope="module")
def dataset_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("enterprise_dataset")
    generate(out)
    return out


def test_generator_is_deterministic(tmp_path):
    """Same seed -> byte-identical files (project determinism rule)."""
    out1 = tmp_path / "a"
    out2 = tmp_path / "b"
    generate(out1)
    generate(out2)
    for name in ("transactions.csv", "customers.csv", "marketing_daily.csv", "ops_calendar.csv"):
        b1 = (out1 / name).read_bytes()
        b2 = (out2 / name).read_bytes()
        assert b1 == b2, f"{name} differs between runs"


def test_ground_truth_validation_passes(dataset_dir):
    """Every designed structural property and anomaly validates."""
    result = validate(dataset_dir)
    failed = [c for c in result["checks"] if not c["passed"]]
    assert not failed, f"Failed checks: {failed}"


def test_row_counts(dataset_dir):
    tx = pd.read_csv(dataset_dir / "transactions.csv")
    assert len(tx) >= 2000
    manifest_counts = validate(dataset_dir)  # cheap re-run for count consistency
    assert manifest_counts["all_passed"]


def test_transactions_roles_will_profile_correctly(dataset_dir):
    """Columns must profile as expected roles when uploaded (Phase 1 contract).

    Critical detail: region values must include 'North America' — a literal
    'NA' would be read as NaN by pandas and corrupt null-detection.
    """
    tx = pd.read_csv(dataset_dir / "transactions.csv")
    assert set(tx["region"].dropna().unique()) == set(REGIONS)
    # A5 duplicates are identical in EVERY column (incl. order_id), so order_id
    # has exactly 12 repeated values — the double-ingestion pattern.
    assert int(tx.duplicated(keep="first").sum()) == 12
    assert pd.to_datetime(tx["order_date"], format="%Y-%m-%d", errors="coerce").notna().all()


def test_manifest_declares_all_sources_and_anomalies():
    sources = ANOMALY_MANIFEST["sources"]
    assert set(sources) == {
        "transactions.csv",
        "customers.csv",
        "marketing_daily.csv",
        "ops_calendar.csv",
    }
    ids = [a["id"] for a in ANOMALY_MANIFEST["anomalies"]]
    assert ids == ["A1", "A2", "A3", "A4", "A5", "A6"]


def test_calendar_span():
    assert ANOMALY_MANIFEST["calendar"]["days"] == DAYS == 180
