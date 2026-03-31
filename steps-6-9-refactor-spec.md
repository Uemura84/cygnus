# Steps 6–9 Refactor — Complete Claude Code Spec

> **What this is:** Complete redesign of the analytical layer (Steps 6–9) of the CVM Demo App.
> The goal: each step adds NEW information or a NEW perspective. No step should
> repackage what the previous step already showed.
>
> **CRITICAL:** Do NOT change any logic inside `pattern_detector.py` or `enrichment.py`.
> The detection algorithms, DQ classification, composite signal engine, and risk scoring
> are validated. You are restructuring how they're called and presented, not what they compute.
>
> **CRITICAL:** Do NOT change Steps 1–5. They are complete and working.

---

## Summary of Changes

| Step | Before | After | Why |
|------|--------|-------|-----|
| 6 | Pattern Detection (findings only) | **Pattern Detection & Risk Assessment** (findings + composites + risk — merged 6+7) | Old Step 7 was just repackaging Step 6's findings |
| 7 | Enrichment (composite signals + risk) | **Hypothesis Generation** (theories + data readiness gap — NEW) | Adds new information: explains *why* patterns exist |
| 8 | Reporting (narrative text) | **Executive Summary** (redesigned: structured narrative + finding hierarchy) | Was a flat text dump; now a structured story |
| 9 | LLM Analysis (Claude elaboration) | **AI Deep Dive** (informed by Step 7 hypotheses — IMPROVED) | Now extends deterministic hypotheses instead of generating blind |

---

## Step 6: Pattern Detection & Risk Assessment (Merge of old Steps 6 + 7)

### Backend

**File:** `backend/steps/step6_core_analysis.py` (rename from `step6_pattern_detection.py`)

The endpoint `POST /api/step/6` now:
1. Reads enriched df from `pipeline_state["step5"]` (unchanged)
2. Calls `pattern_detector.detect_patterns()` — unchanged
3. Calls `enrichment.enrich()` with the findings — unchanged
4. Merges both outputs into a single response
5. Adds a `finding_categories` field that classifies each finding (see below)

**Finding categorization logic** (add to end of step6 before returning):

```python
def categorize_findings(findings: list, composite_signals: list) -> dict:
    """Classify findings into narrative categories for frontend display."""
    structural_types = {
        "STRUCTURAL_COMPETITIVENESS_ISSUE",
        "NEGATIVE_OPERATING_LEVERAGE",
        "COST_INFLATION_PRESSURE",
    }
    has_structural = any(
        cs.get("composite_signal_type") in structural_types
        for cs in composite_signals
    )

    categories = {"core": [], "supporting": [], "contextual": [], "anomalies": []}

    for f in findings:
        fid = f.get("id", "")
        pattern = f.get("pattern", "")
        anomaly_type = f.get("anomaly_type", "")

        if pattern in ("Cost composition drift", "Margin compression"):
            categories["core"].append(fid)
        elif pattern == "Revenue-cost decoupling":
            if (f.get("divergence_pp") or 0) > 0:
                categories["supporting"].append(fid)
            else:
                categories["contextual"].append(fid)
        elif pattern == "Statistical anomaly":
            categories["anomalies"].append(fid)
        elif pattern == "YoY quarter comparison":
            if anomaly_type == "EVENT_DRIVEN_BUT_PLAUSIBLE":
                categories["contextual"].append(fid)
            else:
                categories["supporting"].append(fid)
        elif pattern == "Peer divergence":
            categories["supporting"].append(fid)
        else:
            categories["contextual"].append(fid)

    return categories
```

**Response shape:**

```json
{
  "status": "complete",
  "data": {
    "algorithms_run": ["margin_trends", "cost_composition_drift", "revenue_cost_decoupling",
                       "peer_comparison", "statistical_anomaly", "yoy_quarter_comparison"],
    "raw_findings": 8,
    "findings": [ ... ],
    "finding_categories": {
      "core": ["F001", "F002"],
      "supporting": ["F003", "F005"],
      "contextual": ["F004"],
      "anomalies": ["F006", "F007", "F008"]
    },
    "composite_signals": [ ... ],
    "risk_score": 71.2,
    "risk_level": "HIGH",
    "risk_scores": [ ... ],
    "macro_timeline": [ ... ],
    "findings_enriched": 8,
    "macro_annotations_added": 4
  },
  "metadata": { ... },
  "timing": { ... }
}
```

**Pipeline state:** `pipeline_state["step6"]` now contains EVERYTHING — findings,
enrichment, composites, risk, categories. Steps 7, 8, 9 all read from this.

**Delete:** `backend/steps/step7_enrichment.py` (its logic is now called within step6)

### Frontend

**File:** `frontend/src/steps/Step6CoreAnalysis.jsx` (rename from `Step6PatternDetection.jsx`)

This component now renders ALL analytical output in one view:

**Layout (top to bottom):**

