"""Deterministic enterprise dataset generator â€” "Meridian Consumer Brands".

One reusable dataset for ALL phases (upload -> profile -> contract -> quality ->
canonical build -> KPI discovery/compute -> anomaly detection -> drivers ->
evidence/confidence/personas). Seeded (numpy PCG64, seed=20260830) so the exact
same files are produced on every run â€” required by the project's determinism rule.

Four connected sources (classic enterprise shape):

  1. transactions.csv  (grain: Transactional, cadence: Real-time)  ~5,170 rows
     One row per order line. Links to customers via customer_id.
  2. customers.csv     (grain: Custom, cadence: Real-time)          400 rows
     Conformed customer dimension. Joins 1:1 on customer_id.
  3. marketing_daily.csv (grain: Daily, cadence: Nightly batch)     720 rows
     One row per (date, region) â€” commercial spend fact.
  4. ops_calendar.csv    (grain: Daily, cadence: Nightly batch)    720 rows
     One row per (date, region) â€” operations metrics. Joins 1:1 with marketing.

Two canonical builds (both fanout-free by design):
  A) transactions LEFT JOIN customers  ON customer_id        (~5,170 rows)
  B) marketing_daily LEFT JOIN ops_calendar ON (date, region)  (720 rows)

JOIN-SAFETY RULES baked into this design (these are the answers to the
canonical-model join errors â€” see the phase report):
  * Every source on the RIGHT of a join must be UNIQUE on its join key(s):
    customers.customer_id unique; marketing/ops unique on (date, region).
    Without this, each left row matches N right rows -> row explosion
    (this is how an 8.7M-row canonical gets built by accident).
  * All sources in one build must resolve to the SAME cadence rank:
    transactions + customers are both "Real-time" (rank 0) so the customers
    dimension is NEVER LOCF-upsampled. A dimension table that carries any
    date-parseable column (signup_date) at a coarser cadence would be
    forward-filled onto a daily grid first (400 x ~870 days) and then
    fan out the join catastrophically.
  * No region value may collide with pandas' NaN sentinels: "NA" is avoided
    ("North America" used instead) so null detection stays honest.

DESIGNED ANOMALIES (ground truth â€” ANOMALY_MANIFEST below):
  A1  change point: paid marketing spend steps up ~2.3x from 2026-07-15 (sustained).
  A2  spike outlier: flash sale on 2026-06-18, revenue ~5x daily baseline.
  A3  drop outlier: checkout-provider outage on 2026-09-30 (final day) — ~97% of
      all orders suppressed; support tickets surge the same day.
  A4  data quality: exactly 3 transactions with negative revenue.
  A5  data quality: exactly 12 fully duplicated transaction rows.
  A6  data quality: ~6% of transactions have blank region/region_country.

HIERARCHIES (auto-detected by the contract builder's prefix rules):
  region -> region_country          (rule 1: name prefix)
  product_line -> product_line_category (rule 1: name prefix)
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np

SEED = 20260830

# Calendar: 180 days ending 2026-09-30 (inclusive).
START_DATE = date(2026, 4, 4)
DAYS = 180
END_DATE = START_DATE + timedelta(days=DAYS - 1)  # 2026-09-30

# --- Conformed dimension values (fixed, deterministic) -----------------------

# NOTE: no "NA" â€” pandas read_csv would parse it as NaN and corrupt
# null-detection. "North America" keeps the region honest.
REGIONS = ["APAC", "EMEA", "LATAM", "North America"]
REGION_COUNTRIES = {
    "APAC": ["Australia", "India", "Japan", "Singapore"],
    "EMEA": ["France", "Germany", "Poland", "UK"],
    "LATAM": ["Brazil", "Chile", "Mexico"],
    "North America": ["Canada", "US"],
}
PRODUCT_LINES = ["Electronics", "Home", "Outdoor"]
PRODUCT_LINE_CATEGORIES = {
    "Electronics": ["Computers", "Mobile", "Audio"],
    "Home": ["Furniture", "Kitchen"],
    "Outdoor": ["Camping", "Fitness"],
}
SEGMENTS = ["Consumer", "Enterprise", "SMB"]
LTV_TIERS = ["High", "Low", "Medium"]
PAYMENT_METHODS = ["Card", "Netbanking", "Wallet"]
PAYMENT_WEIGHTS = [0.70, 0.10, 0.20]  # Card-dominant checkout (matters for A3)
ORDER_STATUSES = ["Delivered", "Shipped", "Processing", "Cancelled"]
ORDER_STATUS_WEIGHTS = [0.78, 0.11, 0.08, 0.03]

# Anomaly windows (single source of truth for generation AND validation).
SPIKE_DAY = date(2026, 6, 18)                                   # A2
# A3 outage on the FINAL day: a 1-day gateway collapse is (a) realistic,
# (b) flagged by BOTH the trailing control-limit detector and MAD outliers,
# and (c) the latest period-over-period movement — so the driver
# decomposition attributes it to Card, the dominant payment method.
OUTAGE_DAYS = {date(2026, 9, 30)}
SPEND_STEP_DATE = date(2026, 7, 15)                             # A1
NEGATIVE_ROWS = 3                                               # A4
DUPLICATE_ROWS = 12                                              # A5
NULL_REGION_RATE = 0.06                                          # A6

# --- Anomaly ground truth (exported for validation) --------------------------

ANOMALY_MANIFEST = {
    "company": "Meridian Consumer Brands",
    "seed": SEED,
    "calendar": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat(), "days": DAYS},
    "sources": {
        "transactions.csv": {
            "grain": "Transactional",
            "cadence": "Real-time",
            "primary_key": "order_id",
            "joins": {"customer_id": "customers.csv"},
        },
        "customers.csv": {
            "grain": "Custom",
            "cadence": "Real-time",
            "primary_key": "customer_id",
            "joins": {"customer_id": "transactions.csv"},
        },
        "marketing_daily.csv": {
            "grain": "Daily",
            "cadence": "Nightly batch",
            "primary_key": ["date", "region", "channel"],
            "joins": {"(date, region)": "ops_calendar.csv"},  # channel stays marketing-local
        },
        "ops_calendar.csv": {
            "grain": "Daily",
            "cadence": "Nightly batch",
            "primary_key": ["date", "region"],
            "joins": {"(date, region)": "marketing_daily.csv"},
        },
    },
    "canonical_builds": {
        "A_operational_fact": {
            "source_ids_order": ["transactions.csv", "customers.csv"],
            "join_keys": {"customer_id": {"0": "customer_id", "1": "customer_id"}},
            "target_cadence": None,
            "expected_rows": "same as transactions (1:1 join, no fanout)",
        },
        "B_commercial_daily_fact": {
            "source_ids_order": ["marketing_daily.csv", "ops_calendar.csv"],
            "join_keys": {"date": {"0": "date", "1": "date"}, "region": {"0": "region", "1": "region"}},
            "target_cadence": None,
            "expected_rows": 2160,
        },
    },
    "anomalies": [
        {
            "id": "A1", "type": "change_point",
            "description": "Paid marketing spend steps up ~2.3x from 2026-07-15 onward (sustained level shift)",
            "column": "spend", "source": "marketing_daily.csv",
            "window": {"start": "2026-07-15", "end": "2026-09-30"},
            "canonical": "B", "kpi": "sum(spend)",
        },
        {
            "id": "A2", "type": "spike_outlier",
            "description": "Flash sale on 2026-06-18: daily revenue ~5x baseline",
            "column": "revenue", "source": "transactions.csv",
            "window": {"start": "2026-06-18", "end": "2026-06-18"},
            "canonical": "A", "kpi": "sum(revenue)",
        },
        {
            "id": "A3", "type": "drop_outlier",
            "description": "Checkout-provider outage on 2026-09-30 (final day): ~97% of all "
                           "orders suppressed; support tickets surge",
            "column": "revenue", "source": "transactions.csv",
            "window": {"start": "2026-09-30", "end": "2026-09-30"},
            "canonical": "A", "kpi": "sum(revenue)",
        },
        {
            "id": "A4", "type": "data_quality_negative_values",
            "description": f"Exactly {NEGATIVE_ROWS} transactions with revenue < 0 (invalid_range)",
            "column": "revenue", "source": "transactions.csv",
            "row_count": NEGATIVE_ROWS,
        },
        {
            "id": "A5", "type": "data_quality_duplicate_rows",
            "description": f"Exactly {DUPLICATE_ROWS} fully duplicated transaction rows "
                           "(identical in every column — classic double ingestion)",
            "column": "(all columns)", "source": "transactions.csv",
            "row_count": DUPLICATE_ROWS,
        },
        {
            "id": "A6", "type": "data_quality_missing_values",
            "description": "~6% of transactions have blank region/region_country "
                           "(missing_values issue; excluded from region-sliced analyses)",
            "column": "region", "source": "transactions.csv",
        },
    ],
    "expected_hierarchies": [
        {"parent": "region", "child": "region_country"},
        {"parent": "product_line", "child": "product_line_category"},
    ],
}


def _month_seasonal(d: date) -> float:
    doy = d.timetuple().tm_yday
    return 1.0 + 0.15 * float(np.sin(2 * np.pi * (doy - 30) / 365.0))


def _weekend_boost(d: date) -> float:
    return 1.12 if d.weekday() >= 5 else 1.0


def generate(out_dir: Path) -> dict:
    """Generate the four source CSVs + manifest JSON into out_dir (deterministic)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    # ---------------- customers (conformed dimension) -------------------------
    n_customers = 400
    customer_ids = [f"C{i:05d}" for i in range(1, n_customers + 1)]
    cust_region: dict[str, str] = {}
    cust_country: dict[str, str] = {}
    customer_rows = []
    regions = rng.choice(REGIONS, size=n_customers)
    segments = rng.choice(SEGMENTS, size=n_customers, p=[0.45, 0.20, 0.35])
    tiers = rng.choice(LTV_TIERS, size=n_customers, p=[0.5, 0.3, 0.2])
    for i, cid in enumerate(customer_ids):
        region = str(regions[i])
        country = str(rng.choice(REGION_COUNTRIES[region]))
        cust_region[cid] = region
        cust_country[cid] = country
        customer_rows.append(
            {
                "customer_id": cid,
                "region": region,
                "region_country": country,
                "segment": str(segments[i]),
                "ltv_tier": str(tiers[i]),
                "signup_date": (START_DATE - timedelta(days=int(rng.integers(30, 900)))).isoformat(),
            }
        )

    # ---------------- transactions (operational fact) -------------------------
    base_daily_orders = 26
    transactions: list[dict] = []
    tid = 1

    def _make_tx(d: date, promo: bool) -> dict:
        nonlocal tid
        cid = str(rng.choice(customer_ids))
        product_line = str(rng.choice(PRODUCT_LINES))
        qty = int(rng.integers(2, 7)) if promo else int(rng.integers(1, 6))
        unit_price = round(float(rng.uniform(25.0, 260.0) if promo else rng.uniform(18.0, 240.0)), 2)
        discount_pct = 0.15 if promo else round(float(rng.choice([0.0, 0.0, 0.05, 0.1, 0.15])), 2)
        t = {
            "order_id": f"ORD-{tid:06d}",
            "order_date": d.isoformat(),
            "customer_id": cid,
            "region": cust_region[cid],
            "region_country": cust_country[cid],
            "product_line": product_line,
            "product_line_category": str(rng.choice(PRODUCT_LINE_CATEGORIES[product_line])),
            "payment_method": str(rng.choice(PAYMENT_METHODS, p=PAYMENT_WEIGHTS)),
            "quantity": qty,
            "unit_price": unit_price,
            "discount_pct": discount_pct,
            "revenue": round(qty * unit_price * (1 - discount_pct), 2),
            "order_status": str(rng.choice(ORDER_STATUSES, p=ORDER_STATUS_WEIGHTS)),
        }
        tid += 1
        return t

    for d_offset in range(DAYS):
        d = START_DATE + timedelta(days=d_offset)
        n_orders = int(
            max(8, rng.poisson(base_daily_orders * _month_seasonal(d) * _weekend_boost(d)))
        )
        for _ in range(n_orders):
            transactions.append(_make_tx(d, promo=False))

    # A2: flash-sale spike on 2026-06-18 (~5x baseline revenue for that day).
    for _ in range(int(rng.poisson(base_daily_orders * 4.2))):
        transactions.append(_make_tx(SPIKE_DAY, promo=True))

    # A3: checkout-provider outage on the final day — suppress ~97% of ALL
    # orders (the provider fronts the whole checkout, Card-led) so the drop
    # is unambiguous against day-to-day Poisson noise.
    outage_iso = {od.isoformat() for od in OUTAGE_DAYS}
    kept = []
    for t in transactions:
        if (
            t["order_date"] in outage_iso
            and rng.random() < 0.97
        ):
            continue
        kept.append(t)
    transactions = kept

    # A4: corrupt exactly 3 rows with negative revenue.
    neg_idx = rng.choice(len(transactions), size=NEGATIVE_ROWS, replace=False)
    for i in neg_idx:
        transactions[int(i)]["revenue"] = -round(float(rng.uniform(50.0, 400.0)), 2)

    # A6: blank region/region_country on ~6% of rows.
    null_idx = rng.choice(len(transactions), size=int(NULL_REGION_RATE * len(transactions)), replace=False)
    for i in null_idx:
        transactions[int(i)]["region"] = ""
        transactions[int(i)]["region_country"] = ""

    # A5: exactly 12 fully duplicated rows — IDENTICAL in every column
    # including order_id (the classic double-ingestion bug the quality
    # checker's duplicate_rows check exists to catch).
    eligible = [i for i, t in enumerate(transactions) if t["revenue"] >= 0]
    dup_idx = rng.choice(eligible, size=DUPLICATE_ROWS, replace=False)
    transactions.extend(dict(transactions[int(i)]) for i in dup_idx)

    transactions.sort(key=lambda t: (t["order_date"], t["order_id"]))

    # ---------------- marketing_daily (commercial fact, date x region x channel) --
    # NOTE: channel carries the spend attribution; kept as a 3-value dimension
    # with unequal shares so per-channel KPIs are meaningful.
    CHANNELS = ["Email", "Paid Search", "Social"]
    CHANNEL_WEIGHTS = [0.25, 0.45, 0.30]
    marketing = []
    for d_offset in range(DAYS):
        d = START_DATE + timedelta(days=d_offset)
        for region in REGIONS:
            for channel, w in zip(CHANNELS, CHANNEL_WEIGHTS):
                base = float(rng.uniform(600.0, 1100.0)) * w
                spend = base * float(rng.uniform(2.1, 2.5)) if d >= SPEND_STEP_DATE else base  # A1
                marketing.append(
                    {
                        "date": d.isoformat(),
                        "region": region,
                        "channel": channel,
                        "spend": round(spend, 2),
                        "clicks": int(rng.poisson(spend * float(rng.uniform(0.4, 0.7)))),
                        "impressions": int(spend * rng.integers(35, 60)),
                        "campaign_count": int(rng.integers(3, 10)),
                    }
                )

    # ---------------- ops_calendar (operations fact, date x region) -----------
    ops = []
    for d_offset in range(DAYS):
        d = START_DATE + timedelta(days=d_offset)
        outage = d in OUTAGE_DAYS
        spike = d == SPIKE_DAY
        for region in REGIONS:
            tickets = int(rng.poisson(12 * (1.8 if outage else 1.0)))  # outage -> surge
            utilization = float(rng.uniform(55.0, 85.0))
            utilization += 10.0 if spike else 0.0      # flash-sale volume strains warehouses
            utilization = round(min(utilization, 99.0), 1)
            on_time = float(rng.uniform(80.0, 88.0) if outage else rng.uniform(90.0, 98.0))
            couriers = int(rng.uniform(40.0, 70.0) * (_weekend_boost(d)))
            ops.append(
                {
                    "date": d.isoformat(),
                    "region": region,
                    "support_tickets_open": tickets,
                    "active_couriers": couriers,
                    "on_time_delivery_pct": round(on_time, 1),
                    "warehouse_capacity_utilization_pct": utilization,
                }
            )

    # ---------------- Write files ----------------------------------------------
    import csv

    def write_csv(path: Path, rows: list) -> int:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)

    counts = {
        "transactions.csv": write_csv(out_dir / "transactions.csv", transactions),
        "customers.csv": write_csv(out_dir / "customers.csv", customer_rows),
        "marketing_daily.csv": write_csv(out_dir / "marketing_daily.csv", marketing),
        "ops_calendar.csv": write_csv(out_dir / "ops_calendar.csv", ops),
    }

    manifest = json.loads(json.dumps(ANOMALY_MANIFEST))  # deep copy
    manifest["row_counts"] = counts
    with open(out_dir / "anomaly_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def validate(out_dir: Path) -> dict:
    """Validate the generated dataset against its design (ground-truth checks).

    Deterministic self-verification: row counts, referential integrity, join-key
    uniqueness (the fanout guard), semantic hierarchy consistency, and the
    presence of every designed anomaly at its designed magnitude.
    """
    import pandas as pd

    out_dir = Path(out_dir)
    tx = pd.read_csv(out_dir / "transactions.csv")
    cust = pd.read_csv(out_dir / "customers.csv")
    mkt = pd.read_csv(out_dir / "marketing_daily.csv")
    ops = pd.read_csv(out_dir / "ops_calendar.csv")

    checks: list[dict] = []
    ok = True

    def check(name: str, passed: bool, detail: str):
        nonlocal ok
        checks.append({"check": name, "passed": bool(passed), "detail": detail})
        ok = ok and passed

    # --- structure -------------------------------------------------------------
    check("transactions >= 2000 rows", len(tx) >= 2000, f"{len(tx)} rows")
    check(
        "total rows across sources >= 2000",
        len(tx) + len(cust) + len(mkt) + len(ops) >= 2000,
        f"tx={len(tx)}, cust={len(cust)}, mkt={len(mkt)}, ops={len(ops)}",
    )
    check(
        "customers = 400 rows",
        len(cust) == 400,
        f"{len(cust)} rows",
    )
    check(
        "marketing = 180 days x 4 regions x 3 channels = 2160 rows; ops = 720 rows",
        len(mkt) == DAYS * len(REGIONS) * 3 and len(ops) == DAYS * len(REGIONS),
        f"mkt={len(mkt)}, ops={len(ops)}",
    )

    # --- join-key uniqueness (the anti-fanout guarantee) ------------------------
    check(
        "customers.customer_id unique",
        cust["customer_id"].is_unique,
        f"{cust['customer_id'].nunique()} unique of {len(cust)}",
    )
    check(
        "marketing (date, region) join grain unique after channel rollup",
        len(mkt.groupby(["date", "region"])) == DAYS * len(REGIONS),
        f"{len(mkt.groupby(['date', 'region']))} (date, region) groups",
    )
    check(
        "ops (date, region) unique",
        not ops.duplicated(["date", "region"]).any(),
        f"{ops.duplicated(['date', 'region']).sum()} dups",
    )
    missing = int((~tx["customer_id"].isin(set(cust["customer_id"]))).sum())
    check("referential integrity tx -> customers", missing == 0, f"{missing} orphans")

    # --- semantic consistency of hierarchies ------------------------------------
    valid = tx[tx["region"].notna()]
    bad_geo = (
        valid.apply(
            lambda r: r["region_country"]
            not in REGION_COUNTRIES.get(r["region"], []),
            axis=1,
        ).sum()
    )
    check("region -> region_country hierarchy consistent", bad_geo == 0, f"{bad_geo} violations")
    bad_prod = (
        tx.apply(
            lambda r: r["product_line_category"]
            not in PRODUCT_LINE_CATEGORIES.get(r["product_line"], []),
            axis=1,
        ).sum()
    )
    check("product_line -> product_line_category hierarchy consistent", bad_prod == 0, f"{bad_prod} violations")

    # --- column naming does not collide with pandas NaN sentinels ----------------
    region_vals = set(tx["region"].dropna().astype(str).unique())
    check(
        "region values contain no NaN sentinels",
        region_vals == set(REGIONS),
        f"values={sorted(region_vals)}",
    )

    # --- designed anomalies -------------------------------------------------------
    # A2 spike
    daily_rev = tx.groupby("order_date")["revenue"].sum()
    med = float(daily_rev.median())
    spike = float(daily_rev.get("2026-06-18", 0.0))
    check("A2 flash-sale spike present", spike > 3.0 * med, f"spike={spike:.0f} vs median={med:.0f}")

    # A3 outage (single day: 2026-09-30)
    outage_day = tx[tx["order_date"] == "2026-09-30"]
    normal_days = tx[tx["order_date"] != "2026-09-30"]
    outage_orders = len(outage_day)
    normal_orders_per_day = len(normal_days) / DAYS
    check(
        "A3 checkout outage suppresses ~97% of orders",
        outage_orders < 0.10 * normal_orders_per_day,
        f"{outage_orders} orders on outage day vs {normal_orders_per_day:.1f}/day normally",
    )
    total_outage = float(daily_rev.get("2026-09-30", 0.0))
    check(
        "A3 outage visible in TOTAL revenue (~-60%)",
        total_outage < 0.55 * med,
        f"outage total={total_outage:.0f} vs all-day median={med:.0f}",
    )
    ops["date"] = ops["date"].astype(str)
    outage_tickets = float(ops[ops["date"] == "2026-09-30"]["support_tickets_open"].mean())
    all_tickets = float(ops["support_tickets_open"].mean())
    check(
        "A3 support-ticket surge in ops_calendar",
        outage_tickets > 1.4 * all_tickets,
        f"outage={outage_tickets:.1f} vs overall={all_tickets:.1f}",
    )

    # A4 negatives
    neg = int((tx["revenue"] < 0).sum())
    check(f"A4 negative revenue rows == {NEGATIVE_ROWS}", neg == NEGATIVE_ROWS, f"{neg} rows")

    # A5 duplicates: fully identical rows including order_id.
    dups = int(tx.duplicated(keep="first").sum())
    check(f"A5 duplicate rows == {DUPLICATE_ROWS}", dups == DUPLICATE_ROWS, f"{dups} dups")

    # A6 missing region (~6%)
    region_null = int(tx["region"].isna().sum())
    ratio = region_null / len(tx)
    check(
        f"A6 missing region ~{NULL_REGION_RATE:.0%}",
        0.05 <= ratio <= 0.07,
        f"{region_null} rows ({ratio:.2%})",
    )

    # A1 spend step
    pre = float(mkt[mkt["date"] < "2026-07-15"]["spend"].median())
    post = float(mkt[mkt["date"] >= "2026-07-15"]["spend"].median())
    check(
        "A1 marketing spend step-up present",
        post > 1.8 * pre,
        f"post={post:.0f} vs pre={pre:.0f} (ratio {post / pre:.2f}x)",
    )

    return {"all_passed": ok, "checks": checks}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate the Meridian enterprise dataset")
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent.parent / "data" / "enterprise"),
        help="Output directory (default: backend/data/enterprise)",
    )
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    out = Path(args.out)
    if not args.validate_only:
        manifest = generate(out)
        print("Generated: " + ", ".join(f"{k}={v} rows" for k, v in manifest["row_counts"].items()))
    result = validate(out)
    for c in result["checks"]:
        status = "PASS" if c["passed"] else "FAIL"
        print(f"[{status}] {c['check']}: {c['detail']}")
    raise SystemExit(0 if result["all_passed"] else 1)

