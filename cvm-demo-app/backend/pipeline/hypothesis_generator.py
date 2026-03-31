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

    ("Petrochemical", "Margin compression"): [],
    ("_default", "Margin compression"): [],
}

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
    for fragment, sector in SECTOR_MAP.items():
        if fragment.upper() in company_name.upper():
            return sector
    return "_default"


def _find_supporting(hypothesis: dict, findings: list) -> list:
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

    return list(dict.fromkeys(supporting))


def generate_hypotheses(
    findings: list,
    composite_signals: list,
    company: str,
    sector: str | None = None,
) -> dict:
    """Generate structured hypotheses for structural findings."""
    if sector is None:
        sector = _get_sector(company)

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

    if primary and primary.get("pattern") == "Margin compression":
        key2 = (sector, "Cost composition drift")
        for h in HYPOTHESIS_MAP.get(key2, []):
            if h["theory"] not in seen:
                hyp = dict(h)
                hyp["supporting_findings"] = _find_supporting(h, findings)
                hypotheses.append(hyp)
                seen.add(h["theory"])

    for cs in composite_signals:
        if cs.get("composite_signal_type") == "NEGATIVE_OPERATING_LEVERAGE":
            for h in HYPOTHESIS_MAP.get((sector, "Cost composition drift"), []):
                if h["theory"] not in seen and "utilization" in h.get("tags", []):
                    hyp = dict(h)
                    hyp["supporting_findings"] = _find_supporting(h, findings)
                    hypotheses.append(hyp)
                    seen.add(h["theory"])

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