1. **Summary bar** (horizontal strip at top):
   - Total findings count (e.g., "8 findings detected")
   - Risk score gauge (e.g., 71.2 / HIGH) — compact, not full-page
   - Composite signals as badges (e.g., "STRUCTURAL_COMPETITIVENESS_ISSUE", "NEGATIVE_OPERATING_LEVERAGE")

2. **Findings by category** (main content area):
   - Group findings using `finding_categories` from the API response
   - Section headers: "Core Findings" / "Supporting Evidence" / "Macro Context" / "Anomalies"
   - Each finding is a card with severity indicator, description, supporting mini-chart
   - Core findings visually prominent (larger cards, emphasized border)
   - Contextual findings visually de-emphasized (smaller, muted styling)

3. **Macro timeline** (bottom):
   - Horizontal timeline with findings plotted against macro events
   - Same visualization as before, just moved into this combined view

**Delete:** `frontend/src/steps/Step7Enrichment.jsx`

---

## Step 7: Hypothesis Generation (NEW)

### Backend

**New file:** `backend/pipeline/hypothesis_generator.py`

This is a **deterministic, rule-based** module. No LLM calls. It takes structural
findings from Step 6 and generates hypotheses from a domain knowledge map.

```python
"""Hypothesis generator — deterministic theory generation for structural findings.

Maps structural deterioration patterns to possible causes based on sector and
company characteristics. Each hypothesis includes the mechanism, the internal
data source needed to confirm/refute it, and links to supporting findings.

Public API
----------
generate_hypotheses(findings, composite_signals, company, sector) -> dict
    Step 7: generate structured hypotheses for STRUCTURAL findings.
"""

from pipeline.enrichment import SECTOR_MAP

# =============================================================================
# Domain Knowledge Maps
# =============================================================================

# Hypotheses keyed by (sector, finding_pattern).
HYPOTHESIS_MAP = {
    ("Petrochemical", "Cost composition drift"): [
        {
            "id": "H1",
            "theory": "Naphtha feedstock cost disadvantage widening",
            "mechanism": (
                "Primary cracker feedstock is naphtha, which tracks Brent crude oil prices. "
                "Competitors in the US and Middle East use ethane/propane from natural gas, "
                "which has been structurally cheaper since the US shale revolution. "
                "Each oil price spike disproportionately hits naphtha-based producers."
            ),
            "data_needed": "Feedstock cost breakdown within COGS (3.02.x sub-accounts)",
            "data_availability": "Internal only — CVM reports only top-level 3.02 COGS",
            "confidence": "HIGH",
            "tags": ["feedstock", "structural", "external"],
        },
        {
            "id": "H2",
            "theory": "China oversupply compressing product spreads",
            "mechanism": (
                "China added massive petrochemical capacity (new crackers, PE/PP plants) "
                "between 2020-2024, flooding global markets. This compressed product spreads "
                "(selling price minus feedstock cost). COGS ratio rises not because absolute "
                "costs increased, but because selling prices fell under export pressure."
            ),
            "data_needed": "Product-level revenue and volume data (price vs. volume decomposition)",
            "data_availability": "Internal only — CVM reports consolidated revenue",
            "confidence": "HIGH",
            "tags": ["pricing", "structural", "external"],
        },
        {
            "id": "H3",
            "theory": "BRL depreciation inflating USD-denominated input costs",
            "mechanism": (
                "Naphtha and other feedstocks are priced in USD. The BRL weakened from ~R$5.30 "
                "to R$6.00+ against USD over the analysis period. If COGS is partially "
                "USD-denominated but domestic revenue is BRL-denominated, the FX effect alone "
                "pushes the COGS-to-revenue ratio up."
            ),
            "data_needed": "Currency split of COGS (USD vs. BRL components)",
            "data_availability": "Internal only — may be partially disclosed in explanatory notes",
            "confidence": "MEDIUM",
            "tags": ["fx", "structural", "external"],
        },
        {
            "id": "H4",
            "theory": "International operations dragging consolidated results",
            "mechanism": (
                "Braskem consolidated includes non-Brazil operations (Braskem Idesa/Mexico, "
                "US Gulf Coast). If these subsidiaries had cost problems — feedstock supply "
                "issues with Pemex in Mexico are well documented — consolidated COGS ratio "
                "deteriorates even if Brazil operations are stable."
            ),
            "data_needed": "Segment-level P&L (Brazil vs. international operations)",
            "data_availability": "Partially available in CVM segment reporting, full detail internal",
            "confidence": "MEDIUM",
            "tags": ["segment", "structural", "internal"],
        },
        {
            "id": "H5",
            "theory": "Product mix shift toward lower-margin products",
            "mechanism": (
                "If revenue mix shifted toward basic chemicals/commoditized resins (lower "
                "value-add) and away from specialty or differentiated products, gross margin "
                "compresses even with stable production costs per unit."
            ),
            "data_needed": "Revenue by product line with margin contribution",
            "data_availability": "Internal only",
            "confidence": "MEDIUM",
            "tags": ["mix", "structural", "internal"],
        },
        {
            "id": "H6",
            "theory": "Fixed cost absorption declining on lower utilization",
            "mechanism": (
                "Petrochemical plants have high fixed costs (depreciation, maintenance, labor). "
                "If utilization rates dropped — from demand weakness or planned shutdowns — "
                "fixed costs spread over fewer units, pushing per-unit COGS up. "
                "Depreciation flows through the COGS line in the DRE."
            ),
            "data_needed": "Plant utilization rates, production volumes, fixed vs. variable cost split",
            "data_availability": "Internal only — some volume data in quarterly earnings releases",
            "confidence": "MEDIUM",
            "tags": ["utilization", "structural", "internal"],
        },
        {
            "id": "H7",
            "theory": "Asset aging and deferred maintenance escalating costs",
            "mechanism": (
                "Major facilities in Camaçari (BA) and Triunfo (RS) are decades old. "
                "Aging assets require increasing maintenance spend. If CAPEX was deferred "
                "during 2020-2022 (cash constraints), deferred maintenance may now show up "
                "as higher OPEX flowing through COGS."
            ),
            "data_needed": "Maintenance CAPEX vs. OPEX trend, asset age profile",
            "data_availability": "Internal only — CAPEX total available in CVM cash flow statement",
            "confidence": "LOW",
            "tags": ["capex", "structural", "internal"],
        },
    ],

    # Default fallback for non-petrochemical sectors (Phase 2)
    ("_default", "Cost composition drift"): [
        {
            "id": "H1",
            "theory": "Input cost inflation outpacing revenue growth",
            "mechanism": (
                "Raw material or energy costs may have increased faster than the company's "
                "ability to pass through price increases to customers."
            ),
            "data_needed": "COGS sub-account breakdown (materials, labor, overhead, energy)",
            "data_availability": "Internal only",
            "confidence": "HIGH",
            "tags": ["cost", "structural", "external"],
        },
        {
            "id": "H2",
            "theory": "Volume decline causing fixed cost absorption loss",
            "mechanism": (
                "High fixed cost operations lose margin when volumes decline, as fixed costs "
                "spread over fewer units."
            ),
            "data_needed": "Production volumes and utilization rates",
            "data_availability": "Internal only",
            "confidence": "MEDIUM",
            "tags": ["utilization", "structural", "internal"],
        },
        {
            "id": "H3",
            "theory": "Product or customer mix shift",
            "mechanism": (
                "Revenue mix may have shifted toward lower-margin products, customers, or "
                "geographies, compressing overall gross margin."
            ),
            "data_needed": "Revenue by product/customer/geography with margin data",
            "data_availability": "Internal only",
            "confidence": "MEDIUM",
            "tags": ["mix", "structural", "internal"],
        },
    ],

    # Empty entries for Margin compression — same root causes as cost drift
    ("Petrochemical", "Margin compression"): [],
    ("_default", "Margin compression"): [],
}

# Data readiness gap — questions public data raises but can't answer
DATA_READINESS_QUESTIONS = {
    "Petrochemical": [
        {
            "question": "What is the feedstock cost as percentage of total COGS?",
            "source": "3.02.x COGS sub-accounts",
            "availability": "Internal only",
            "priority": "CRITICAL",
        },
        {
            "question": "How do margins differ by product line (PE, PP, PVC, basic chemicals)?",
            "source": "Product-level P&L",
            "availability": "Internal only",
            "priority": "HIGH",
        },
        {
            "question": "What share of COGS is USD-denominated vs. BRL?",
            "source": "Treasury / procurement data",
            "availability": "Internal only",
            "priority": "HIGH",
        },
        {
            "question": "How do Brazil operations perform vs. international (Mexico, US)?",
            "source": "Segment-level financial statements",
            "availability": "Partially in CVM filings, full detail internal",
            "priority": "HIGH",
        },
        {
            "question": "What are current plant utilization rates?",
            "source": "Operations / production reports",
            "availability": "Internal only, some in earnings releases",
            "priority": "MEDIUM",
        },
        {
            "question": "What is the maintenance CAPEX vs. OPEX split trend?",
            "source": "Asset management / engineering",
            "availability": "Internal only",
            "priority": "MEDIUM",
        },
    ],
    "_default": [
        {
            "question": "What is the breakdown of COGS by major category?",
            "source": "3.02.x COGS sub-accounts",
            "availability": "Internal only",
            "priority": "CRITICAL",
        },
        {
            "question": "How do margins vary across product lines or business segments?",
            "source": "Segment-level P&L",
            "availability": "Internal only",
            "priority": "HIGH",
        },
        {
            "question": "What are current capacity utilization rates?",
            "source": "Operations data",
            "availability": "Internal only",
            "priority": "MEDIUM",
        },
    ],
}


# =============================================================================
# Public API
# =============================================================================

def _get_sector(company_name: str) -> str:
    """Determine sector from company name."""
    for fragment, sector in SECTOR_MAP.items():
        if fragment.upper() in company_name.upper():
            return sector
    return "_default"


def _find_supporting(hypothesis: dict, findings: list) -> list:
    """Find finding IDs that support a hypothesis based on tag matching."""
    supporting = []
    tags = set(hypothesis.get("tags", []))

    for f in findings:
        fid = f.get("id", "")
        pattern = f.get("pattern", "")

        if ("cost" in tags or "feedstock" in tags) and pattern in ("Cost composition drift", "Revenue-cost decoupling"):
            supporting.append(fid)
        if "pricing" in tags and pattern in ("Margin compression", "Revenue-cost decoupling"):
            supporting.append(fid)
        if "fx" in tags and pattern == "Cost composition drift":
            supporting.append(fid)
        if "utilization" in tags and pattern == "Revenue-cost decoupling" and (f.get("divergence_pp") or 0) > 0:
            supporting.append(fid)
        if "mix" in tags and pattern == "Margin compression":
            supporting.append(fid)

    return list(dict.fromkeys(supporting))  # dedupe preserving order


def generate_hypotheses(
    findings: list,
    composite_signals: list,
    company: str,
    sector: str | None = None,
) -> dict:
    """Generate structured hypotheses for structural findings.

    Returns:
        {
            "company": str,
            "sector": str,
            "primary_finding": { id, pattern, description, magnitude },
            "hypotheses": [ { id, theory, mechanism, data_needed, data_availability,
                              confidence, supporting_findings } ],
            "hypothesis_count": int,
            "data_readiness_gap": [ { question, source, availability, priority } ],
        }
    """
    if sector is None:
        sector = _get_sector(company)

    # Find the primary structural finding (largest COGS drift or margin compression)
    structural = [
        f for f in findings
        if f.get("pattern") in ("Cost composition drift", "Margin compression")
        and f.get("severity") in ("HIGH", "CRITICAL")
    ]
    structural.sort(
        key=lambda f: abs(f.get("shift_pp") or f.get("annual_change_pp") or 0),
        reverse=True,
    )
    primary = structural[0] if structural else None

    # Build hypotheses from knowledge map
    hypotheses = []
    seen = set()

    if primary:
        pattern = primary.get("pattern", "")
        key = (sector, pattern)
        sector_hyps = HYPOTHESIS_MAP.get(key, [])
        if not sector_hyps:
            key = ("_default", pattern)
            sector_hyps = HYPOTHESIS_MAP.get(key, [])

        for h in sector_hyps:
            if h["theory"] not in seen:
                hyp = dict(h)
                hyp["supporting_findings"] = _find_supporting(h, findings)
                hypotheses.append(hyp)
                seen.add(h["theory"])

    # Also pull from Cost composition drift if primary was Margin compression
    if primary and primary.get("pattern") == "Margin compression":
        key2 = (sector, "Cost composition drift")
        for h in HYPOTHESIS_MAP.get(key2, []):
            if h["theory"] not in seen:
                hyp = dict(h)
                hyp["supporting_findings"] = _find_supporting(h, findings)
                hypotheses.append(hyp)
                seen.add(h["theory"])

    # Check composite signals for NEGATIVE_OPERATING_LEVERAGE — emphasize utilization hypotheses
    for cs in composite_signals:
        if cs.get("composite_signal_type") == "NEGATIVE_OPERATING_LEVERAGE":
            for h in HYPOTHESIS_MAP.get((sector, "Cost composition drift"), []):
                if h["theory"] not in seen and "utilization" in h.get("tags", []):
                    hyp = dict(h)
                    hyp["supporting_findings"] = _find_supporting(h, findings)
                    hypotheses.append(hyp)
                    seen.add(h["theory"])

    # Data readiness gap
    drg = DATA_READINESS_QUESTIONS.get(sector, DATA_READINESS_QUESTIONS["_default"])

    return {
        "company": company,
        "sector": sector,
        "primary_finding": {
            "id": primary.get("id", "F001") if primary else None,
            "pattern": primary.get("pattern") if primary else None,
            "description": primary.get("description") or primary.get("insight") if primary else None,
            "magnitude": (
                f"+{primary.get('shift_pp', 0):.1f}pp COGS drift"
                if primary and primary.get("shift_pp")
                else f"{primary.get('annual_change_pp', 0):.1f}pp/year compression"
                if primary and primary.get("annual_change_pp")
                else None
            ),
        },
        "hypotheses": hypotheses,
        "hypothesis_count": len(hypotheses),
        "data_readiness_gap": drg,
    }
```

