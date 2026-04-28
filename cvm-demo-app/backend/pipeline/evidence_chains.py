"""Evidence Chain Builder — assembles findings into causal chains using the
financial relationship registry, grounded in canonical financial concepts.

Consumes Step 6 findings + stacked diagnoses + relationship registry YAML.
Produces EvidenceChain objects with ordered steps, concept paths, and
supporting-finding references.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pipeline.reasoning_engine import normalize_algorithm, parse_condition


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ChainStep:
    relationship: str
    mechanism: str
    specificity: str
    supporting_findings: list[str]
    supporting_concepts: list[str]
    driver_concepts: list[str]
    outcome_concepts: list[str]
    evidence_count: int


@dataclass
class EvidenceChain:
    diagnosis: str
    steps: list[ChainStep]
    total_evidence_count: int
    chain_description: str
    concept_path: list[str]


# ---------------------------------------------------------------------------
# Stacked-diagnosis code → template key mapping
# ---------------------------------------------------------------------------

_STACKED_TO_TEMPLATE: dict[str, str] = {
    "STACKED_FINANCIAL_DISTRESS_RISK": "DX-1_financial_distress",
    "STACKED_WORKING_CAPITAL_TRAP":    "DX-2_working_capital_trap",
    "STACKED_LOW_QUALITY_GROWTH":      "DX-3_low_quality_growth",
    "STACKED_CONFIRMED_RECOVERY":      "DX-4_confirmed_recovery",
    "STACKED_REFINANCING_CLIFF_RISK":  "DX-5_refinancing_cliff",
}

# Short label for diagnosis references (used in chain_description)
_STACKED_TO_DX: dict[str, str] = {
    "STACKED_FINANCIAL_DISTRESS_RISK": "DX-1",
    "STACKED_WORKING_CAPITAL_TRAP":    "DX-2",
    "STACKED_LOW_QUALITY_GROWTH":      "DX-3",
    "STACKED_CONFIRMED_RECOVERY":      "DX-4",
    "STACKED_REFINANCING_CLIFF_RISK":  "DX-5",
}


# ---------------------------------------------------------------------------
# Distinguisher evaluation
# ---------------------------------------------------------------------------

def _eval_distinguisher(check: str, all_findings: list[dict]) -> bool:
    """Evaluate a distinguisher check expression against the full finding set.

    Supports two patterns:
    1. Flag-style: "sga_drift_present", "equity_negative", etc.
       Resolved by inspecting finding codes, algorithms, and data.
    2. Numeric comparison: "consecutive_decline_periods >= 4"
       Parsed as a condition against each contributing finding's data.
    """
    check = check.strip()

    # Flag-style checks — map to presence/property tests
    flag_checks: dict[str, Any] = {
        "sga_drift_present": lambda: any(
            "SGA" in (f.get("metric") or "").upper()
            for f in all_findings
            if normalize_algorithm(f.get("code", "")) == "cost_composition_drift"
        ),
        "equity_negative": lambda: any(
            (f.get("data_points") or {}).get("total_equity_latest", 1) < 0
            or "negative equity" in (f.get("description") or "").lower()
            or "technical insolvency" in (f.get("description") or "").lower()
            for f in all_findings
            if normalize_algorithm(f.get("code", "")) in ("equity_erosion", "leverage_escalation")
        ),
        "inventory_days_growing": lambda: any(
            normalize_algorithm(f.get("code", "")) == "ccc_expansion"
            for f in all_findings
        ),
        "working_capital_drain_present": lambda: any(
            normalize_algorithm(f.get("code", "")) == "working_capital_cash_drain"
            for f in all_findings
        ),
        "fcf_negative": lambda: any(
            normalize_algorithm(f.get("code", "")) == "fcf_erosion"
            for f in all_findings
        ),
        "equity_eroding": lambda: any(
            normalize_algorithm(f.get("code", "")) == "equity_erosion"
            for f in all_findings
        ),
        "going_concern_present": lambda: any(
            normalize_algorithm(f.get("code", "")) == "going_concern"
            for f in all_findings
        ),
        "capex_starvation_present": lambda: any(
            normalize_algorithm(f.get("code", "")) == "capex_starvation"
            for f in all_findings
        ),
        "fx_debt_concentration_present": lambda: any(
            normalize_algorithm(f.get("code", "")) == "fx_debt_concentration"
            for f in all_findings
        ),
    }

    if check in flag_checks:
        return flag_checks[check]()

    # Numeric comparison — try parse_condition against each finding
    for f in all_findings:
        if parse_condition(check, f):
            return True
    return False


def _evaluate_distinguishers(
    distinguishers: list[dict],
    all_findings: list[dict],
) -> str:
    """Evaluate distinguishers in order. Return the specificity string from the
    first matching check, or a default."""
    for d in distinguishers:
        check = d.get("check", "")
        result = _eval_distinguisher(check, all_findings)
        return d["if_true"] if result else d["if_false"]
    return ""


# ---------------------------------------------------------------------------
# Relationship matching
# ---------------------------------------------------------------------------

def _collect_contributing_findings(
    stacked: dict,
    all_findings: list[dict],
) -> list[dict]:
    """Collect actual finding objects that contributed to a stacked diagnosis.

    The stacked diagnosis has `contributing_signals` mapping module names to
    lists of {code, signal, severity, module}.  We match these codes against
    the full findings list.
    """
    contrib_codes: set[str] = set()
    for sigs in (stacked.get("contributing_signals") or {}).values():
        for sig in sigs:
            code = sig.get("code") or sig.get("signal") or ""
            if code:
                contrib_codes.add(code)

    matched = [
        f for f in all_findings
        if f.get("module") != "stacked"
        and (f.get("code") or f.get("pattern", "")) in contrib_codes
    ]
    return matched


def _match_relationship(
    rel_id: str,
    rel: dict,
    available_findings: list[dict],
) -> ChainStep | None:
    """Check if a relationship's requires are ALL satisfied by the available
    findings.  Returns a ChainStep if matched, None otherwise."""
    requires = rel.get("requires", [])
    if not requires:
        return None

    all_supporting: list[str] = []

    for req in requires:
        algo_name = req.get("algorithm", "")
        condition = req.get("condition", "")

        # Find findings whose normalized algorithm matches
        candidates = [
            f for f in available_findings
            if normalize_algorithm(f.get("code") or f.get("pattern", "")) == algo_name
        ]
        if not candidates:
            return None

        if condition:
            matched = [f for f in candidates if parse_condition(condition, f)]
            if not matched:
                return None
            candidates = matched

        for f in candidates:
            fid = f.get("id", "")
            if fid and fid not in all_supporting:
                all_supporting.append(fid)

    concepts_block = rel.get("concepts", {})
    core = concepts_block.get("core", [])
    drivers = concepts_block.get("driver_candidates", [])
    outcomes = concepts_block.get("outcome_concepts", [])

    return ChainStep(
        relationship=rel_id,
        mechanism=rel.get("description", ""),
        specificity="",  # filled by distinguisher evaluation
        supporting_findings=all_supporting,
        supporting_concepts=list(core),
        driver_concepts=list(drivers),
        outcome_concepts=list(outcomes),
        evidence_count=len(all_supporting),
    )


# ---------------------------------------------------------------------------
# Chain walking (DFS along connects_to links)
# ---------------------------------------------------------------------------

def _walk_chains(
    start_step: ChainStep,
    relationships: dict[str, dict],
    available_findings: list[dict],
    visited: set[str] | None = None,
    depth: int = 0,
    max_depth: int = 4,
) -> list[list[ChainStep]]:
    """Recursively walk connects_to links starting from start_step.

    Returns a list of possible chain paths (each is a list of ChainSteps).
    Single-step results (no extension possible) are also returned — the
    caller filters by min length.
    """
    if visited is None:
        visited = set()

    if depth >= max_depth:
        return [[start_step]]

    visited = visited | {start_step.relationship}
    rel = relationships.get(start_step.relationship, {})
    next_ids = rel.get("connects_to", [])

    paths: list[list[ChainStep]] = []
    extended = False

    for next_id in next_ids:
        if next_id in visited or next_id not in relationships:
            continue
        next_step = _match_relationship(next_id, relationships[next_id], available_findings)
        if next_step is None:
            continue
        sub_paths = _walk_chains(
            next_step, relationships, available_findings,
            visited, depth + 1, max_depth,
        )
        for sp in sub_paths:
            paths.append([start_step] + sp)
        extended = True

    if not extended:
        paths.append([start_step])

    return paths


# ---------------------------------------------------------------------------
# Concept-path construction
# ---------------------------------------------------------------------------

def _build_concept_path(steps: list[ChainStep]) -> list[str]:
    """Build an ordered concept path through the chain:
    driver_concepts → outcome_concepts for each step, deduplicated."""
    path: list[str] = []
    for step in steps:
        for c in step.driver_concepts:
            if c not in path:
                path.append(c)
        for c in step.outcome_concepts:
            if c not in path:
                path.append(c)
    return path


def _concept_coherence_score(steps: list[ChainStep]) -> float:
    """Compute how concept-coherent a chain is.

    Higher score = findings reinforce the same concepts across steps.
    Returns a value between 0 and 1 (used for chain preference, not the
    ranker's concept_coherence_bonus which is 1.0–1.2).
    """
    if len(steps) <= 1:
        return 0.0
    all_concepts: list[str] = []
    for s in steps:
        all_concepts.extend(s.supporting_concepts)
        all_concepts.extend(s.outcome_concepts)
    if not all_concepts:
        return 0.0
    from collections import Counter
    counts = Counter(all_concepts)
    top_freq = counts.most_common(1)[0][1]
    return top_freq / len(steps)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_evidence_chains(
    findings: list[dict],
    stacked_diagnoses: list[dict],
    relationships: dict[str, dict],
) -> tuple[list[EvidenceChain], list[str]]:
    """Build evidence chains for each stacked diagnosis.

    Args:
        findings: all Step 6 findings (including stacked).
        stacked_diagnoses: findings with module == "stacked".
        relationships: loaded financial_relationships.yaml.

    Returns:
        (chains, unmatched_finding_codes): chains for each diagnosis, plus
        codes of non-stacked findings not consumed by any chain.
    """
    non_stacked = [f for f in findings if f.get("module") != "stacked"]
    consumed_ids: set[str] = set()
    all_chains: list[EvidenceChain] = []

    for stacked in stacked_diagnoses:
        dx_code = stacked.get("code", "")
        dx_label = _STACKED_TO_DX.get(dx_code, dx_code)

        # Collect findings that contributed to this diagnosis
        contributing = _collect_contributing_findings(stacked, non_stacked)
        if not contributing:
            continue

        # Match each relationship against the contributing findings
        matched_steps: dict[str, ChainStep] = {}
        for rel_id, rel in relationships.items():
            step = _match_relationship(rel_id, rel, contributing)
            if step is not None:
                step.specificity = _evaluate_distinguishers(
                    rel.get("distinguishers", []), non_stacked,
                )
                matched_steps[rel_id] = step

        if not matched_steps:
            continue

        # Walk connects_to links from each matched relationship to build chains
        candidate_chains: list[list[ChainStep]] = []
        for rel_id, step in matched_steps.items():
            paths = _walk_chains(step, relationships, contributing)
            candidate_chains.extend(paths)

        # Filter: min 2 steps required for a chain
        multi_step = [c for c in candidate_chains if len(c) >= 2]

        # If no multi-step chains, keep single-step matches as 1-step chains
        # (the ranker can still use them even though spec prefers >=2)
        if not multi_step:
            for rel_id, step in matched_steps.items():
                multi_step.append([step])

        # Sort by concept coherence (prefer tighter causal stories)
        multi_step.sort(key=lambda c: _concept_coherence_score(c), reverse=True)

        # Build EvidenceChain objects
        for steps in multi_step:
            concept_path = _build_concept_path(steps)
            desc_parts = [s.relationship.replace("_", " ") for s in steps]
            chain_desc = " → ".join(desc_parts)

            chain = EvidenceChain(
                diagnosis=dx_label,
                steps=steps,
                total_evidence_count=sum(s.evidence_count for s in steps),
                chain_description=chain_desc,
                concept_path=concept_path,
            )
            all_chains.append(chain)

            for step in steps:
                consumed_ids.update(step.supporting_findings)

    # Identify unmatched findings
    all_non_stacked_ids = {f.get("id", "") for f in non_stacked if f.get("id")}
    unmatched = sorted(all_non_stacked_ids - consumed_ids)

    return all_chains, unmatched
