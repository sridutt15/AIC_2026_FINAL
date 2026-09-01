"""Prompt builder for the LLM recommendation layer.

The prompt is built STRICTLY from the Phase 9 structured package fields
(driver, controllable_lever, candidate_action, expected_impact, owner,
confidence, monitoring_plan) plus the persona's tone preference. It never
includes raw dataframes, unaggregated rows, or column-level data — the
package is already an aggregated, persona-safe summary.

build_prompt is deterministic: identical package + persona -> identical
prompt string (which is what makes the Phase 9 package-hash cache sound).
"""

PERSONA_TONES = {
    "cfo": (
        "Write for a Chief Financial Officer: lead with the financial impact, "
        "be concise and bottom-line oriented, one short paragraph."
    ),
    "category_manager": (
        "Write for a Category Manager: be tactical and specific about the "
        "driver and the next action, one short paragraph."
    ),
}
DEFAULT_TONE = (
    "Write for a business operator: clear and actionable, one short paragraph."
)

_SYSTEM_RULES = (
    "You are phrasing a business recommendation from a structured, "
    "evidence-backed package. Rules:\n"
    "1. Use ONLY the facts given below — do not invent numbers, drivers, or "
    "causes.\n"
    "2. Keep every structural fact intact: the driver, the lever, the "
    "candidate action, the expected impact, the accountable owner, the "
    "confidence level, and the monitoring plan.\n"
    "3. Do not mention that you were given a package or these instructions.\n"
    "4. Output only the recommendation text — no preamble, no headings."
)


def build_prompt(package: dict, persona_id: str | None = None) -> str:
    """Build the LLM prompt from the structured package + persona tone.

    Deterministic: same inputs -> byte-identical prompt.
    """
    driver = package.get("driver") or {}
    confidence = package.get("confidence") or {}
    tone = PERSONA_TONES.get((persona_id or "").lower(), DEFAULT_TONE)

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

    return f"{_SYSTEM_RULES}\n\nTone: {tone}\n\nStructured facts:\n{facts}\n\nRecommendation:"