### New file: `backend/steps/step7_hypotheses.py`

```python
"""Step 7 endpoint — Hypothesis Generation."""

from pipeline.hypothesis_generator import generate_hypotheses
from config import pipeline_state, get_config
from cache_utils import load_cache, save_cache


def run(use_cache: bool = False) -> dict:
    if use_cache:
        cached = load_cache(7)
        if cached:
            return cached

    step6 = pipeline_state.get("step6", {}).get("data", {})
    findings = step6.get("findings", [])
    composite_signals = step6.get("composite_signals", [])

    config = get_config()

    try:
        result = generate_hypotheses(
            findings=findings,
            composite_signals=composite_signals,
            company=config.company_name,
        )
        save_cache(7, result)
        return result
    except Exception as e:
        cached = load_cache(7)
        if cached:
            cached["_metadata"] = {"source": "cache", "reason": str(e)}
            return cached
        raise
```

### Frontend: `frontend/src/steps/Step7Hypotheses.jsx`

**Layout (top to bottom):**

1. **Primary finding banner** — full-width card showing the main structural finding:
   - Pattern name + magnitude (e.g., "COGS burden shifted +16.8pp over 5 years")
   - Brief description

2. **Hypotheses section** — the 7 theories, each as an expandable card:
   - **Collapsed state:** Theory name + confidence badge + one-line summary
   - **Expanded state:** Full mechanism explanation + data needed + data availability tag + supporting findings list
   - Confidence color coding: HIGH = green, MEDIUM = yellow, LOW = gray
   - Data availability color coding: "Internal only" = orange, "Partially available" = yellow
   - Cards are expandable/collapsible (first 3 expanded by default)

