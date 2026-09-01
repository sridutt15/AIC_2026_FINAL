"""Rule-based lever library: driver types -> controllable levers + actions.

This is a HEURISTIC STARTING LIBRARY — a small, transparent, rule-based
lookup, not an exhaustive taxonomy and NOT an LLM. It maps dimension-name
keywords to driver types (price/volume/mix/marketing/supply/seasonality/
channel/region/quality), each with:

    lever           : the controllable business lever
    candidate_action: a concrete action to evaluate
    owner           : the persona accountable for acting on it
    metric          : what to monitor to see whether it worked

Types are inferred from dimension names in the semantic contract (Phase 2's
columns_by_role.dimension entries) via keyword matching — deliberately
simple so failures are debuggable. Extend DRIVER_TYPE_KEYWORDS or LEVERS to
add coverage; anything unmatched falls back to "other".

Example matching (case-insensitive substring):
    "region"        -> region
    "day_of_week"   -> seasonality
    "supplier_name" -> supply
"""

# keyword (lowercase substring of the dimension name) -> driver type.
# Order matters only for readability; lookup picks the FIRST keyword hit.
DRIVER_TYPE_KEYWORDS = [
    ("price", "price"),
    ("unit_price", "price"),
    ("list_price", "price"),
    ("discount", "price"),
    ("promo", "marketing"),
    ("campaign", "marketing"),
    ("marketing", "marketing"),
    ("channel", "channel"),
    ("platform", "channel"),
    ("store", "channel"),
    ("warehouse", "supply"),
    ("supplier", "supply"),
    ("vendor", "supply"),
    ("inventory", "supply"),
    ("stock", "supply"),
    ("logistics", "supply"),
    ("shipping", "supply"),
    ("region", "region"),
    ("country", "region"),
    ("market", "region"),
    ("city", "region"),
    ("zip", "region"),
    ("postal", "region"),
    ("category", "mix"),
    ("product", "mix"),
    ("sku", "mix"),
    ("item", "mix"),
    ("menu", "mix"),
    ("month", "seasonality"),
    ("week", "seasonality"),
    ("day", "seasonality"),
    ("hour", "seasonality"),
    ("time", "seasonality"),
    ("season", "seasonality"),
    ("holiday", "seasonality"),
    ("customer", "volume"),
    ("order", "volume"),
    ("traffic", "volume"),
    ("visit", "volume"),
    ("user", "volume"),
    ("quality", "quality"),
    ("rating", "quality"),
    ("review", "quality"),
    ("complaint", "quality"),
]

LEVERS = {
    "price": {
        "lever": "Pricing & discount policy",
        "candidate_action": (
            "Review the price/discount schedule for the affected slices; test "
            "a targeted price or promotion adjustment and measure elasticity "
            "before rolling out."
        ),
        "owner": "cfo",
        "metric": "realized price and discount depth",
    },
    "volume": {
        "lever": "Demand generation & traffic",
        "candidate_action": (
            "Investigate the demand funnel for the affected customer/order "
            "segment; double down on the highest-converting acquisition "
            "channel or fix the drop-off step."
        ),
        "owner": "category_manager",
        "metric": "order volume and conversion rate",
    },
    "mix": {
        "lever": "Category & assortment mix",
        "candidate_action": (
            "Rebalance the assortment toward the slice types gaining share; "
            "review placement and availability of the decliners."
        ),
        "owner": "category_manager",
        "metric": "mix share by product/category",
    },
    "marketing": {
        "lever": "Marketing spend & campaign targeting",
        "candidate_action": (
            "Audit active campaigns touching the affected slices; reallocate "
            "budget toward the segments with proven lift and pause the rest."
        ),
        "owner": "category_manager",
        "metric": "campaign-attributed revenue",
    },
    "supply": {
        "lever": "Supplier & inventory performance",
        "candidate_action": (
            "Check supplier SLAs and stock coverage for the affected slices; "
            "fix stockout/backlog issues before adjusting demand."
        ),
        "owner": "category_manager",
        "metric": "fill rate and stockout count",
    },
    "seasonality": {
        "lever": "Seasonal planning calendar",
        "candidate_action": (
            "Confirm the movement is a recurring seasonal pattern against "
            "last year's same period; adjust the seasonal forecast and "
            "staffing/inventory plan accordingly."
        ),
        "owner": "category_manager",
        "metric": "same-period year-over-year movement",
    },
    "channel": {
        "lever": "Channel operations",
        "candidate_action": (
            "Compare operating metrics across the affected channel/store "
            "slices; replicate the practices of the best performer."
        ),
        "owner": "category_manager",
        "metric": "channel-level conversion and fulfillment",
    },
    "region": {
        "lever": "Regional market focus",
        "candidate_action": (
            "Review regional pricing, competition, and coverage for the "
            "affected regions; prioritize the regions with the largest "
            "recoverable contribution."
        ),
        "owner": "category_manager",
        "metric": "regional contribution trend",
    },
    "quality": {
        "lever": "Product/service quality",
        "candidate_action": (
            "Triage quality signals (ratings, complaints) for the affected "
            "slices; fix the top defect drivers before demand actions."
        ),
        "owner": "category_manager",
        "metric": "average rating and complaint volume",
    },
    "other": {
        "lever": "Operational review",
        "candidate_action": (
            "Run a focused operational review of the affected dimension; "
            "identify the process step behind the movement and pilot a fix."
        ),
        "owner": "category_manager",
        "metric": "dimension-level movement",
    },
}


class LeverLibrary:
    """Small rule-based lookup — deterministic, no external calls."""

    def __init__(self, levers: dict | None = None, keywords: list | None = None):
        self.levers = levers or LEVERS
        self.keywords = keywords if keywords is not None else DRIVER_TYPE_KEYWORDS

    def lookup(self, driver_type: str) -> dict:
        """Lever entry for a driver type; unknown types fall back to 'other'.

        Returns {lever, candidate_action, owner, metric} — all non-null.
        """
        entry = self.levers.get(driver_type) or self.levers["other"]
        return dict(entry)

    def owner_for(self, lever: str) -> str:
        """Persona id accountable for a lever name ('cfo'/'category_manager')."""
        for entry in self.levers.values():
            if entry["lever"] == lever:
                return entry["owner"]
        return "category_manager"


def driver_type_for_dimension(dimension: str) -> str:
    """Infer the driver type from the dimension/column name.

    Case-insensitive substring match against DRIVER_TYPE_KEYWORDS; the first
    hit wins; no hit -> 'other'. Deterministic for any fixed input.
    """
    name = str(dimension or "").lower()
    for keyword, driver_type in DRIVER_TYPE_KEYWORDS:
        if keyword in name:
            return driver_type
    return "other"


# Shared singleton used by the API layer.
lever_library = LeverLibrary()
