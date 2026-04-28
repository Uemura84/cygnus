"""Reasoning Engine — Sprints A + B.

Sprint A: concept layer, relationship loading, finding annotation.
Sprint B: evidence chain construction, explanation ranking, orchestration.

Loads the canonical concept vocabulary, financial relationship registry, and
explanation templates from backend/knowledge/ YAML files.  Annotates Step 6
findings with canonical concept references, builds evidence chains from the
financial relationship registry, and ranks candidate explanations for each
stacked diagnosis.

The public entry point is ``run_reasoning_engine(step6_output)`` which
consumes Step 6 output and produces a separate ReasoningOutput — it does
NOT modify the Step 6 output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


# ---------------------------------------------------------------------------
# Algorithm-to-concept mapping
# ---------------------------------------------------------------------------
# Maps each detector algorithm (normalized name) to the canonical concepts it
# touches.  The keys here are the *normalized* algorithm names used in the
# relationship registry.  Actual finding codes from each detector are mapped
# to these keys via _CODE_TO_ALGORITHM below.

ALGORITHM_CONCEPTS: dict[str, dict[str, Any]] = {
    # --- Profitability (pattern_detector.py) ---
    "margin_trend": {
        "concepts": ["revenue", "cogs", "gross_profit", "ebitda"],
        "primary_concept": "gross_profit",
        "affected_concepts": ["ebitda", "net_income"],
    },
    "cost_composition_drift": {
        "concepts": ["revenue", "cogs", "gross_profit"],
        "primary_concept": "cogs",
        "affected_concepts": ["gross_profit", "ebitda"],
    },
    "revenue_cost_decoupling": {
        "concepts": ["revenue", "cogs", "gross_profit"],
        "primary_concept": "revenue",
        "affected_concepts": ["gross_profit", "ebitda"],
    },
    "statistical_anomaly": {
        "concepts": ["revenue", "cogs", "gross_profit", "ebitda"],
        "primary_concept": "gross_profit",
        "affected_concepts": [],
    },
    "yoy_comparison": {
        "concepts": ["revenue", "cogs", "gross_profit", "ebitda"],
        "primary_concept": "gross_profit",
        "affected_concepts": [],
    },
    # --- Balance Sheet (bs_detector.py) ---
    "leverage_escalation": {
        "concepts": ["debt", "ebitda", "equity"],
        "primary_concept": "debt",
        "affected_concepts": ["equity", "free_cash_flow"],
    },
    "working_capital_deterioration": {
        "concepts": ["accounts_receivable", "inventory", "accounts_payable",
                     "working_capital", "operating_cash_flow"],
        "primary_concept": "working_capital",
        "affected_concepts": ["operating_cash_flow"],
    },
    "liquidity_stress": {
        "concepts": ["working_capital", "debt", "operating_cash_flow"],
        "primary_concept": "working_capital",
        "affected_concepts": ["operating_cash_flow", "free_cash_flow"],
    },
    "asset_efficiency": {
        "concepts": ["revenue", "equity", "net_income"],
        "primary_concept": "revenue",
        "affected_concepts": ["net_income"],
    },
    "ccc_expansion": {
        "concepts": ["accounts_receivable", "inventory", "accounts_payable",
                     "cash_conversion_cycle"],
        "primary_concept": "cash_conversion_cycle",
        "affected_concepts": ["operating_cash_flow"],
    },
    "debt_maturity_wall": {
        "concepts": ["debt", "free_cash_flow"],
        "primary_concept": "debt",
        "affected_concepts": ["equity", "operating_cash_flow"],
    },
    "equity_erosion": {
        "concepts": ["equity", "net_income", "debt"],
        "primary_concept": "equity",
        "affected_concepts": ["debt"],
    },
    "fx_debt_concentration": {
        "concepts": ["debt", "equity"],
        "primary_concept": "debt",
        "affected_concepts": ["equity"],
    },
    # --- Cash Flow (cf_detector.py) ---
    "earnings_quality": {
        "concepts": ["net_income", "operating_cash_flow", "working_capital"],
        "primary_concept": "operating_cash_flow",
        "affected_concepts": ["free_cash_flow"],
    },
    "capex_starvation": {
        "concepts": ["capex", "free_cash_flow"],
        "primary_concept": "capex",
        "affected_concepts": ["free_cash_flow"],
    },
    "fcf_erosion": {
        "concepts": ["operating_cash_flow", "capex", "free_cash_flow"],
        "primary_concept": "free_cash_flow",
        "affected_concepts": ["debt", "equity"],
    },
    "debt_dependency": {
        "concepts": ["debt", "free_cash_flow", "operating_cash_flow"],
        "primary_concept": "debt",
        "affected_concepts": ["equity"],
    },
    "dividend_sustainability": {
        "concepts": ["free_cash_flow", "equity", "debt"],
        "primary_concept": "free_cash_flow",
        "affected_concepts": ["equity", "debt"],
    },
    "working_capital_cash_drain": {
        "concepts": ["working_capital", "operating_cash_flow",
                     "accounts_receivable", "inventory"],
        "primary_concept": "working_capital",
        "affected_concepts": ["operating_cash_flow", "free_cash_flow"],
    },
    # --- DVA (dva_detector.py) ---
    "lender_share_escalation": {
        "concepts": ["debt", "equity", "net_income"],
        "primary_concept": "debt",
        "affected_concepts": ["equity"],
    },
    "shareholder_value_erosion": {
        "concepts": ["equity", "net_income", "free_cash_flow"],
        "primary_concept": "equity",
        "affected_concepts": ["net_income"],
    },
    "labor_compression": {
        "concepts": ["cogs", "revenue", "net_income"],
        "primary_concept": "cogs",
        "affected_concepts": ["net_income"],
    },
    # --- Auditor (auditor_detector.py) ---
    "going_concern": {
        "concepts": ["equity", "debt", "operating_cash_flow"],
        "primary_concept": "equity",
        "affected_concepts": [],
    },
    "opinion_qualification": {
        "concepts": ["equity", "net_income"],
        "primary_concept": "equity",
        "affected_concepts": [],
    },
    # auditor_change removed — routine event, weak signal.
    "independence_risk": {
        "concepts": ["equity"],
        "primary_concept": "equity",
        "affected_concepts": [],
    },
    "fee_trend": {
        "concepts": ["equity"],
        "primary_concept": "equity",
        "affected_concepts": [],
    },
    # --- Equity (equity_detector.py) ---
    "dividend_exceeds_income": {
        "concepts": ["equity", "net_income", "free_cash_flow"],
        "primary_concept": "equity",
        "affected_concepts": ["debt"],
    },
    "material_oci": {
        "concepts": ["equity", "net_income"],
        "primary_concept": "equity",
        "affected_concepts": [],
    },
}


# Maps actual finding codes (as they appear in step 6 output) to the
# normalized algorithm names used in ALGORITHM_CONCEPTS and the relationship
# registry.  Pattern-detector findings use title-case pattern strings as
# codes; BS/CF/DVA/AUD/EQ detectors use uppercase prefixed codes.

_CODE_TO_ALGORITHM: dict[str, str] = {
    # Pattern detector
    "Persistent margin decline":        "margin_trend",
    "Sustained margin decline":         "margin_trend",
    "Margin compression":               "margin_trend",
    "Margin expansion":                 "margin_trend",
    "High margin volatility":           "margin_trend",
    "Cost composition drift":           "cost_composition_drift",
    "Potential cost reclassification":   "cost_composition_drift",
    "Revenue-cost decoupling":          "revenue_cost_decoupling",
    "Statistical anomaly":              "statistical_anomaly",
    "YoY quarter comparison":           "yoy_comparison",
    # BS detector
    "BS_LEVERAGE_ESCALATION":           "leverage_escalation",
    "BS_WORKING_CAPITAL_DETERIORATION": "working_capital_deterioration",
    "BS_LIQUIDITY_STRESS":              "liquidity_stress",
    "BS_LIQUIDITY_STRESS_STREAK":       "liquidity_stress",
    "BS_ASSET_EFFICIENCY_DECLINE":      "asset_efficiency",
    "BS_ASSET_EFFICIENCY_STREAK":       "asset_efficiency",
    "BS_CCC_EXPANSION":                 "ccc_expansion",
    "BS_DEBT_MATURITY_CONCENTRATION":   "debt_maturity_wall",
    "BS_MATURITY_WALL":                 "debt_maturity_wall",
    "BS_EQUITY_EROSION":                "equity_erosion",
    "BS_FX_DEBT_CONCENTRATION":         "fx_debt_concentration",
    # CF detector
    "CF_EARNINGS_QUALITY_GAP":          "earnings_quality",
    "CF_CAPEX_STARVATION":              "capex_starvation",
    "CF_FCF_EROSION":                   "fcf_erosion",
    "CF_DEBT_DEPENDENCY":               "debt_dependency",
    "CF_DIVIDEND_SUSTAINABILITY":       "dividend_sustainability",
    "CF_WORKING_CAPITAL_DRAIN":         "working_capital_cash_drain",
    # DVA detector
    "DVA_LENDER_SHARE_ESCALATION":      "lender_share_escalation",
    "DVA_SHAREHOLDER_VALUE_EROSION":    "shareholder_value_erosion",
    "DVA_LABOR_COMPRESSION":            "labor_compression",
    # Auditor detector
    "AUD001":                           "going_concern",
    "AUD002":                           "opinion_qualification",
    # AUD003 (auditor_change) removed — weak signal.
    "AUD004":                           "independence_risk",
    "AUD005":                           "fee_trend",
    # Equity detector
    "EQ_DIVIDEND_EXCEEDS_INCOME":       "dividend_exceeds_income",
    "EQ_MATERIAL_OCI":                  "material_oci",
}


def normalize_algorithm(code: str) -> str | None:
    """Map a finding code to its normalized algorithm name, or None if unknown."""
    return _CODE_TO_ALGORITHM.get(code)


# ---------------------------------------------------------------------------
# YAML loaders with validation
# ---------------------------------------------------------------------------

def load_canonical_concepts(
    path: str | Path | None = None,
) -> dict[str, dict[str, str]]:
    """Load and validate canonical_concepts.yaml.

    Returns a dict of concept_id -> {label, category}.
    """
    path = Path(path) if path else KNOWLEDGE_DIR / "canonical_concepts.yaml"
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"canonical_concepts.yaml must be a YAML mapping, got {type(raw)}")

    concepts: dict[str, dict[str, str]] = {}
    for concept_id, meta in raw.items():
        if not isinstance(meta, dict):
            raise ValueError(f"Concept '{concept_id}' must be a mapping")
        if "label" not in meta:
            raise ValueError(f"Concept '{concept_id}' missing required field 'label'")
        if "category" not in meta:
            raise ValueError(f"Concept '{concept_id}' missing required field 'category'")
        concepts[concept_id] = {
            "label": meta["label"],
            "category": meta["category"],
        }
    return concepts


def load_relationships(
    path: str | Path | None = None,
    concepts: dict[str, dict] | None = None,
) -> dict[str, dict]:
    """Load and validate financial_relationships.yaml.

    Returns a dict of relationship_id -> relationship metadata.
    If `concepts` is provided, validates that every concept referenced in each
    relationship exists in the canonical vocabulary.
    """
    path = Path(path) if path else KNOWLEDGE_DIR / "financial_relationships.yaml"
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"financial_relationships.yaml must be a YAML mapping, got {type(raw)}")

    relationships: dict[str, dict] = {}
    for rel_id, meta in raw.items():
        if not isinstance(meta, dict):
            raise ValueError(f"Relationship '{rel_id}' must be a mapping")
        for field in ("description", "category", "requires"):
            if field not in meta:
                raise ValueError(f"Relationship '{rel_id}' missing required field '{field}'")
        if "concepts" not in meta:
            raise ValueError(f"Relationship '{rel_id}' missing required 'concepts' block")

        concept_block = meta["concepts"]
        for sub in ("core", "driver_candidates", "outcome_concepts"):
            if sub not in concept_block:
                raise ValueError(
                    f"Relationship '{rel_id}' concepts block missing '{sub}'"
                )

        if concepts:
            all_refs = set(
                concept_block.get("core", [])
                + concept_block.get("driver_candidates", [])
                + concept_block.get("outcome_concepts", [])
            )
            unknown = all_refs - set(concepts.keys())
            if unknown:
                raise ValueError(
                    f"Relationship '{rel_id}' references unknown concepts: {unknown}"
                )

        relationships[rel_id] = meta
    return relationships


def load_explanation_templates(
    path: str | Path | None = None,
) -> dict[str, dict]:
    """Load explanation_templates.yaml.

    Returns a dict of diagnosis_key -> template metadata.
    """
    path = Path(path) if path else KNOWLEDGE_DIR / "explanation_templates.yaml"
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"explanation_templates.yaml must be a YAML mapping, got {type(raw)}")

    templates: dict[str, dict] = {}
    for dx_key, meta in raw.items():
        if not isinstance(meta, dict):
            raise ValueError(f"Template '{dx_key}' must be a mapping")
        if "candidate_explanations" not in meta:
            raise ValueError(f"Template '{dx_key}' missing 'candidate_explanations'")
        templates[dx_key] = meta
    return templates


# ---------------------------------------------------------------------------
# Condition parser
# ---------------------------------------------------------------------------

_OPERATORS = {
    "==":  lambda a, b: a == b,
    "!=":  lambda a, b: a != b,
    ">=":  lambda a, b: float(a) >= float(b),
    "<=":  lambda a, b: float(a) <= float(b),
    ">":   lambda a, b: float(a) > float(b),
    "<":   lambda a, b: float(a) < float(b),
}

_COMPARISON_RE = re.compile(
    r"^\s*(\w+)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$"
)

_IN_RE = re.compile(
    r"^\s*(\w+)\s+in\s+\[(.+?)\]\s*$"
)


def _parse_literal(s: str) -> Any:
    """Parse a string literal, number, or leave as-is."""
    s = s.strip()
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        return s[1:-1]
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _resolve_field(field_name: str, finding_detail: dict) -> Any:
    """Look up a field in the finding — top-level first, then data_points,
    then derived fields for compatibility with the relationship registry."""
    if field_name in finding_detail:
        return finding_detail[field_name]
    dp = finding_detail.get("data_points", {})
    if isinstance(dp, dict) and field_name in dp:
        return dp[field_name]
    # Derived field: 'direction' from the pattern name (margin_trend findings
    # don't carry an explicit direction field; the pattern string encodes it).
    if field_name == "direction":
        pattern = (finding_detail.get("pattern") or "").lower()
        if "compression" in pattern or "decline" in pattern:
            return "compression"
        if "expansion" in pattern:
            return "expansion"
        if "improvement" in pattern or "recovery" in pattern:
            return "improvement"
    return None


def _eval_single(expr: str, finding_detail: dict) -> bool:
    """Evaluate a single condition expression against a finding dict."""
    expr = expr.strip()

    m_in = _IN_RE.match(expr)
    if m_in:
        field = m_in.group(1)
        items_raw = m_in.group(2)
        items = [_parse_literal(x) for x in items_raw.split(",")]
        val = _resolve_field(field, finding_detail)
        return val in items

    m_cmp = _COMPARISON_RE.match(expr)
    if m_cmp:
        field = m_cmp.group(1)
        op_str = m_cmp.group(2)
        rhs = _parse_literal(m_cmp.group(3))
        val = _resolve_field(field, finding_detail)
        if val is None:
            return False
        try:
            return _OPERATORS[op_str](val, rhs)
        except (ValueError, TypeError):
            return False

    return False


def parse_condition(condition_str: str, finding_detail: dict) -> bool:
    """Evaluate a condition expression against a finding's detail dict.

    Supports ==, !=, >, <, >=, <=, ``in``, and ``and`` for combining
    sub-conditions.  Returns True if all sub-conditions match.
    """
    if not condition_str or not condition_str.strip():
        return True

    parts = re.split(r"\s+and\s+", condition_str)
    return all(_eval_single(part, finding_detail) for part in parts)


# ---------------------------------------------------------------------------
# Finding annotation
# ---------------------------------------------------------------------------

def annotate_findings_with_concepts(
    findings: list[dict],
    concept_mapping: dict[str, dict[str, Any]] | None = None,
) -> list[dict]:
    """Add concept annotations to each finding in-place and return the list.

    New fields added per finding (when algorithm is recognized):
        concepts         — list[str]: all canonical concepts this finding touches
        primary_concept  — str | None: the single most relevant concept
        affected_concepts — list[str]: concepts impacted downstream

    Findings with module == "stacked" are skipped (they are composite
    diagnoses, not individual algorithm findings).
    """
    mapping = concept_mapping or ALGORITHM_CONCEPTS

    for finding in findings:
        if finding.get("module") == "stacked":
            continue

        code = finding.get("code") or finding.get("pattern", "")
        algo = normalize_algorithm(code)

        if algo and algo in mapping:
            entry = mapping[algo]
            finding["concepts"] = list(entry["concepts"])
            finding["primary_concept"] = entry["primary_concept"]
            finding["affected_concepts"] = list(entry["affected_concepts"])
        else:
            finding["concepts"] = []
            finding["primary_concept"] = None
            finding["affected_concepts"] = []

    return findings


# ---------------------------------------------------------------------------
# Orchestration (Sprint B)
# ---------------------------------------------------------------------------

@dataclass
class ReasoningOutput:
    """Full output of the reasoning engine for one company."""
    ranked_explanations: list
    evidence_chains: list
    unmatched_findings: list[str]
    concept_annotations: dict[str, dict]


def run_reasoning_engine(step6_output: dict) -> ReasoningOutput:
    """Orchestrate the full reasoning pipeline on Step 6 output.

    1. Load canonical concepts, relationships, explanation templates.
    2. Annotate findings with concepts (Sprint A).
    3. Build evidence chains (Sprint B).
    4. Rank explanations (Sprint B).
    5. Return a structured ReasoningOutput.

    This function does NOT modify the step6_output dict.
    """
    import copy
    from pipeline.evidence_chains import build_evidence_chains
    from pipeline.explanation_ranker import rank_explanations

    # Deep-copy findings so we don't mutate the caller's data
    findings = copy.deepcopy(step6_output.get("findings", []))

    # Step 1: load knowledge
    concepts = load_canonical_concepts()
    relationships = load_relationships(concepts=concepts)
    templates = load_explanation_templates()

    # Step 2: annotate findings with concepts
    annotate_findings_with_concepts(findings)

    # Step 3: build evidence chains
    stacked = [f for f in findings if f.get("module") == "stacked"]
    chains, unmatched = build_evidence_chains(findings, stacked, relationships)

    # Step 4: rank explanations
    ranked = rank_explanations(chains, findings, templates)

    # Step 5: build concept annotation summary
    concept_summary: dict[str, dict] = {}
    for f in findings:
        if f.get("module") == "stacked":
            continue
        fid = f.get("id", "")
        if fid:
            concept_summary[fid] = {
                "concepts": f.get("concepts", []),
                "primary_concept": f.get("primary_concept"),
                "affected_concepts": f.get("affected_concepts", []),
            }

    return ReasoningOutput(
        ranked_explanations=ranked,
        evidence_chains=chains,
        unmatched_findings=unmatched,
        concept_annotations=concept_summary,
    )