3. **Data Readiness Gap table** — the bridge to the consulting offer:

   | Question | Data Source | Availability | Priority |
   |----------|------------|--------------|----------|
   | What is the feedstock cost as % of COGS? | 3.02.x sub-accounts | Internal only | CRITICAL |
   | ... | ... | ... | ... |

   This table should be visually prominent — it's the most important element for
   the consulting conversation. Use color for priority (CRITICAL = red, HIGH = orange,
   MEDIUM = yellow).

**Design intent:** This step should feel like the analysis transitioning from
"what we found" to "what we'd investigate next with your internal data." It's the
bridge to the offer.

---

## Step 8: Executive Summary (Redesigned)

### Backend

**File:** `backend/steps/step8_reporting.py` (update existing)

The current Step 8 generates a narrative string, key findings summary, and data
limitations. Keep this but restructure the output to be more useful for the frontend.

Read from `pipeline_state["step6"]` (findings, composites, risk) AND
`pipeline_state["step7"]` (hypotheses, data readiness gap).

**Updated response shape:**

```json
{
  "status": "complete",
  "data": {
    "headline": "Braskem shows structural COGS deterioration: 75% → 92% over 5 years, EBIT now negative",
    "narrative": "... (existing narrative string, kept as-is) ...",
    "story_arc": {
      "setup": "Between 2020 and 2025, Braskem's cost structure deteriorated significantly...",
      "evidence": "COGS as a percentage of revenue shifted from 75.2% to 92.1%...",
      "inflection": "The critical inflection came in 2022, when revenue fell 8.6% but COGS rose 15.8%...",
      "implication": "At current trajectory, COGS will exceed revenue within 2-3 years...",
      "question": "Seven hypotheses could explain this deterioration, but confirming which requires internal data that public filings don't provide..."
    },
    "key_findings_summary": [
      { "rank": 1, "id": "F001", "category": "core", "finding": "Structural COGS deterioration", "evidence": "75.2% → 92.1% (+16.8pp)" },
      { "rank": 2, "id": "F003", "category": "supporting", "finding": "Negative operating leverage in 2022", "evidence": "Revenue -8.6%, COGS +15.8%" },
      { "rank": 3, "id": "F002", "category": "core", "finding": "Margin compression trend", "evidence": "-4.9pp/year, currently 7.8%" }
    ],
    "data_limitations": [
      "No COGS sub-account breakdown (3.02.x) — only top-level COGS available in CVM structured data",
      "Quarterly granularity only — monthly patterns invisible",
      "Consolidated view — subsidiary-level patterns hidden",
      "No operational KPIs — production volumes, utilization rates unavailable",
      "No product-line profitability — revenue reported at aggregate level"
    ],
    "transition_to_offer": "This analysis identified a structural COGS deterioration of 16.8pp and generated 7 hypotheses for its root cause. Confirming which hypotheses apply requires access to internal data behind the 3.02 COGS line — feedstock costs, product margins, segment P&L, and utilization rates."
  }
}
```

