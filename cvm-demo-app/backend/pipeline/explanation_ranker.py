"""Explanation Ranker — scores and ranks candidate explanations for each
stacked diagnosis, using evidence chains and the scoring formula from the spec.

score = signal_score x module_diversity x recency_bonus x weight x score_boost
        x concept_coherence_bonus
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from pipeline.evidence_chains import EvidenceChain, ChainStep, _STACKED_TO_TEMPLATE


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RankedExplanation:
    diagnosis: str
    rank: str                       # "primary" | "secondary" | "co-primary" | "ungrounded"
    relationship: str
    label: str
    mechanism: str
    specificity: str
    score: float
    evidence_chain: EvidenceChain | None
    supporting_findings: list[str]
    supporting_concepts: list[str]
    primary_driver_concepts: list[str]
    affected_concepts: list[str]
    chain_instruction: str


# ---------------------------------------------------------------------------
# Severity weights
# ---------------------------------------------------------------------------

_SEVERITY_WEIGHT: dict[str, int] = {
    "CRITICAL": 4,
    "HIGH":     3,
    "MEDIUM":   2,
    "LOW":      1,
}


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _signal_score(finding_ids: list[str], findings_by_id: dict[str, dict]) -> float:
    """Sum of severity weights for the supporting findings."""
    total = 0.0
    for fid in finding_ids:
        f = findings_by_id.get(fid, {})
        sev = (f.get("severity") or "MEDIUM").upper()
        total += _SEVERITY_WEIGHT.get(sev, 1)
    return total


def _module_diversity(finding_ids: list[str], findings_by_id: dict[str, dict]) -> int:
    """Count of distinct modules contributing evidence."""
    modules = {findings_by_id[fid].get("module", "") for fid in finding_ids if fid in findings_by_id}
    modules.discard("")
    return max(len(modules), 1)


def _parse_period_rank(period: str) -> int:
    """Convert a period string to a rough rank (higher = more recent).

    Handles formats: "2024-12-31", "Q2 2023", "2024", empty.
    """
    if not period:
        return 0
    # Try extracting a year
    m = re.search(r"(\d{4})", str(period))
    if not m:
        return 0
    year = int(m.group(1))
    # Quarter bonus
    qm = re.search(r"Q(\d)", str(period))
    quarter = int(qm.group(1)) if qm else 0
    # Month bonus
    mm = re.search(r"-(\d{2})-", str(period))
    month = int(mm.group(1)) if mm else quarter * 3
    return year * 100 + month


def _recency_bonus(finding_ids: list[str], findings_by_id: dict[str, dict]) -> float:
    """Max recency weight among supporting findings.

    Sorts all findings by period, assigns: latest=1.5, 2nd=1.2, 3rd=1.0,
    4th=0.8, 5th+=0.5.  Returns the best bonus among the supporting set.
    """
    if not finding_ids:
        return 1.0

    # Rank ALL findings by period to determine recency tiers
    all_sorted = sorted(
        findings_by_id.values(),
        key=lambda f: _parse_period_rank(f.get("period", "")),
        reverse=True,
    )
    # Assign tier bonuses
    tier_bonuses = [1.5, 1.2, 1.0, 0.8]
    id_to_bonus: dict[str, float] = {}
    seen_periods: list[int] = []
    tier = 0
    for f in all_sorted:
        fid = f.get("id", "")
        if not fid:
            continue
        rank = _parse_period_rank(f.get("period", ""))
        if not seen_periods or rank != seen_periods[-1]:
            seen_periods.append(rank)
            tier = len(seen_periods) - 1
        bonus = tier_bonuses[tier] if tier < len(tier_bonuses) else 0.5
        id_to_bonus[fid] = bonus

    best = max((id_to_bonus.get(fid, 0.5) for fid in finding_ids), default=1.0)
    return best


def _concept_coherence_bonus(
    finding_ids: list[str],
    findings_by_id: dict[str, dict],
) -> float:
    """1.0 to 1.2 bonus when supporting findings reinforce the same concepts.

    Measures how concentrated the concept annotations are across the
    supporting findings.  If ≥60% of findings share the same primary or
    affected concept, bonus is 1.2.  If ≥40%, 1.1.  Otherwise 1.0.
    """
    if len(finding_ids) < 2:
        return 1.0

    all_concepts: list[str] = []
    for fid in finding_ids:
        f = findings_by_id.get(fid, {})
        all_concepts.extend(f.get("concepts", []))
        all_concepts.extend(f.get("affected_concepts", []))

    if not all_concepts:
        return 1.0

    counts = Counter(all_concepts)
    top_count = counts.most_common(1)[0][1]
    ratio = top_count / len(finding_ids)

    if ratio >= 0.6:
        return 1.2
    if ratio >= 0.4:
        return 1.1
    return 1.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rank_explanations(
    chains: list[EvidenceChain],
    findings: list[dict],
    explanation_templates: dict[str, dict],
) -> list[RankedExplanation]:
    """Score and rank candidate explanations for each diagnosis.

    For each stacked diagnosis that has chains, looks up candidate
    explanations from the template, scores each one, and tags rank as
    "primary", "secondary", or "co-primary" (top two within 15%).

    Diagnoses with no matching chains are flagged as "ungrounded".
    """
    # Index findings by id for fast lookup
    findings_by_id = {f["id"]: f for f in findings if f.get("id")}

    # Group chains by diagnosis
    chains_by_dx: dict[str, list[EvidenceChain]] = {}
    for chain in chains:
        chains_by_dx.setdefault(chain.diagnosis, []).append(chain)

    # Find all diagnoses from stacked findings
    stacked = [f for f in findings if f.get("module") == "stacked"]
    all_dx_codes = {f.get("code", ""): f for f in stacked}

    results: list[RankedExplanation] = []

    for dx_code, stacked_f in all_dx_codes.items():
        template_key = _STACKED_TO_TEMPLATE.get(dx_code, "")
        dx_label = {
            "STACKED_FINANCIAL_DISTRESS_RISK": "DX-1",
            "STACKED_WORKING_CAPITAL_TRAP":    "DX-2",
            "STACKED_LOW_QUALITY_GROWTH":      "DX-3",
            "STACKED_CONFIRMED_RECOVERY":      "DX-4",
            "STACKED_REFINANCING_CLIFF_RISK":  "DX-5",
        }.get(dx_code, dx_code)

        template = explanation_templates.get(template_key)
        dx_chains = chains_by_dx.get(dx_label, [])
        chain_instruction = (template or {}).get("chain_instruction", "")

        if not template or not dx_chains:
            # Ungrounded — no structural explanation matched
            results.append(RankedExplanation(
                diagnosis=dx_label,
                rank="ungrounded",
                relationship="",
                label=f"No structural explanation matched for {dx_label}",
                mechanism="",
                specificity="",
                score=0.0,
                evidence_chain=None,
                supporting_findings=[],
                supporting_concepts=[],
                primary_driver_concepts=[],
                affected_concepts=[],
                chain_instruction=chain_instruction,
            ))
            continue

        # Index chains by ALL relationships in any step (not just the first)
        # so template candidates that appear mid-chain are still matched.
        chain_by_rel: dict[str, EvidenceChain] = {}
        for chain in dx_chains:
            for step in chain.steps:
                rel_id = step.relationship
                existing = chain_by_rel.get(rel_id)
                if existing is None or chain.total_evidence_count > existing.total_evidence_count:
                    chain_by_rel[rel_id] = chain

        # Score each candidate explanation from the template
        scored: list[tuple[float, RankedExplanation]] = []
        for candidate in template.get("candidate_explanations", []):
            rel_id = candidate.get("relationship", "")
            chain = chain_by_rel.get(rel_id)
            if chain is None:
                continue

            # Collect all supporting findings across chain steps
            all_finding_ids: list[str] = []
            all_concepts: list[str] = []
            all_drivers: list[str] = []
            all_affected: list[str] = []
            for step in chain.steps:
                for fid in step.supporting_findings:
                    if fid not in all_finding_ids:
                        all_finding_ids.append(fid)
                for c in step.supporting_concepts:
                    if c not in all_concepts:
                        all_concepts.append(c)
                for c in step.driver_concepts:
                    if c not in all_drivers:
                        all_drivers.append(c)
                for c in step.outcome_concepts:
                    if c not in all_affected:
                        all_affected.append(c)

            # Scoring formula
            sig = _signal_score(all_finding_ids, findings_by_id)
            diversity = _module_diversity(all_finding_ids, findings_by_id)
            recency = _recency_bonus(all_finding_ids, findings_by_id)
            weight = 1.0
            # Get weight from the relationship in the chain's first step
            # (we'd need the relationships dict — retrieve from chain step metadata)
            # For now, use a default weight passed via the chain or from the template
            score_boost = candidate.get("score_boost", 1.0)
            coherence = _concept_coherence_bonus(all_finding_ids, findings_by_id)

            total_score = sig * diversity * recency * weight * score_boost * coherence

            mechanism = chain.steps[0].mechanism if chain.steps else ""
            specificity = chain.steps[0].specificity if chain.steps else ""

            ranked = RankedExplanation(
                diagnosis=dx_label,
                rank="",  # set below
                relationship=rel_id,
                label=candidate.get("label", ""),
                mechanism=mechanism,
                specificity=specificity,
                score=round(total_score, 2),
                evidence_chain=chain,
                supporting_findings=all_finding_ids,
                supporting_concepts=all_concepts,
                primary_driver_concepts=all_drivers,
                affected_concepts=all_affected,
                chain_instruction=chain_instruction,
            )
            scored.append((total_score, ranked))

        if not scored:
            results.append(RankedExplanation(
                diagnosis=dx_label,
                rank="ungrounded",
                relationship="",
                label=f"No candidate explanations matched for {dx_label}",
                mechanism="",
                specificity="",
                score=0.0,
                evidence_chain=None,
                supporting_findings=[],
                supporting_concepts=[],
                primary_driver_concepts=[],
                affected_concepts=[],
                chain_instruction=chain_instruction,
            ))
            continue

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Assign ranks
        top_score = scored[0][0]
        for i, (s, exp) in enumerate(scored):
            if i == 0:
                exp.rank = "primary"
            elif top_score > 0 and s >= top_score * 0.85:
                exp.rank = "co-primary"
                scored[0][1].rank = "co-primary"
            else:
                exp.rank = "secondary"
            results.append(exp)

    return results
