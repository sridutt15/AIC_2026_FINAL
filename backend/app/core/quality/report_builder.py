"""Quality report builder: runs all checks and computes a deterministic 0-100 score.

Scoring formula (documented, deterministic — same input -> same score):
    score = 100 - sum of penalties over all issues

Per-issue penalties by severity and type:
    - "high"   severity issue:   10 points per issue occurrence
    - "medium" severity issue:   5 points per issue occurrence
    - "low"    severity issue:   2 points per issue occurrence

Additionally, penalties scale with the share of affected rows so that a "high" issue
touching 1 row doesn't equal one touching every row. The per-issue penalty above is
multiplied by an impact factor:

    impact = 1 + affected_row_count / total_rows   (capped at 2.0)

The final score is clamped to [0, 100] and rounded to one decimal.
"""

from app.core.quality import checks as checks_mod
from app.core.quality.checks import (
    check_duplicates,
    check_invalid_ranges,
    check_missing_values,
    check_outliers,
    check_type_violations,
)

_SEVERITY_WEIGHTS = {"high": 10.0, "medium": 5.0, "low": 2.0}
_MAX_IMPACT = 2.0


def build_quality_report(df, contract: dict, profile: dict | None = None) -> dict:
    """Run every check against df and produce {score, issues, row_count, column_count}.

    Args:
        df: the source's dataframe.
        contract: the source's semantic contract (used by range checks).
        profile: optional stored profile (used by type-violation checks).
    """
    issues: list = []
    issues.extend(check_missing_values(df))
    issues.extend(check_duplicates(df))
    issues.extend(check_invalid_ranges(df, contract))
    issues.extend(check_type_violations(df, profile))
    issues.extend(check_outliers(df, contract))

    row_count = int(len(df))
    column_count = int(len(df.columns))

    score = 100.0
    for issue in issues:
        base = _SEVERITY_WEIGHTS.get(issue["severity"], 2.0)
        if row_count > 0:
            impact = 1.0 + (issue["affected_row_count"] / row_count)
        else:
            impact = 1.0
        score -= base * min(impact, _MAX_IMPACT)

    score = round(max(0.0, min(100.0, score)), 1)

    return {
        "score": score,
        "issues": issues,
        "row_count": row_count,
        "column_count": column_count,
    }