**The `story_arc` is new.** It structures the narrative into a five-part story
(setup → evidence → inflection → implication → question) that the presenter can
follow as a talk track. The logic to generate this:

```python
def build_story_arc(findings, composites, hypotheses_data):
    """Build a structured narrative arc from analysis results."""

    # Find key data points from findings
    cogs_drift = next((f for f in findings if f.get("pattern") == "Cost composition drift"), None)
    margin_comp = next((f for f in findings if f.get("pattern") == "Margin compression" and "Gross" in f.get("metric", "")), None)
    worst_decoupling = next((f for f in findings
                             if f.get("pattern") == "Revenue-cost decoupling"
                             and (f.get("divergence_pp") or 0) > 0), None)

    first_half = cogs_drift.get("first_half_avg", "N/A") if cogs_drift else "N/A"
    second_half = cogs_drift.get("second_half_avg", "N/A") if cogs_drift else "N/A"
    shift = cogs_drift.get("shift_pp", 0) if cogs_drift else 0
    annual_chg = margin_comp.get("annual_change_pp", 0) if margin_comp else 0
    current_margin = margin_comp.get("current_level", "N/A") if margin_comp else "N/A"

    h_count = hypotheses_data.get("hypothesis_count", 0) if hypotheses_data else 0

    setup = (
        f"Between 2020 and 2025, the company's cost structure deteriorated significantly. "
        f"COGS as a percentage of revenue shifted from {first_half:.1f}% to {second_half:.1f}%, "
        f"a {abs(shift):.1f} percentage point increase."
    )
    evidence = (
        f"Gross margin compressed at {abs(annual_chg):.1f}pp per year, "
        f"reaching {current_margin}% — approaching the viability floor for "
        f"capital-intensive manufacturing."
    )

    if worst_decoupling:
        period = worst_decoupling.get("period", "")
        rev_chg = worst_decoupling.get("revenue_change_pct", 0)
        cogs_chg = worst_decoupling.get("cogs_change_pct", 0)
        inflection = (
            f"The critical inflection came in {period}, when revenue fell {abs(rev_chg):.1f}% "
            f"but COGS rose {cogs_chg:.1f}%. Costs did not normalize when revenue recovered — "
            f"indicating a structural shift, not a cyclical one."
        )
    else:
        inflection = "The deterioration has been persistent across periods, without recovery."

    implication = (
        f"At the current compression rate of {abs(annual_chg):.1f}pp per year, "
        f"operating margins will continue eroding unless the underlying cost drivers are addressed."
    )

    question = (
        f"{h_count} hypotheses could explain this deterioration, but confirming which "
        f"requires internal data that public filings do not provide — specifically, "
        f"the decomposition of the COGS line into feedstock, energy, labor, and overhead components."
    )

    return {
        "setup": setup,
        "evidence": evidence,
        "inflection": inflection,
        "implication": implication,
        "question": question,
    }
```

