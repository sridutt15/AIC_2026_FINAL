"""Prompt builder for the LLM recommendation layer (Phase 18: bulleted output).

The prompt is built STRICTLY from the Phase 9 structured package fields
(driver, controllable_lever, candidate_action, expected_impact, owner,
confidence, monitoring_plan). It never includes raw dataframes, unaggregated
rows, or column-level data — the package is already an aggregated summary.

build_prompt is deterministic: identical package -> identical prompt string
(which is what makes the Phase 9 package-hash cache sound).
"""

_SYSTEM_RULES = (
    "You are phrasing a business recommendation from a structured, "
    "evidence-backed package. Rules:\n"
    "1. Use ONLY the facts given below — do not invent numbers, drivers, or "
    "causes.\n"
    "2. Keep every structural fact intact: the driver, the lever, the "
    "candidate action, the expected impact, the accountable owner, the "
    "confidence level, and the monitoring plan.\n"
    "3. Do not mention that you were given a package or these instructions.\n"
    "4. Output a short bulleted list of 3-6 concise points, one per line, "
    "each starting with '- '. Cover: what happened, why (the driver), the "
    "recommended action, the expected impact, and the confidence level. "
    "No preamble, no headings, no closing paragraph."
)


def build_prompt(package: dict) -> str:
    """Build the LLM prompt from the structured package.

    Deterministic: same inputs -> byte-identical prompt.
    """
    driver = package.get("driver") or {}
    confidence = package.get("confidence") or {}

    facts = (
        f"KPI movement summary: {package.get('expected_impact', 'n/a')}\n"
        f"Driver: {driver.get('dimension', 'n/a')} = '{driver.get('slice', 'n/a')}' "
        f"(type {driver.get('type', 'n/a')}, direction {driver.get('direction', 'n/a')}, "
        f"contribution {driver.get('contribution', 'n/a')}, "
        f"{driver.get('share_pct', 'n/a')}% of total movement)\n"
        f"Controllable lever: {package.get('controllable_lever', 'n/a')}\n"
        f"Candidate action: {package.get('candidate_action', 'n/a')}\n"
        f"Expected impact: {package.get('expected_impact', 'n/a')}\n"
        f"Accountable owner: {package.get('owner', 'n/a')}\n"
        f"Confidence level: {confidence.get('level', 'n/a')}\n"
        f"Monitoring plan: {package.get('monitoring_plan', 'n/a')}"
    )

    return f"{_SYSTEM_RULES}\n\nStructured facts:\n{facts}\n\nBulleted recommendation:"