**The `transition_to_offer` field is new.** It's a one-paragraph bridge from
the analysis to the consulting conversation. The frontend renders it as a
highlighted callout at the bottom of Step 8.

### Frontend: `frontend/src/steps/Step8Summary.jsx` (rename from `Step8Reporting.jsx`)

**Layout (top to bottom):**

1. **Headline** — large text, bold, one line summarizing the entire analysis
   (e.g., "Braskem: Structural COGS Deterioration — 75% → 92% Over 5 Years")

2. **Story arc** — five sections rendered as a vertical flow/timeline:
   - Setup (what happened)
   - Evidence (how bad it is)
   - Inflection (when things turned)
   - Implication (what comes next)
   - Question (what we can't answer with public data)
   Each section is a card with a label and 2-3 sentences.

3. **Key findings table** — top 3-5 findings ranked, with category badge
   (Core / Supporting), and one-line evidence

4. **Transition callout** — highlighted box (light blue or light yellow background)
   with the `transition_to_offer` text. This is the last thing the audience reads
   before Step 9.

5. **Data limitations** — collapsible section (default collapsed), listing the 5
   limitations for reference

**Design intent:** Step 8 is the "so what" moment. The audience should come away
understanding: (1) there's a real structural problem, (2) public data proves it
exists but can't explain it, (3) internal data is the next step.

---

## Step 9: AI Deep Dive (Improved)

### Backend

**File:** `backend/steps/step9_llm_analysis.py` (update existing)

Two changes:

1. **Include top-3 hypotheses in the prompt context.** When the user selects a
   finding for LLM analysis, the WebSocket message now includes hypotheses from
   Step 7 (read from `pipeline_state["step7"]`).

2. **Updated system prompt and user prompt.**

**System prompt:**

```
You are a senior financial analyst examining public financial data from Brazilian
companies filed with the CVM (Securities Commission). You have expertise in
petrochemical industry economics, cost structure analysis, and EBITDA driver
decomposition.

Your task: Given a specific analytical finding and its supporting data, generate
additional theories and analytical angles that could explain the pattern.

You have been provided with structured hypotheses already generated by the
analytical pipeline. BUILD ON THESE — do not repeat them. Instead:
1. Identify 2-3 ADDITIONAL theories the pipeline may have missed
2. For each theory, explain the specific mechanism and what data would confirm it
3. Highlight which of the provided hypotheses you consider most likely and why
4. Suggest specific analytical next steps

Be specific and quantitative. Reference the actual numbers from the finding.
Write in the language specified ({language}).
```

**User prompt template:**

```
## Finding
{finding_description}

## Supporting Data
{finding_data_points as formatted key-value pairs}

## Macro Context
{macro_context if available}

## Existing Hypotheses (from analytical pipeline)
{top 3 hypotheses from Step 7, formatted as:
- H1: {theory} — {one-line mechanism}
- H2: {theory} — {one-line mechanism}
- H3: {theory} — {one-line mechanism}}

## Company Context
Company: {company_name}
Sector: {sector}
Analysis period: {date_range}

Generate your analysis.
```

**Key design decision:** Only include the TOP 3 hypotheses by confidence in the
prompt (not all 7). This leaves room for the LLM to contribute novel theories
while being informed by the deterministic analysis.

**Fallback behavior:** If `pipeline_state["step7"]` is empty (Step 7 wasn't run),
omit the "Existing Hypotheses" section and fall back to current behavior.

### Frontend: `frontend/src/steps/Step9LLMAnalysis.jsx` (update existing)

Mostly unchanged, but add:

1. **Hypothesis context indicator** — small text above the streaming response:
   "AI analysis informed by 7 structured hypotheses from Step 7"
   (or "AI analysis without hypothesis context" if Step 7 wasn't run)

2. **Finding selector** should show finding category badges (Core / Supporting / etc.)
   next to each finding in the dropdown, so the presenter can quickly pick a
   core finding.

3. After streaming completes, show a subtle divider and text:
   "Domain expert interpretation follows..." — this is the cue for the presenter
   to add verbal commentary.

---

## i18n Keys (all new/updated)

### English (`frontend/src/i18n/en.json`)

```json
{
  "step6": {
    "title": "Pattern Detection & Risk Assessment",
    "description": "Running 6 detection algorithms, building composite signals, and scoring risk",
    "running": "Analyzing patterns...",
    "findings_detected": "findings detected",
    "risk_score": "Risk Score",
    "composite_signals": "Composite Signals",
    "core_findings": "Core Findings",
    "supporting_evidence": "Supporting Evidence",
    "macro_context": "Macro Context",
    "anomalies": "Anomalies"
  },
  "step7": {
    "title": "Hypothesis Generation",
    "description": "Generating theories for structural findings and mapping to internal data sources",
    "running": "Generating hypotheses...",
    "primary_finding": "Primary Finding",
    "hypotheses": "Possible Theories",
    "data_readiness": "Data Readiness Gap",
    "data_needed": "Data Needed",
    "data_availability": "Availability",
    "internal_only": "Internal Only",
    "partially_available": "Partially Available",
    "confidence": "Confidence",
    "supporting_findings": "Supported by"
  },
  "step8": {
    "title": "Executive Summary",
    "description": "Synthesizing findings into a structured narrative",
    "running": "Building narrative...",
    "headline": "Headline",
    "story_setup": "What Happened",
    "story_evidence": "How Serious It Is",
    "story_inflection": "When Things Turned",
    "story_implication": "What Comes Next",
    "story_question": "What We Can't Answer",
    "key_findings": "Key Findings",
    "data_limitations": "Data Limitations",
    "transition": "Next Step"
  },
  "step9": {
    "title": "AI Deep Dive",
    "description": "AI-powered analysis of individual findings with hypothesis context",
    "running": "Streaming AI analysis...",
    "select_finding": "Select a finding to analyze",
    "hypothesis_context": "AI analysis informed by {count} structured hypotheses",
    "no_hypothesis_context": "AI analysis without hypothesis context",
    "expert_cue": "Domain expert interpretation follows..."
  }
}
```

### Portuguese (`frontend/src/i18n/pt-br.json`)

```json
{
  "step6": {
    "title": "Detecção de Padrões e Avaliação de Risco",
    "description": "Executando 6 algoritmos de detecção, construindo sinais compostos e pontuando risco",
    "running": "Analisando padrões...",
    "findings_detected": "achados detectados",
    "risk_score": "Pontuação de Risco",
    "composite_signals": "Sinais Compostos",
    "core_findings": "Achados Centrais",
    "supporting_evidence": "Evidências de Suporte",
    "macro_context": "Contexto Macroeconômico",
    "anomalies": "Anomalias"
  },
  "step7": {
    "title": "Geração de Hipóteses",
    "description": "Gerando teorias para achados estruturais e mapeando para fontes de dados internas",
    "running": "Gerando hipóteses...",
    "primary_finding": "Achado Principal",
    "hypotheses": "Teorias Possíveis",
    "data_readiness": "Gap de Prontidão de Dados",
    "data_needed": "Dados Necessários",
    "data_availability": "Disponibilidade",
    "internal_only": "Apenas Interno",
    "partially_available": "Parcialmente Disponível",
    "confidence": "Confiança",
    "supporting_findings": "Suportado por"
  },
  "step8": {
    "title": "Sumário Executivo",
    "description": "Sintetizando achados em uma narrativa estruturada",
    "running": "Construindo narrativa...",
    "headline": "Manchete",
    "story_setup": "O Que Aconteceu",
    "story_evidence": "Qual a Gravidade",
    "story_inflection": "Quando Mudou",
    "story_implication": "O Que Vem a Seguir",
    "story_question": "O Que Não Podemos Responder",
    "key_findings": "Principais Achados",
    "data_limitations": "Limitações dos Dados",
    "transition": "Próximo Passo"
  },
  "step9": {
    "title": "Análise Aprofundada com IA",
    "description": "Análise com IA de achados individuais com contexto de hipóteses",
    "running": "Transmitindo análise de IA...",
    "select_finding": "Selecione um achado para analisar",
    "hypothesis_context": "Análise de IA informada por {count} hipóteses estruturadas",
    "no_hypothesis_context": "Análise de IA sem contexto de hipóteses",
    "expert_cue": "Interpretação do especialista de domínio a seguir..."
  }
}
```

---

## Backend i18n (`backend/i18n/en.json` and `backend/i18n/pt_br.json`)

Update step labels to match:

```json
{
  "step6_name": "Pattern Detection & Risk Assessment",
  "step7_name": "Hypothesis Generation",
  "step8_name": "Executive Summary",
  "step9_name": "AI Deep Dive"
}
```

Portuguese:
```json
{
  "step6_name": "Detecção de Padrões e Avaliação de Risco",
  "step7_name": "Geração de Hipóteses",
  "step8_name": "Sumário Executivo",
  "step9_name": "Análise Aprofundada com IA"
}
```

---

## Routing Changes (`backend/main.py`)

```
POST /api/step/6  →  step6_core_analysis.run()      # was step6_pattern_detection
POST /api/step/7  →  step7_hypotheses.run()          # was step7_enrichment
POST /api/step/8  →  step8_reporting.run()           # same file, updated logic
WS   /ws/llm      →  step9_llm_analysis.stream()    # same endpoint, updated prompt
```

Pipeline state keys:
- `pipeline_state["step6"]` = findings + enrichment + composites + risk + categories
- `pipeline_state["step7"]` = hypotheses + data readiness gap
- `pipeline_state["step8"]` = narrative + story arc + transition
- Step 9 reads from steps 6 + 7 at runtime

---

## Files to Delete

- `backend/steps/step7_enrichment.py` (logic absorbed into step6)
- `frontend/src/steps/Step7Enrichment.jsx` (replaced by Step7Hypotheses.jsx)

---

## Files to Create

- `backend/pipeline/hypothesis_generator.py` (full code provided above)
- `backend/steps/step7_hypotheses.py` (full code provided above)
- `frontend/src/steps/Step7Hypotheses.jsx` (layout described above)

---

## Files to Modify

- `backend/steps/step6_pattern_detection.py` → rename to `step6_core_analysis.py`, add enrichment call + categorization
- `backend/steps/step8_reporting.py` → add story_arc + transition_to_offer + read from step7
- `backend/steps/step9_llm_analysis.py` → add hypothesis context to prompt
- `backend/main.py` → update routing and imports
- `frontend/src/steps/Step6PatternDetection.jsx` → rename + merge enrichment UI
- `frontend/src/steps/Step8Reporting.jsx` → rename to Step8Summary.jsx, redesign layout
- `frontend/src/steps/Step9LLMAnalysis.jsx` → add hypothesis indicator + finding categories
- `frontend/src/components/StepSidebar.jsx` → update step labels
- `frontend/src/components/StepContent.jsx` → update step component mapping
- All i18n files (en.json, pt-br.json, both frontend and backend)

---

## Verification Checklist

- [ ] Step 6 produces same 8 findings + same 2 composite signals + same 71.2 risk score as before
- [ ] Step 6 additionally returns `finding_categories` with core/supporting/contextual/anomalies
- [ ] Step 7 produces 7 hypotheses for Braskem, each with mechanism + data_needed + supporting_findings
- [ ] Step 7 produces 6 data readiness gap questions
- [ ] Step 8 produces a story_arc with 5 parts (setup/evidence/inflection/implication/question)
- [ ] Step 8 produces a transition_to_offer string
- [ ] Step 9 WebSocket prompt includes top-3 hypotheses from Step 7
- [ ] Step 9 falls back gracefully if Step 7 wasn't run
- [ ] All i18n keys present in both EN and PT-BR
- [ ] Frontend renders all 9 steps without errors
- [ ] Cache files regenerated for steps 6-8
- [ ] Old Step 7 enrichment files deleted
