"""
Pattern Discovery — EBITDA Driver Decomposition
=================================================
Analyzes structured financial data to surface hidden patterns
that finance teams typically miss. This is the core methodology
for the "Discover" layer.

Patterns we look for:
1. Margin compression/expansion trends (annual data)
2. Cost composition drift (annual data)
3. Revenue-cost decoupling (annual data)
4. Cross-company divergence within the same sector
5. Anomalous quarters (statistical outliers, quarterly data)
6. YoY same-quarter comparison to control for seasonality

Usage:
    python 02_pattern_discovery.py

Requires: output from 01_download_and_parse.py
"""

import json
import pandas as pd
import numpy as np
from collections import defaultdict
from pathlib import Path
from datetime import datetime

ANALYSIS_DIR = Path("data/analysis")
PROCESSED_DIR = Path("data/processed")
OUTPUT_DIR = Path("data/findings")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Sector map for peer comparison — only companies in the same sector are compared.
# Keys are uppercase name fragments matching DENOM_CIA values.
SECTOR_MAP = {
    "BRASKEM":   "Petrochemical",
    "UNIPAR":    "Petrochemical",
    "ELEKEIROZ": "Petrochemical",
    "SUZANO":    "Pulp & Paper",
    "GERDAU":    "Steel",
    "VALE":      "Mining",
}

# Macro context lookup — maps year-halves to key economic events.
# Appended to period-specific finding insights to give readers immediate context.
MACRO_CONTEXT = {
    "2020-H1": "COVID-19 demand collapse — industrial output down globally",
    "2020-H2": "COVID recovery — fiscal stimulus, demand rebound in China",
    "2021-H1": "Post-COVID demand surge — commodity supercycle begins",
    "2021-H2": "Commodity supercycle peak — naphtha/ethylene at multi-year highs",
    "2022-H1": "Ukraine war — energy spike, Brent >$100/bbl; naphtha cost surge",
    "2022-H2": "Global tightening cycle — Fed raises 400bps, demand destruction begins",
    "2023-H1": "Post-war normalization — petrochemical margins under China oversupply pressure",
    "2023-H2": "China restart — polyethylene/PVC export pressure intensifies",
    "2024-H1": "Fiscal uncertainty — BRL weakness adds import cost pressure",
    "2024-H2": "Commodity cycle trough — petrochemical spreads at cycle lows",
    "2025-H1": "Potential recovery — monitor spread recovery and demand rebound signals",
}


def _get_macro_context(period_str: str) -> str:
    """Return macro context for a period string ('Q3 2022' or '2022-09-30')."""
    try:
        if period_str and 'Q' in str(period_str):
            parts = str(period_str).split()
            year    = int(parts[1])
            quarter = int(parts[0][1:])
            half = 'H1' if quarter <= 2 else 'H2'
        else:
            dt   = pd.to_datetime(period_str)
            year = dt.year
            half = 'H1' if dt.month <= 6 else 'H2'
        return MACRO_CONTEXT.get(f"{year}-{half}", '')
    except Exception:
        return ''


# =============================================================================
# Data Quality Layer
# =============================================================================

# Plausibility thresholds for industrial/petrochemical sectors
PLAUSIBILITY_THRESHOLDS = {
    'Gross_Margin_pct':  (-50.0,  80.0),
    'EBIT_Margin_pct':   (-50.0,  60.0),
    'COGS_pct_Revenue':  ( 20.0, 130.0),
    'SGA_pct_Revenue':   (  0.0,  40.0),
}


def validate_metric_ranges(df: pd.DataFrame) -> pd.DataFrame:
    """Add plausibility flag columns to df.

    Adds:
      - _plausibility_flags: semicolon-separated issues string (empty if clean)
      - _has_plausibility_issue: bool
    """
    df = df.copy()
    flags_list = []
    for _, row in df.iterrows():
        issues = []
        for metric, (lo, hi) in PLAUSIBILITY_THRESHOLDS.items():
            if metric not in df.columns:
                continue
            val = row.get(metric)
            if pd.isna(val):
                continue
            if val < lo or val > hi:
                issues.append(f"{metric}={val:.1f} outside [{lo},{hi}]")
        flags_list.append(';'.join(issues))
    df['_plausibility_flags'] = flags_list
    df['_has_plausibility_issue'] = df['_plausibility_flags'].apply(lambda x: x != '')
    return df


def classify_anomaly_type(
    value: float,
    metric: str,
    normal_low: float,
    normal_high: float,
    is_standalone: bool = True,
    has_peer_confirmation: bool = False,
    adjacent_periods_anomalous: bool = False,
) -> str:
    """Classify anomaly type for data quality purposes.

    Returns one of:
      'DATA_ISSUE', 'ACCOUNTING_EVENT', 'EVENT_DRIVEN_BUT_PLAUSIBLE',
      'LOW_CONFIDENCE_SIGNAL', 'VALID_SIGNAL'

    Rules (applied in priority order):
      1. Non-standalone row with implausible value → DATA_ISSUE (always wins;
         non-standalone = YTD cumulative artifact, implausible = pipeline error)
      2. Adjacent periods also anomalous → VALID_SIGNAL (persistent structural shift;
         takes precedence over single-period plausibility concern)
      3. Peer confirmation in same period → EVENT_DRIVEN_BUT_PLAUSIBLE (industry-wide
         event; takes precedence over isolated one-time accounting concern)
      4. Standalone row with implausible value → ACCOUNTING_EVENT (possible one-time item)
      5. Isolated, within plausibility range, no confirmation → LOW_CONFIDENCE_SIGNAL
    """
    thresholds = PLAUSIBILITY_THRESHOLDS.get(metric)
    outside_range = False
    if thresholds is not None:
        lo, hi = thresholds
        outside_range = (value < lo or value > hi)

    # Rule 1: non-standalone + outside plausibility → almost certainly a data pipeline issue
    if outside_range and not is_standalone:
        return 'DATA_ISSUE'

    # Rule 2: adjacent periods also anomalous → persistent structural pattern, regardless of
    # whether the individual value is plausible
    if adjacent_periods_anomalous:
        return 'VALID_SIGNAL'

    # Rule 3: peer confirmation → likely industry-wide event
    if has_peer_confirmation:
        return 'EVENT_DRIVEN_BUT_PLAUSIBLE'

    # Rule 4: standalone row outside plausibility → possible one-time accounting item
    if outside_range:
        return 'ACCOUNTING_EVENT'

    # Rule 5: isolated, within plausibility range, no confirmation
    return 'LOW_CONFIDENCE_SIGNAL'


# Backward-compat alias (kept for existing tests and external callers)
classify_anomaly_type_dq = classify_anomaly_type


def assign_data_confidence(df: pd.DataFrame) -> pd.DataFrame:
    """Add _row_confidence column based on plausibility issues.

    Calls validate_metric_ranges if not already done.
    Returns enriched df.
    """
    if '_has_plausibility_issue' not in df.columns:
        df = validate_metric_ranges(df)

    # Determine standalone: use is_standalone column if present, else assume True
    if 'is_standalone' in df.columns:
        is_standalone_series = df['is_standalone'].fillna(True).astype(bool)
    else:
        is_standalone_series = pd.Series([True] * len(df), index=df.index)

    def _conf(row, is_standalone):
        if not row['_has_plausibility_issue']:
            return 'HIGH'
        if is_standalone:
            return 'MEDIUM'
        return 'LOW'

    df = df.copy()
    df['_row_confidence'] = [
        _conf(row, is_standalone_series.iloc[i])
        for i, (_, row) in enumerate(df.iterrows())
    ]
    return df


# =============================================================================
# Composite Signal Engine
# =============================================================================

# Maps legacy anomaly_type strings (written before the unified DQ taxonomy) to their
# current equivalents. Used by normalize_findings() for backward compatibility.
_LEGACY_ANOMALY_TYPE_MAP: dict = {
    'likely_data_artifact':    'DATA_ISSUE',
    'likely_structural_shift': 'VALID_SIGNAL',
    'likely_one_time_event':   'LOW_CONFIDENCE_SIGNAL',
}


def normalize_findings(findings: list) -> list:
    """Return a normalized, filtered copy of findings for composite signal building.

    Performs two transformations:
    1. Filters out SUMMARY-severity findings and Company Narrative entries —
       these are meta-findings and should not drive composite signal rules.
    2. Migrates legacy anomaly_type strings (pre-DQ-layer taxonomy) to the
       current unified DQ taxonomy so that composite rules work correctly
       regardless of which pipeline version generated the data.

    Does NOT modify the original list or any of its dicts.
    """
    normalized = []
    for f in findings:
        if f.get('severity') == 'SUMMARY' or f.get('pattern') == 'Company Narrative':
            continue
        norm = dict(f)
        legacy = _LEGACY_ANOMALY_TYPE_MAP.get(norm.get('anomaly_type', ''))
        if legacy:
            norm['anomaly_type'] = legacy
        normalized.append(norm)
    return normalized


def _compute_composite_confidence(base_confidence: str, supporting_findings: list) -> str:
    """Downgrade composite confidence based on supporting findings' data quality.

    Rules (applied in priority order):
    - If ALL supporting findings have confidence_score 'LOW' → return 'LOW'
    - If more than half have confidence_score 'LOW' → cap at 'MEDIUM'
      (downgrade 'HIGH' → 'MEDIUM'; 'MEDIUM' stays 'MEDIUM')
    - Otherwise → return base_confidence unchanged

    Propagates the DQ layer's per-finding confidence up to the composite level,
    so that signals built entirely on low-quality data are clearly flagged.
    """
    if not supporting_findings:
        return base_confidence
    scores = [f.get('confidence_score', 'MEDIUM') for f in supporting_findings]
    low_count = sum(1 for s in scores if s == 'LOW')
    if low_count == len(scores):
        return 'LOW'
    if low_count > len(scores) / 2:
        return 'MEDIUM' if base_confidence == 'HIGH' else base_confidence
    return base_confidence


def explain_composite_signal(
    signal_type: str,
    company: str,
    supporting_findings: list,
    sector_context: dict = None,
) -> tuple:
    """Generate (explanation, recommended_investigation_angle) for a composite signal.

    Args:
        signal_type: One of the 8 composite signal type values.
        company: Company name for grammatical subjects in the explanation.
        supporting_findings: Raw findings that triggered this composite signal.
        sector_context (optional): Sector-level data dict:
            - 'peers_with_compression': int  (# peers with margin compression)
            - 'n_peers': int  (total companies in analysis)

    Returns:
        Tuple of (explanation: str, recommended_investigation_angle: str),
        both plain-language strings suitable for the markdown report.
    """
    ctx = sector_context or {}

    if signal_type == 'STRUCTURAL_COMPETITIVENESS_ISSUE':
        drift = [f for f in supporting_findings if f.get('pattern') == 'Cost composition drift']
        comp  = [f for f in supporting_findings if f.get('pattern') == 'Margin compression']
        shift_pp   = max((f.get('shift_pp', 0) or 0 for f in drift), default=0)
        annual_chg = min((f.get('annual_change_pp', 0) or 0 for f in comp), default=0)
        return (
            f"{company} shows rising COGS burden (+{shift_pp:.1f}pp shift) "
            f"alongside margin compression ({annual_chg:.1f}pp/year). "
            f"The simultaneous cost increase and margin deterioration points to a "
            f"structural competitiveness problem rather than a one-time event.",
            "Benchmark cost structure vs peers at sub-account level. "
            "Decompose COGS into raw materials, labor, and overhead to identify the primary driver.",
        )

    if signal_type == 'NEGATIVE_OPERATING_LEVERAGE':
        decouple = [f for f in supporting_findings if f.get('pattern') == 'Revenue-cost decoupling']
        worst    = max(decouple, key=lambda f: abs(f.get('divergence_pp', 0) or 0), default={})
        rev_chg  = worst.get('revenue_change_pct', 0) or 0
        cogs_chg = worst.get('cogs_change_pct', 0) or 0
        return (
            f"{company} exhibits negative operating leverage: revenue changed {rev_chg:+.1f}% "
            f"while COGS changed {cogs_chg:+.1f}% in the worst period, amplifying margin compression. "
            f"Fixed cost structure is not providing the expected leverage on revenue growth.",
            "Decompose COGS into fixed vs variable components. "
            "Assess whether fixed cost absorption is declining due to volume or utilization changes.",
        )

    if signal_type == 'SECTOR_CYCLE_PRESSURE':
        n_with  = ctx.get('peers_with_compression', 0)
        n_total = ctx.get('n_peers', 1)
        return (
            f"{company} margin compression appears sector-wide, with "
            f"{n_with} of {n_total - 1} peers also showing compression. "
            f"This is consistent with a cyclical sector downturn rather than a company-specific issue.",
            "Monitor commodity spread recovery. "
            "Compare relative margin performance to assess if company is outperforming or underperforming the cycle.",
        )

    if signal_type == 'NON_RECURRING_EVENT':
        periods = sorted({f.get('period', '') for f in supporting_findings if f.get('period')})
        period_label = ', '.join(periods) if periods else 'flagged periods'
        return (
            f"{company} shows isolated statistical anomalies ({period_label}) "
            f"without underlying trend deterioration. "
            f"No sustained margin compression or cost drift accompanies these spikes, "
            f"suggesting a non-recurring event (e.g., write-off, one-time charge).",
            "Review quarterly filings for the flagged periods to identify specific one-time items. "
            "Confirm the anomaly does not recur in subsequent periods.",
        )

    if signal_type == 'RELATIVE_OUTPERFORMANCE':
        has_exp = any(f.get('pattern') == 'Margin expansion' for f in supporting_findings)
        return (
            f"{company} is outperforming sector peers on key metrics "
            f"{'with expanding margins reinforcing the advantage' if has_exp else 'while maintaining stable margins'}. "
            f"This may indicate superior operational efficiency, pricing power, or product mix advantages.",
            "Investigate the source of competitive advantage. "
            "Assess sustainability: is it structural (cost position, scale) or temporary (pricing cycle)?",
        )

    if signal_type == 'RELATIVE_UNDERPERFORMANCE':
        return (
            f"{company} is underperforming vs sector peers while experiencing margin compression, "
            f"in a period where sector-wide pressure does not explain the gap. "
            f"This points to a company-specific operational or strategic issue.",
            "Investigate company-specific cost drivers, pricing strategy, and operational efficiency. "
            "Compare product mix and capacity utilization with outperforming peers.",
        )

    if signal_type == 'COST_INFLATION_PRESSURE':
        drift    = [f for f in supporting_findings if f.get('pattern') == 'Cost composition drift']
        shift_pp = max((f.get('shift_pp', 0) or 0 for f in drift), default=0)
        return (
            f"{company} faces cost inflation pressure: COGS burden is rising (+{shift_pp:.1f}pp) "
            f"and costs are growing faster than revenue. "
            f"Margins have not yet compressed significantly, but pressure is building.",
            "Monitor input cost hedging and pricing pass-through ability. "
            "Assess whether current pricing can absorb further cost increases before margin impact becomes severe.",
        )

    if signal_type == 'RECOVERY_SIGNAL':
        has_yoy = any(f.get('pattern') == 'YoY quarter comparison' for f in supporting_findings)
        has_dec = any(f.get('pattern') == 'Revenue-cost decoupling' for f in supporting_findings)
        detail  = (
            'favorable YoY comparison and improving cost-revenue dynamics'
            if (has_yoy and has_dec)
            else 'improving trends in revenue-cost dynamics or YoY comparison'
        )
        return (
            f"{company} shows recovery signals: margin expansion is accompanied by {detail}. "
            f"Early recovery from prior compression cycle may be underway.",
            "Assess whether recovery is driven by pricing recovery, volume growth, or cost reduction. "
            "Monitor sustainability over next 2-3 quarters to confirm structural improvement.",
        )

    # Fallback for unrecognized types
    return (
        f"{company}: {signal_type} detected based on {len(supporting_findings)} supporting signals.",
        "Review supporting findings for further investigation.",
    )


def _is_below_peer(finding: dict) -> bool:
    """True if peer divergence finding shows company performing worse than peers."""
    if finding.get('pattern') != 'Peer divergence':
        return False
    metric = finding.get('metric', '')
    # n=2 gap_pp findings
    if 'gap_pp' in finding:
        company_val = finding.get('company_value')
        peer_val = finding.get('peer_value')
        if company_val is None or peer_val is None:
            return False
        if 'Margin' in metric:
            return company_val < peer_val
        else:
            return company_val > peer_val
    # n>=3 z_score findings
    if 'z_score' in finding:
        z = finding.get('z_score', 0)
        if 'Margin' in metric:
            return z < 0
        else:
            return z > 0
    return False


def _is_above_peer(finding: dict) -> bool:
    """True if peer divergence finding shows company performing better than peers."""
    if finding.get('pattern') != 'Peer divergence':
        return False
    metric = finding.get('metric', '')
    # n=2 gap_pp findings
    if 'gap_pp' in finding:
        company_val = finding.get('company_value')
        peer_val = finding.get('peer_value')
        if company_val is None or peer_val is None:
            return False
        if 'Margin' in metric:
            return company_val > peer_val
        else:
            return company_val < peer_val
    # n>=3 z_score findings
    if 'z_score' in finding:
        z = finding.get('z_score', 0)
        if 'Margin' in metric:
            return z > 0
        else:
            return z < 0
    return False


def build_composite_signals(findings: list, df: pd.DataFrame) -> list:
    """Build composite signals by correlating multiple findings per company.

    Returns a list of composite signal dicts, each containing:
      company, period, analysis_window, composite_signal_type, severity,
      confidence, supporting_signals, signal_count, explanation,
      recommended_investigation_angle

    Processing steps:
    1. Normalize findings (filter + legacy taxonomy migration) via normalize_findings()
    2. Group by company
    3. Compute sector-wide context (used by Rules 3 and 6)
    4. Apply 8 rule-based composite signal classifiers
    5. Adjust composite confidence using _compute_composite_confidence()
    6. Generate human-readable explanation via explain_composite_signal()
    """
    composite = []

    # Step 1: Normalize — filters SUMMARY/Narrative findings and migrates legacy taxonomy
    active = normalize_findings(findings)

    # Step 2: Group by company
    by_company: dict = defaultdict(list)
    for f in active:
        by_company[f.get('company', '')].append(f)

    # Step 3: Build sector-wide view for SECTOR_CYCLE_PRESSURE (Rule 3) and
    #         RELATIVE_UNDERPERFORMANCE gate (Rule 6)
    all_companies = list(by_company.keys())
    sector_margin_comp_companies = set()
    for comp, cfindings in by_company.items():
        if any(f.get('pattern') == 'Margin compression' for f in cfindings):
            sector_margin_comp_companies.add(comp)
    n_peers = len(all_companies)

    for company, cfindings in by_company.items():
        # --- Categorize findings into semantic buckets ---
        margin_comp    = [f for f in cfindings if f.get('pattern') == 'Margin compression']
        margin_exp     = [f for f in cfindings if f.get('pattern') == 'Margin expansion']
        cost_drift_pos = [f for f in cfindings if f.get('pattern') == 'Cost composition drift'  and (f.get('shift_pp') or 0) > 0]
        cost_drift_neg = [f for f in cfindings if f.get('pattern') == 'Cost composition drift'  and (f.get('shift_pp') or 0) < 0]  # noqa: F841
        neg_decouple   = [f for f in cfindings if f.get('pattern') == 'Revenue-cost decoupling' and (f.get('divergence_pp') or 0) > 0]
        pos_decouple   = [f for f in cfindings if f.get('pattern') == 'Revenue-cost decoupling' and (f.get('divergence_pp') or 0) < 0]
        peers_below    = [f for f in cfindings if _is_below_peer(f)]
        peers_above    = [f for f in cfindings if _is_above_peer(f)]
        # Non-recurring statistical anomalies: isolated spikes or peer-confirmed one-off events.
        # Uses the unified DQ taxonomy set by _enrich_findings_with_dq().
        anomalies_ot   = [f for f in cfindings
                          if f.get('pattern') == 'Statistical anomaly'
                          and f.get('anomaly_type') in ('LOW_CONFIDENCE_SIGNAL', 'EVENT_DRIVEN_BUT_PLAUSIBLE')]
        # Structural anomalies: persistent pattern across adjacent periods (VALID_SIGNAL)
        anomalies_str  = [f for f in cfindings  # noqa: F841
                          if f.get('pattern') == 'Statistical anomaly'
                          and f.get('anomaly_type') == 'VALID_SIGNAL']
        yoy_worse      = [f for f in cfindings if f.get('pattern') == 'YoY quarter comparison' and (f.get('yoy_change_pp') or 0) < -15]  # noqa: F841
        yoy_better     = [f for f in cfindings if f.get('pattern') == 'YoY quarter comparison' and (f.get('yoy_change_pp') or 0) > 15]

        # Sector-wide compression check (True when ≥ n-1 peers also compressed)
        peers_with_compression = sector_margin_comp_companies - {company}
        sector_wide = (
            n_peers >= 2 and
            len(peers_with_compression) >= max(2, n_peers - 1)
        )

        # Analysis window: full date range for this company in the dataset
        comp_rows = df[df['DENOM_CIA'] == company] if 'DENOM_CIA' in df.columns else pd.DataFrame()
        if not comp_rows.empty and 'DT_REFER' in comp_rows.columns:
            dates = pd.to_datetime(comp_rows['DT_REFER'], errors='coerce').dropna()
            analysis_window = (
                f"{dates.min().strftime('%Y-%m-%d')} to {dates.max().strftime('%Y-%m-%d')}"
                if not dates.empty else 'unknown'
            )
        else:
            analysis_window = 'unknown'

        fired_structural = False

        # ----------------------------------------------------------------
        # Rule 1: STRUCTURAL_COMPETITIVENESS_ISSUE
        #   Trigger: cost_drift_pos ∩ margin_comp
        #   Confidence boost: peers_below or ≥3 total supporting signals
        # ----------------------------------------------------------------
        if cost_drift_pos and margin_comp:
            signals   = cost_drift_pos + margin_comp + peers_below
            base_conf = 'HIGH' if (peers_below or len(signals) >= 3) else 'MEDIUM'
            explanation, angle = explain_composite_signal(
                'STRUCTURAL_COMPETITIVENESS_ISSUE', company, signals
            )
            composite.append({
                'company':     company,
                'period':      ', '.join(sorted({f.get('period', '') for f in cost_drift_pos + margin_comp if f.get('period')})) or 'multiple periods',
                'analysis_window': analysis_window,
                'composite_signal_type': 'STRUCTURAL_COMPETITIVENESS_ISSUE',
                'severity':    'HIGH',
                'confidence':  _compute_composite_confidence(base_conf, signals),
                'supporting_signals': list({f.get('pattern') for f in signals}),
                'signal_count': len(signals),
                'explanation': explanation,
                'recommended_investigation_angle': angle,
            })
            fired_structural = True

        # ----------------------------------------------------------------
        # Rule 2: NEGATIVE_OPERATING_LEVERAGE
        #   Trigger: neg_decouple ∩ margin_comp
        # ----------------------------------------------------------------
        if neg_decouple and margin_comp:
            signals  = neg_decouple + margin_comp
            worst    = max(neg_decouple, key=lambda f: abs(f.get('divergence_pp', 0) or 0))
            all_sev  = [f.get('severity') for f in signals]
            sev      = 'HIGH' if 'HIGH' in all_sev else 'MEDIUM'
            explanation, angle = explain_composite_signal(
                'NEGATIVE_OPERATING_LEVERAGE', company, signals
            )
            composite.append({
                'company':     company,
                'period':      worst.get('period', 'multiple periods'),
                'analysis_window': analysis_window,
                'composite_signal_type': 'NEGATIVE_OPERATING_LEVERAGE',
                'severity':    sev,
                'confidence':  _compute_composite_confidence('HIGH', signals),
                'supporting_signals': list({f.get('pattern') for f in signals}),
                'signal_count': len(signals),
                'explanation': explanation,
                'recommended_investigation_angle': angle,
            })

        # ----------------------------------------------------------------
        # Rule 3: SECTOR_CYCLE_PRESSURE
        #   Trigger: margin_comp ∩ sector_wide ∧ NOT (cost_drift_pos ∩ peers_below)
        #   (if structural issue already explains the compression, don't also call it cyclical)
        # ----------------------------------------------------------------
        if margin_comp and sector_wide and not (cost_drift_pos and peers_below):
            signals    = margin_comp
            sector_ctx = {'peers_with_compression': len(peers_with_compression), 'n_peers': n_peers}
            explanation, angle = explain_composite_signal(
                'SECTOR_CYCLE_PRESSURE', company, signals, sector_context=sector_ctx
            )
            composite.append({
                'company':     company,
                'period':      ', '.join(sorted({f.get('period', '') for f in margin_comp if f.get('period')})) or 'multiple periods',
                'analysis_window': analysis_window,
                'composite_signal_type': 'SECTOR_CYCLE_PRESSURE',
                'severity':    'MEDIUM',
                'confidence':  _compute_composite_confidence('HIGH', signals),
                'supporting_signals': list({f.get('pattern') for f in signals}),
                'signal_count': len(signals),
                'explanation': explanation,
                'recommended_investigation_angle': angle,
            })

        # ----------------------------------------------------------------
        # Rule 4: NON_RECURRING_EVENT
        #   Trigger: anomalies_ot (isolated/event-driven anomalies) ∧ no persistent trend
        # ----------------------------------------------------------------
        if anomalies_ot and not margin_comp and not cost_drift_pos:
            signals     = anomalies_ot
            explanation, angle = explain_composite_signal(
                'NON_RECURRING_EVENT', company, signals
            )
            composite.append({
                'company':     company,
                'period':      ', '.join(sorted({f.get('period', '') for f in signals if f.get('period')})) or 'unknown period',
                'analysis_window': analysis_window,
                'composite_signal_type': 'NON_RECURRING_EVENT',
                'severity':    'MEDIUM',
                'confidence':  _compute_composite_confidence('MEDIUM', signals),
                'supporting_signals': list({f.get('pattern') for f in signals}),
                'signal_count': len(signals),
                'explanation': explanation,
                'recommended_investigation_angle': angle,
            })

        # ----------------------------------------------------------------
        # Rule 5: RELATIVE_OUTPERFORMANCE
        #   Trigger: peers_above ∧ (margin expanding OR no compression)
        # ----------------------------------------------------------------
        if peers_above and (margin_exp or not margin_comp):
            signals   = peers_above + margin_exp
            base_conf = 'HIGH' if margin_exp else 'MEDIUM'
            explanation, angle = explain_composite_signal(
                'RELATIVE_OUTPERFORMANCE', company, signals
            )
            composite.append({
                'company':     company,
                'period':      ', '.join(sorted({f.get('period', '') for f in signals if f.get('period')})) or 'latest period',
                'analysis_window': analysis_window,
                'composite_signal_type': 'RELATIVE_OUTPERFORMANCE',
                'severity':    'MEDIUM',
                'confidence':  _compute_composite_confidence(base_conf, signals),
                'supporting_signals': list({f.get('pattern') for f in signals}),
                'signal_count': len(signals),
                'explanation': explanation,
                'recommended_investigation_angle': angle,
            })

        # ----------------------------------------------------------------
        # Rule 6: RELATIVE_UNDERPERFORMANCE
        #   Trigger: peers_below ∩ margin_comp ∧ NOT sector_wide ∧ NOT already structural
        # ----------------------------------------------------------------
        if peers_below and margin_comp and not sector_wide and not fired_structural:
            signals     = peers_below + margin_comp
            explanation, angle = explain_composite_signal(
                'RELATIVE_UNDERPERFORMANCE', company, signals
            )
            composite.append({
                'company':     company,
                'period':      ', '.join(sorted({f.get('period', '') for f in signals if f.get('period')})) or 'latest period',
                'analysis_window': analysis_window,
                'composite_signal_type': 'RELATIVE_UNDERPERFORMANCE',
                'severity':    'HIGH',
                'confidence':  _compute_composite_confidence('HIGH', signals),
                'supporting_signals': list({f.get('pattern') for f in signals}),
                'signal_count': len(signals),
                'explanation': explanation,
                'recommended_investigation_angle': angle,
            })

        # ----------------------------------------------------------------
        # Rule 7: COST_INFLATION_PRESSURE
        #   Trigger: cost_drift_pos ∩ neg_decouple ∧ no compression yet
        # ----------------------------------------------------------------
        if cost_drift_pos and neg_decouple and not margin_comp:
            signals     = cost_drift_pos + neg_decouple
            explanation, angle = explain_composite_signal(
                'COST_INFLATION_PRESSURE', company, signals
            )
            composite.append({
                'company':     company,
                'period':      ', '.join(sorted({f.get('period', '') for f in signals if f.get('period')})) or 'multiple periods',
                'analysis_window': analysis_window,
                'composite_signal_type': 'COST_INFLATION_PRESSURE',
                'severity':    'MEDIUM',
                'confidence':  _compute_composite_confidence('MEDIUM', signals),
                'supporting_signals': list({f.get('pattern') for f in signals}),
                'signal_count': len(signals),
                'explanation': explanation,
                'recommended_investigation_angle': angle,
            })

        # ----------------------------------------------------------------
        # Rule 8: RECOVERY_SIGNAL
        #   Trigger: margin_exp ∩ (yoy_better OR pos_decouple)
        #   Confidence HIGH only when both YoY improvement AND favorable cost decoupling present
        # ----------------------------------------------------------------
        if margin_exp and (yoy_better or pos_decouple):
            signals   = margin_exp + yoy_better + pos_decouple
            base_conf = 'HIGH' if (yoy_better and pos_decouple) else 'MEDIUM'
            explanation, angle = explain_composite_signal(
                'RECOVERY_SIGNAL', company, signals
            )
            composite.append({
                'company':     company,
                'period':      ', '.join(sorted({f.get('period', '') for f in signals if f.get('period')})) or 'recent periods',
                'analysis_window': analysis_window,
                'composite_signal_type': 'RECOVERY_SIGNAL',
                'severity':    'MEDIUM',
                'confidence':  _compute_composite_confidence(base_conf, signals),
                'supporting_signals': list({f.get('pattern') for f in signals}),
                'signal_count': len(signals),
                'explanation': explanation,
                'recommended_investigation_angle': angle,
            })

    return composite


# =============================================================================
# Risk Scoring Engine
# =============================================================================

def _score_magnitude(findings: list) -> float:
    """Score magnitude of deterioration signals (0-20)."""
    margin_comp    = [f for f in findings if f.get('pattern') == 'Margin compression']
    cost_drift_pos = [f for f in findings if f.get('pattern') == 'Cost composition drift' and (f.get('shift_pp') or 0) > 0]
    peers_below    = [f for f in findings if _is_below_peer(f)]

    scores = []
    if margin_comp:
        max_chg = max(abs(f.get('annual_change_pp', 0)) for f in margin_comp)
        scores.append(min(20.0, max_chg * 2))
    if cost_drift_pos:
        max_shift = max(f.get('shift_pp', 0) for f in cost_drift_pos)
        scores.append(min(20.0, max_shift * 1.5))
    if peers_below:
        vals = []
        for f in peers_below:
            gap = f.get('gap_pp')
            z = f.get('z_score')
            if gap is not None:
                vals.append(gap)
            elif z is not None:
                vals.append(abs(z) * 10)
        if vals:
            scores.append(min(20.0, max(vals) * 0.8))

    return max(scores) if scores else 0.0


def _score_persistence(findings: list, df: pd.DataFrame, company: str) -> float:
    """Score persistence of deterioration signals (0-20)."""
    if df is None or df.empty:
        return 10.0  # neutral

    comp_df = df[df['DENOM_CIA'] == company] if 'DENOM_CIA' in df.columns else pd.DataFrame()

    if comp_df.empty:
        return 10.0

    # Compute stress fraction from df
    stress_fractions = []
    if 'EBIT_Margin_pct' in comp_df.columns:
        series = comp_df['EBIT_Margin_pct'].dropna()
        if len(series) > 0:
            frac_neg_ebit = (series < 0).sum() / len(series)
            stress_fractions.append(frac_neg_ebit)
    if 'COGS_pct_Revenue' in comp_df.columns:
        series = comp_df['COGS_pct_Revenue'].dropna()
        if len(series) > 0:
            frac_cogs_above_90 = (series > 90).sum() / len(series)
            stress_fractions.append(frac_cogs_above_90)

    stress_fraction = max(stress_fractions) if stress_fractions else 0.0

    # Finding persistence
    margin_comp_n = sum(1 for f in findings if f.get('pattern') == 'Margin compression')
    yoy_worse_n   = sum(1 for f in findings if f.get('pattern') == 'YoY quarter comparison' and (f.get('yoy_change_pp') or 0) < -15)
    finding_persistence = min(1.0, (margin_comp_n + yoy_worse_n * 0.5) / 3)

    score = min(20.0, (stress_fraction * 0.5 + finding_persistence * 0.5) * 20)
    return score


def _score_confirmation(findings: list) -> float:
    """Score signal confirmation (0-20) based on distinct deterioration signal types."""
    signal_types = set()
    for f in findings:
        pattern = f.get('pattern', '')
        if pattern == 'Margin compression':
            signal_types.add('margin_compression')
        if pattern == 'Cost composition drift' and (f.get('shift_pp') or 0) > 0:
            signal_types.add('cost_drift')
        if _is_below_peer(f):
            signal_types.add('peer_gap')
        if pattern == 'Revenue-cost decoupling' and (f.get('divergence_pp') or 0) > 0:
            signal_types.add('cost_decoupling')
        if pattern == 'YoY quarter comparison' and (f.get('yoy_change_pp') or 0) < -15:
            signal_types.add('yoy_deterioration')

    n = len(signal_types)
    score_map = {0: 0, 1: 4, 2: 10, 3: 15}
    return score_map.get(n, 20) if n <= 3 else 20


def _score_peer_gap(findings: list) -> float:
    """Score peer gap magnitude (0-20)."""
    scores = []
    for f in findings:
        if not _is_below_peer(f):
            continue
        gap = f.get('gap_pp')
        z = f.get('z_score')
        if gap is not None:
            scores.append(min(20.0, gap * 0.8))
        elif z is not None:
            scores.append(min(20.0, abs(z) * 7))
    return max(scores) if scores else 0.0


def _score_data_confidence(findings: list) -> float:
    """Score data confidence (0-20). Base 10, penalize LOW, reward HIGH."""
    if not findings:
        return 10.0
    n_total = len(findings)
    n_low   = sum(1 for f in findings if f.get('confidence_score') == 'LOW')
    n_high  = sum(1 for f in findings if f.get('confidence_score') == 'HIGH')
    low_ratio  = n_low  / n_total
    high_ratio = n_high / n_total
    score = 10.0 - (low_ratio * 8) + (high_ratio * 10)
    return max(0.0, min(20.0, score))


def score_company_risk(
    company: str,
    company_findings: list,
    composite_signals: list,
    df: pd.DataFrame,
) -> dict:
    """Score overall risk for a company.

    Returns dict with company, risk_score, priority, top_risk_drivers,
    score_breakdown, composite_signal_count, composite_signal_types,
    key_supporting_findings, executive_summary.
    """
    # Filter to non-SUMMARY entries
    active = [f for f in company_findings if f.get('severity') != 'SUMMARY']

    # Company composite signals
    company_cs = [s for s in composite_signals if s.get('company') == company]

    # Score dimensions
    mag  = _score_magnitude(active)
    pers = _score_persistence(active, df, company)
    conf = _score_confirmation(active)
    pg   = _score_peer_gap(active)
    dc   = _score_data_confidence(active)

    total = mag + pers + conf + pg + dc

    if total >= 75:
        priority = 'CRITICAL'
    elif total >= 50:
        priority = 'HIGH'
    elif total >= 25:
        priority = 'MEDIUM'
    else:
        priority = 'LOW'

    # Top drivers: top 3 composite signal types (HIGH severity first, then signal_count)
    if company_cs:
        sorted_cs = sorted(
            company_cs,
            key=lambda s: (0 if s.get('severity') == 'HIGH' else 1, -s.get('signal_count', 0))
        )
        top_drivers = [s['composite_signal_type'] for s in sorted_cs[:3]]
    else:
        # Fall back to top 3 raw non-LOW-confidence findings by severity
        raw_findings = [
            f for f in active
            if f.get('confidence_score') != 'LOW'
        ]
        raw_sorted = sorted(
            raw_findings,
            key=lambda f: (0 if f.get('severity') == 'HIGH' else 1)
        )
        top_drivers = [f.get('pattern', 'Unknown') for f in raw_sorted[:3]]

    # Executive summary
    cs_types = [s['composite_signal_type'] for s in company_cs]
    if cs_types:
        cs_summary = ', '.join(cs_types[:2])
        exec_summary = (
            f"{company} is rated {priority} risk (score: {total:.1f}/100). "
            f"Primary concerns: {cs_summary}."
        )
    else:
        exec_summary = (
            f"{company} is rated {priority} risk (score: {total:.1f}/100). "
            f"No composite signals detected; review individual findings."
        )

    return {
        'company': company,
        'risk_score': round(total, 1),
        'priority': priority,
        'top_risk_drivers': top_drivers,
        'score_breakdown': {
            'magnitude': round(mag, 1),
            'persistence': round(pers, 1),
            'confirmation': round(conf, 1),
            'peer_gap': round(pg, 1),
            'data_confidence': round(dc, 1),
        },
        'composite_signal_count': len(company_cs),
        'composite_signal_types': cs_types,
        'key_supporting_findings': len(active),
        'executive_summary': exec_summary,
    }


# =============================================================================
# Pattern 1: Margin Trend Analysis
# =============================================================================

def analyze_margin_trends(df: pd.DataFrame, periods_per_year: int = 4) -> list:
    """
    Detect sustained margin compression or expansion.

    A CFO cares about this because:
    - Gradual margin erosion often goes unnoticed period by period
    - The rate of change matters more than the absolute level
    - Divergence from sector peers signals company-specific issues

    Args:
        periods_per_year: 4 for quarterly data, 1 for annual data.
                          Used to annualize the slope for reporting.
    """
    findings = []

    for company in df['DENOM_CIA'].unique():
        comp = df[df['DENOM_CIA'] == company].sort_values('DT_REFER').copy()

        if len(comp) < 4:  # Need at least 4 periods for trend analysis
            continue

        for margin_col in ['Gross_Margin_pct', 'EBIT_Margin_pct']:
            if margin_col not in comp.columns:
                continue

            series = comp[margin_col].dropna()
            if len(series) < 4:
                continue

            # Linear trend
            x = np.arange(len(series))
            slope, intercept = np.polyfit(x, series.values, 1)

            # Annualized rate of change
            annual_change = slope * periods_per_year

            # Volatility (standard deviation)
            volatility = series.std()

            # Recent vs historical average
            recent_avg = series.tail(4).mean()
            historical_avg = series.mean()

            # Flag significant trends
            if abs(annual_change) > 2:  # More than 2pp per year
                direction = "compression" if annual_change < 0 else "expansion"
                findings.append({
                    'company': company,
                    'metric': margin_col,
                    'pattern': f'Margin {direction}',
                    'annual_change_pp': round(annual_change, 2),
                    'current_level': round(series.iloc[-1], 2),
                    'volatility': round(volatility, 2),
                    'periods_analyzed': len(series),
                    'severity': 'HIGH' if abs(annual_change) > 5 else 'MEDIUM',
                    'insight': (
                        f"{company}: {margin_col.replace('_pct', '')} shows "
                        f"{direction} of {abs(annual_change):.1f}pp/year. "
                        f"Current: {series.iloc[-1]:.1f}%, "
                        f"Historical avg: {historical_avg:.1f}%. "
                        f"{'This rate is unsustainable and warrants investigation.' if abs(annual_change) > 5 else 'Monitor closely.'}"
                    )
                })

            # Flag high volatility
            if volatility > 5:
                findings.append({
                    'company': company,
                    'metric': margin_col,
                    'pattern': 'High margin volatility',
                    'volatility': round(volatility, 2),
                    'min': round(series.min(), 2),
                    'max': round(series.max(), 2),
                    'range': round(series.max() - series.min(), 2),
                    'severity': 'MEDIUM',
                    'insight': (
                        f"{company}: {margin_col.replace('_pct', '')} swings "
                        f"from {series.min():.1f}% to {series.max():.1f}% "
                        f"(range: {series.max() - series.min():.1f}pp). "
                        f"High volatility suggests exposure to commodity cycles "
                        f"or pricing power issues."
                    )
                })

    return findings


# =============================================================================
# Pattern 2: Cost Composition Drift
# =============================================================================

def analyze_cost_drift(df: pd.DataFrame) -> list:
    """
    Detect changes in cost structure that aren't explained by revenue changes.

    This is the classic "hidden pattern" — costs can shift between categories
    (e.g., COGS absorbing costs that used to be in SG&A, or vice versa)
    without anyone noticing because the total looks stable.
    """
    findings = []

    cost_cols = [
        ('COGS_pct_Revenue', 'COGS'),
        ('SGA_pct_Revenue', 'SG&A'),
        ('Selling_pct_Revenue', 'Selling Expenses'),
    ]

    for company in df['DENOM_CIA'].unique():
        comp = df[df['DENOM_CIA'] == company].sort_values('DT_REFER').copy()

        if len(comp) < 4:
            continue

        # Check if cost composition is shifting
        available_costs = [(col, name) for col, name in cost_cols if col in comp.columns]

        for col, name in available_costs:
            series = comp[col].dropna()
            if len(series) < 4:
                continue

            # Compare first half vs second half of the time series
            mid = len(series) // 2
            first_half = series.iloc[:mid].mean()
            second_half = series.iloc[mid:].mean()
            shift = second_half - first_half

            if abs(shift) > 3:  # More than 3pp shift
                econ_label = "deterioration" if shift > 0 else "improvement"
                findings.append({
                    'company': company,
                    'metric': col,
                    'pattern': 'Cost composition drift',
                    'first_half_avg': round(first_half, 2),
                    'second_half_avg': round(second_half, 2),
                    'shift_pp': round(shift, 2),
                    'severity': 'HIGH' if abs(shift) > 5 else 'MEDIUM',
                    'insight': (
                        f"{company}: {name} burden shifted from {first_half:.1f}% to "
                        f"{second_half:.1f}% of revenue — a {abs(shift):.1f}pp {econ_label}. "
                        f"This structural shift may indicate changes in "
                        f"{'input costs, product mix, or operational efficiency' if name == 'COGS' else 'organizational structure or cost allocation methodology'}."
                    )
                })

        # Check for cost transfer between categories
        # (One goes up while another goes down = potential reclassification)
        if len(available_costs) >= 2:
            for i, (col1, name1) in enumerate(available_costs):
                for col2, name2 in available_costs[i+1:]:
                    s1 = comp[col1].dropna()
                    s2 = comp[col2].dropna()

                    if len(s1) < 4 or len(s2) < 4:
                        continue

                    # Check correlation — negative correlation suggests transfer
                    if len(s1) == len(s2):
                        corr = s1.corr(s2)
                        if corr < -0.5:
                            findings.append({
                                'company': company,
                                'pattern': 'Potential cost reclassification',
                                'categories': f"{name1} ↔ {name2}",
                                'correlation': round(corr, 3),
                                'severity': 'HIGH',
                                'insight': (
                                    f"{company}: {name1} and {name2} show strong "
                                    f"negative correlation ({corr:.2f}), suggesting "
                                    f"costs may be shifting between categories. "
                                    f"This could indicate accounting reclassification "
                                    f"or genuine operational changes worth investigating."
                                )
                            })

    return findings


# =============================================================================
# Pattern 3: Revenue-Cost Decoupling
# =============================================================================

def analyze_revenue_cost_decoupling(df: pd.DataFrame) -> list:
    """
    Detect periods where costs don't move proportionally with revenue.

    In capital-intensive industries, you'd expect COGS to have a strong
    relationship with revenue. When they decouple, it signals either:
    - Fixed cost leverage (good) or de-leverage (bad)
    - Product mix changes
    - Input cost shocks being absorbed
    - Pricing power (or loss thereof)
    """
    findings = []

    revenue_col = 'Receita de Venda de Bens e/ou Serviços'
    cogs_col = 'Custo dos Bens e/ou Serviços Vendidos'

    if revenue_col not in df.columns or cogs_col not in df.columns:
        return findings

    for company in df['DENOM_CIA'].unique():
        comp = df[df['DENOM_CIA'] == company].sort_values('DT_REFER').copy()

        if len(comp) < 4:
            continue

        revenue = comp[revenue_col].dropna()
        cogs = comp[cogs_col].dropna().abs()  # COGS is typically negative

        if len(revenue) < 4 or len(cogs) < 4:
            continue

        # Compute period-over-period changes
        rev_pct_change = revenue.pct_change().dropna()
        cogs_pct_change = cogs.pct_change().dropna()

        # Find periods where revenue and COGS diverge significantly
        if len(rev_pct_change) == len(cogs_pct_change):
            delta = (cogs_pct_change.values - rev_pct_change.values) * 100

            # Flag periods with >10pp divergence
            anomalous_periods = np.where(np.abs(delta) > 10)[0]

            if len(anomalous_periods) > 0:
                for idx in anomalous_periods:
                    period_idx = rev_pct_change.index[idx]
                    date = comp.loc[period_idx, 'DT_REFER'] if period_idx in comp.index else 'Unknown'
                    rev_chg = rev_pct_change.iloc[idx] * 100
                    cogs_chg = cogs_pct_change.iloc[idx] * 100

                    findings.append({
                        'company': company,
                        'pattern': 'Revenue-cost decoupling',
                        'period': str(date),
                        'revenue_change_pct': round(rev_chg, 1),
                        'cogs_change_pct': round(cogs_chg, 1),
                        'divergence_pp': round(delta[idx], 1),
                        'severity': 'HIGH' if abs(delta[idx]) > 20 else 'MEDIUM',
                        'insight': (
                            f"{company} ({date}): Revenue changed {rev_chg:+.1f}% "
                            f"but COGS changed {cogs_chg:+.1f}% — "
                            f"a {abs(delta[idx]):.1f}pp divergence. "
                            f"{'COGS grew faster than revenue (margin pressure)' if delta[idx] > 0 else 'Revenue outpaced COGS (margin expansion)'}. "
                            f"Investigate: product mix shift, input cost changes, "
                            f"or one-time items."
                        )
                    })

    return findings


# =============================================================================
# Pattern 4: Cross-Company Comparison (sector-aware)
# =============================================================================

def analyze_peer_comparison(df: pd.DataFrame, sector_map: dict = None) -> list:
    """
    Compare financial metrics across companies in the same sector.

    Divergence from peers is one of the most powerful signals because
    it controls for macro factors (commodity prices, FX, demand cycles)
    and isolates company-specific performance.

    Args:
        sector_map: Dict mapping uppercase DENOM_CIA fragments to sector names.
                    When provided, companies are only compared within their sector.
                    When None, all companies are compared together (original behavior).
    """
    findings = []

    metric_cols = ['Gross_Margin_pct', 'EBIT_Margin_pct', 'COGS_pct_Revenue', 'SGA_pct_Revenue']
    available_metrics = [col for col in metric_cols if col in df.columns]

    if not available_metrics or df['DENOM_CIA'].nunique() < 2:
        return findings

    # Get latest period for each company
    latest = df.sort_values('DT_REFER').groupby('DENOM_CIA').tail(1).copy()

    # Assign sector labels
    def _get_sector(company_name: str) -> str:
        if sector_map:
            for fragment, sector in sector_map.items():
                if fragment.upper() in company_name.upper():
                    return sector
        return 'All'

    latest['_sector'] = latest['DENOM_CIA'].apply(_get_sector)

    for sector_name, sector_df in latest.groupby('_sector'):
        if len(sector_df) < 2:
            continue

        for metric in available_metrics:
            values = sector_df[['DENOM_CIA', metric]].dropna()
            if len(values) < 2:
                continue

            # n=2: z-score is always ±0.71 (ddof=1) regardless of gap size — use absolute gap
            if len(values) == 2:
                threshold = 10.0 if 'Margin' in metric else 15.0
                gap = abs(values[metric].iloc[0] - values[metric].iloc[1])
                if gap > threshold:
                    if 'Margin' in metric:
                        worse_idx = values[metric].idxmin()
                        better_idx = values[metric].idxmax()
                        verb = 'trails'
                    else:
                        worse_idx = values[metric].idxmax()
                        better_idx = values[metric].idxmin()
                        verb = 'exceeds'
                    worse_row = values.loc[worse_idx]
                    better_row = values.loc[better_idx]
                    finding = {
                        'company': worse_row['DENOM_CIA'],
                        'metric': metric,
                        'pattern': 'Peer divergence',
                        'company_value': round(worse_row[metric], 2),
                        'peer_value': round(better_row[metric], 2),
                        'gap_pp': round(gap, 2),
                        'severity': 'HIGH' if gap > (20.0 if 'Margin' in metric else 25.0) else 'MEDIUM',
                        'insight': (
                            f"{worse_row['DENOM_CIA']}: {metric.replace('_pct', '')} "
                            f"({worse_row[metric]:.1f}%) {verb} "
                            f"{better_row['DENOM_CIA']} ({better_row[metric]:.1f}%) "
                            f"by {gap:.1f}pp."
                        ),
                    }
                    if sector_map:
                        finding['sector'] = sector_name
                    findings.append(finding)
                continue  # skip z-score path for n=2

            mean_val = values[metric].mean()
            std_val = values[metric].std()

            for _, row in values.iterrows():
                if std_val > 0:
                    z_score = (row[metric] - mean_val) / std_val
                    if abs(z_score) > 1:
                        position = "above" if z_score > 0 else "below"
                        finding = {
                            'company': row['DENOM_CIA'],
                            'metric': metric,
                            'pattern': 'Peer divergence',
                            'company_value': round(row[metric], 2),
                            'peer_average': round(mean_val, 2),
                            'z_score': round(z_score, 2),
                            'severity': 'HIGH' if abs(z_score) > 2 else 'MEDIUM',
                            'insight': (
                                f"{row['DENOM_CIA']}: {metric.replace('_pct', '')} "
                                f"at {row[metric]:.1f}% is significantly {position} "
                                f"the {sector_name} peer average of {mean_val:.1f}% "
                                f"(z-score: {z_score:+.1f}). "
                                f"{'This could indicate superior operational efficiency or different business model.' if position == 'above' and 'Margin' in metric else 'Investigate structural disadvantages or strategic positioning differences.'}"
                            )
                        }
                        if sector_map:
                            finding['sector'] = sector_name
                        findings.append(finding)

    return findings


# =============================================================================
# Pattern 5: Anomaly Detection (Statistical Outliers)
# =============================================================================

def detect_anomalies(df: pd.DataFrame) -> list:
    """
    Flag individual data points that are statistical outliers.

    Uses IQR method (more robust than z-score for financial data
    which tends to have fat tails).
    """
    findings = []

    metric_cols = ['Gross_Margin_pct', 'EBIT_Margin_pct', 'COGS_pct_Revenue']
    available_metrics = [col for col in metric_cols if col in df.columns]

    for company in df['DENOM_CIA'].unique():
        comp = df[df['DENOM_CIA'] == company].sort_values('DT_REFER').reset_index(drop=True)

        for metric in available_metrics:
            series = comp[metric].dropna()
            if len(series) < 6:
                continue

            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            # Identify outlier positions for neighbor-aware classification
            is_outlier = comp[metric].notna() & (
                (comp[metric] < lower) | (comp[metric] > upper)
            )
            outlier_idxs = set(comp[is_outlier].index.tolist())

            for pos in sorted(outlier_idxs):
                row = comp.iloc[pos]
                value = row[metric]

                # Rule 1: physically impossible value → data issue (pre-enrichment classification)
                if metric in ('Gross_Margin_pct', 'COGS_pct_Revenue') and value > 100:
                    anomaly_type = 'DATA_ISSUE'
                    confidence_score = 'LOW'
                # Rule 2: adjacent period also an outlier → persistent structural shift
                elif (pos - 1) in outlier_idxs or (pos + 1) in outlier_idxs:
                    anomaly_type = 'VALID_SIGNAL'
                    confidence_score = 'HIGH'
                # Rule 3: isolated outlier → low-confidence, needs context
                else:
                    anomaly_type = 'LOW_CONFIDENCE_SIGNAL'
                    confidence_score = 'MEDIUM'
                # Note: _enrich_findings_with_dq() will overwrite anomaly_type using the
                # full DQ rules (plausibility thresholds, peer confirmation, row-level context)

                findings.append({
                    'company': company,
                    'metric': metric,
                    'pattern': 'Statistical anomaly',
                    'period': row['DT_REFER'],
                    'value': round(value, 2),
                    'normal_range': f"{round(lower, 1)} - {round(upper, 1)}",
                    'anomaly_type': anomaly_type,
                    'confidence_score': confidence_score,
                    'severity': 'HIGH',
                    'insight': (
                        f"{company} ({row['DT_REFER']}): {metric.replace('_pct', '')} "
                        f"at {value:.1f}% is outside the normal range "
                        f"({lower:.1f}% to {upper:.1f}%). "
                        f"Investigate one-time items, impairments, or "
                        f"extraordinary events in this period."
                    )
                })

    return findings


# =============================================================================
# Pattern 6: YoY Same-Quarter Comparison
# =============================================================================

def analyze_yoy_comparison(
    df: pd.DataFrame, max_findings_per_company: int = 3
) -> list:
    """
    Compare same-quarter performance year-over-year to control for seasonality.

    Q3 2024 vs Q3 2023 is more informative than Q3 2024 vs Q2 2024 for
    businesses with seasonal cost structures (energy, maintenance cycles,
    ethylene/naphtha spot price exposure).

    Flags changes > 15pp YoY (capital-intensive commodity sectors see routine
    10-20pp swings; lower thresholds generate excessive noise).

    Args:
        max_findings_per_company: Keep only the top N most extreme YoY swings
                                  per company per metric (default 3).
    """
    findings = []

    if df.empty or 'DT_REFER' not in df.columns:
        return findings

    df = df.copy()
    df['DT_REFER_dt'] = pd.to_datetime(df['DT_REFER'], errors='coerce')
    df['year'] = df['DT_REFER_dt'].dt.year
    df['quarter'] = df['DT_REFER_dt'].dt.quarter

    metric_cols = ['Gross_Margin_pct', 'EBIT_Margin_pct']
    available = [c for c in metric_cols if c in df.columns]

    for company in df['DENOM_CIA'].unique():
        comp = df[df['DENOM_CIA'] == company].copy()

        for metric in available:
            company_metric_findings = []

            for quarter in range(1, 5):
                q_data = (
                    comp[comp['quarter'] == quarter]
                    .sort_values('year')[['year', metric]]
                    .dropna()
                )
                if len(q_data) < 2:
                    continue

                q_data = q_data.copy()
                q_data['yoy_change'] = q_data[metric].diff()

                for _, row in q_data.dropna(subset=['yoy_change']).iterrows():
                    if abs(row['yoy_change']) > 15:  # 15pp threshold for commodity sectors
                        direction = "improved" if row['yoy_change'] > 0 else "deteriorated"
                        company_metric_findings.append({
                            'company': company,
                            'metric': metric,
                            'pattern': 'YoY quarter comparison',
                            'period': f"Q{quarter} {int(row['year'])}",
                            'yoy_change_pp': round(row['yoy_change'], 2),
                            'current_value': round(row[metric], 2),
                            'severity': 'HIGH' if abs(row['yoy_change']) > 25 else 'MEDIUM',
                            'insight': (
                                f"{company}: {metric.replace('_pct', '')} in "
                                f"Q{quarter} {int(row['year'])} {direction} by "
                                f"{abs(row['yoy_change']):.1f}pp vs "
                                f"Q{quarter} {int(row['year']) - 1} "
                                f"(now {row[metric]:.1f}%). "
                                f"Same-quarter comparison controls for seasonality."
                            )
                        })

            # Keep only the most extreme swings per company+metric
            company_metric_findings.sort(
                key=lambda f: abs(f['yoy_change_pp']), reverse=True
            )
            findings.extend(company_metric_findings[:max_findings_per_company])

    return findings


# =============================================================================
# Narrative Synthesis
# =============================================================================

def synthesize_company_narratives(findings: list, df: pd.DataFrame) -> list:
    """
    Generate a 2-4 sentence narrative per company by correlating findings.

    Looks for compound signals:
    - Cost drift + Margin compression → deteriorating/improving cost structure
    - Revenue-cost decoupling → inflection point in cost behaviour
    - Peer divergence → structural vs. cyclical underperformance
    """
    narrative_findings = []

    by_company: dict = defaultdict(list)
    for f in findings:
        if f.get('pattern') != 'Company Narrative':
            by_company[f.get('company', '')].append(f)

    for company, cfinding in sorted(by_company.items()):
        drift    = [f for f in cfinding if f['pattern'] == 'Cost composition drift']
        compress = [f for f in cfinding if f['pattern'] in ('Margin compression', 'Margin expansion')]
        decouple = [f for f in cfinding if f['pattern'] == 'Revenue-cost decoupling']
        peers    = [f for f in cfinding if f['pattern'] == 'Peer divergence']

        sentences = []

        # Sentence 1: cost structure headline
        cogs_drift = next((f for f in drift if 'COGS' in f.get('metric', '')), None)
        ebit_comp  = next((f for f in compress if 'EBIT' in f.get('metric', '')), None)
        gross_comp = next((f for f in compress if 'Gross' in f.get('metric', '')), None)

        if cogs_drift and (ebit_comp or gross_comp):
            cf = ebit_comp or gross_comp
            mname = 'EBIT margin' if ebit_comp else 'Gross margin'
            direction = 'increased' if cogs_drift['shift_pp'] > 0 else 'decreased'
            move = 'compressed' if cf['annual_change_pp'] < 0 else 'expanded'
            sentences.append(
                f"COGS burden {direction} {abs(cogs_drift['shift_pp']):.1f}pp over the "
                f"analysis period while {mname} {move} "
                f"{abs(cf['annual_change_pp']):.1f}pp/year to {cf['current_level']:.1f}% "
                f"— the cost structure is "
                f"{'deteriorating' if cogs_drift['shift_pp'] > 0 else 'improving'}."
            )
        elif cogs_drift:
            direction = 'increased' if cogs_drift['shift_pp'] > 0 else 'decreased'
            sentences.append(
                f"COGS burden {direction} {abs(cogs_drift['shift_pp']):.1f}pp "
                f"({cogs_drift['first_half_avg']:.1f}% → "
                f"{cogs_drift['second_half_avg']:.1f}% of revenue)."
            )
        elif gross_comp or ebit_comp:
            cf = ebit_comp or gross_comp
            mname = 'EBIT margin' if ebit_comp else 'Gross margin'
            move = 'compressing' if cf['annual_change_pp'] < 0 else 'expanding'
            sentences.append(
                f"{mname} is {move} at {abs(cf['annual_change_pp']):.1f}pp/year, "
                f"now at {cf['current_level']:.1f}%."
            )

        # Sentence 2: inflection point from decoupling
        if decouple:
            pf = max(decouple, key=lambda f: abs(f.get('divergence_pp', 0)))
            sentences.append(
                f"A revenue-cost decoupling in {pf['period']} "
                f"(revenue {pf['revenue_change_pct']:+.1f}%, "
                f"COGS {pf['cogs_change_pct']:+.1f}%) marked a key inflection point."
            )

        # Sentence 3: peer context (n=2 absolute-gap findings have gap_pp)
        n2_peers = [f for f in peers if 'gap_pp' in f]
        if n2_peers:
            pf = max(n2_peers, key=lambda f: f.get('gap_pp', 0))
            metric_name = pf['metric'].replace('_pct', '').replace('_', ' ')
            short = company.split()[0]
            sentences.append(
                f"{short} trails its sector peer by {pf['gap_pp']:.0f}pp on "
                f"{metric_name} ({pf['company_value']:.1f}% vs {pf['peer_value']:.1f}%), "
                f"suggesting a structural disadvantage beyond commodity cycle effects."
            )

        if not sentences:
            high_n = sum(1 for f in cfinding if f.get('severity') == 'HIGH')
            sentences.append(
                f"{high_n} high-severity signal(s) detected. "
                f"Review individual findings below for detail."
            )

        narrative_findings.append({
            'company': company,
            'pattern': 'Company Narrative',
            'severity': 'SUMMARY',
            'confidence_score': 'SUMMARY',
            'insight': ' '.join(sentences),
        })

    return narrative_findings


# =============================================================================
# Report Generator
# =============================================================================

def generate_findings_report(
    all_findings: list,
    df: pd.DataFrame,
    quality_stats: dict = None,
    composite_signals: list = None,
    risk_scores: list = None,
):
    """Generate a findings report grouped by company.

    Structure:
        - Data Quality Summary (if quality_stats provided)
        - Company Priority Rankings (if risk_scores provided)
        - Composite Signals (if composite_signals provided)
        - Findings by Company table
        - One section per company: narrative → risk score → composite signals → HIGH/MEDIUM findings
        - Low Confidence Findings (Verify Data) section
        - Summary & Next Steps
    """
    report_path = OUTPUT_DIR / "pattern_discovery_report.md"

    # Exclude SUMMARY/LOW from headline counts
    high_count = sum(
        1 for f in all_findings
        if f.get('severity') == 'HIGH' and f.get('confidence_score') != 'LOW'
    )
    medium_count = sum(
        1 for f in all_findings
        if f.get('severity') == 'MEDIUM' and f.get('confidence_score') != 'LOW'
    )
    low_conf_findings = [f for f in all_findings if f.get('confidence_score') == 'LOW']

    # Group findings by company
    by_company = defaultdict(list)
    for finding in all_findings:
        company = finding.get('company', 'Unknown')
        by_company[company].append(finding)

    severity_emoji = {'HIGH': '🔴', 'MEDIUM': '🟡'}
    skip_keys = {'company', 'pattern', 'insight', 'severity', 'confidence_score'}

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Pattern Discovery Report — Petrochemical Sector\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"**Companies analyzed:** {', '.join(df['DENOM_CIA'].unique())}\n\n")
        f.write(f"**Period:** {df['DT_REFER'].min()} to {df['DT_REFER'].max()}\n\n")
        f.write(
            f"**Total findings:** {high_count + medium_count} actionable "
            f"({high_count} high severity, {medium_count} medium) "
            f"+ {len(low_conf_findings)} low confidence (see bottom)\n\n"
        )
        f.write("---\n\n")

        # Data quality summary
        if quality_stats:
            f.write("## Data Quality Summary\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Raw DRE rows (post-ORDEM_EXERC filter) | {quality_stats.get('rows_raw', 'N/A'):,} |\n")
            f.write(f"| Rows after DFP/ITR dedup | {quality_stats.get('rows_after_dedup', 'N/A'):,} |\n")
            f.write(f"| Duplicates removed | {quality_stats.get('duplicates_removed', 'N/A'):,} |\n")
            f.write(f"| Companies | {', '.join(quality_stats.get('companies', []))} |\n")
            date_range = quality_stats.get('date_range', ('?', '?'))
            f.write(f"| Date range | {date_range[0]} to {date_range[1]} |\n")
            for doc_type, count in quality_stats.get('doc_types', {}).items():
                f.write(f"| {doc_type} periods | {count:,} |\n")
            missing = quality_stats.get('missing_revenue_pct', 0)
            f.write(f"| Missing revenue rows | {missing:.1f}% |\n")
            f.write("\n---\n\n")

        # Macro Environment timeline
        f.write("## Macro Environment\n\n")
        f.write("Key economic events mapped to analysis periods:\n\n")
        f.write("| Period | Event |\n")
        f.write("|--------|-------|\n")
        for period_key, event in MACRO_CONTEXT.items():
            f.write(f"| {period_key} | {event} |\n")
        f.write("\n---\n\n")

        # Company Priority Rankings
        if risk_scores:
            f.write("## Company Priority Rankings\n\n")
            f.write("| Priority | Risk Score | Company | Top Drivers |\n")
            f.write("|----------|-----------|---------|-------------|\n")
            for rs in risk_scores:
                drivers_str = ', '.join(rs.get('top_risk_drivers', []))
                f.write(f"| {rs['priority']} | {rs['risk_score']:.1f} | {rs['company']} | {drivers_str} |\n")
            f.write("\n---\n\n")

        # Composite Signals summary table
        if composite_signals:
            f.write("## Composite Signals\n\n")
            f.write("| Company | Signal Type | Severity | Confidence |\n")
            f.write("|---------|------------|----------|------------|\n")
            for cs in sorted(composite_signals, key=lambda s: (s.get('company', ''), s.get('composite_signal_type', ''))):
                f.write(f"| {cs['company']} | {cs['composite_signal_type']} | {cs['severity']} | {cs['confidence']} |\n")
            f.write("\n---\n\n")

        # Summary table (excludes SUMMARY and LOW confidence)
        f.write("## Findings by Company\n\n")
        f.write("| Company | 🔴 High | 🟡 Medium | Total |\n")
        f.write("|---------|---------|-----------|-------|\n")
        for company in sorted(by_company.keys()):
            actionable = [
                x for x in by_company[company]
                if x.get('severity') not in ('SUMMARY',)
                and x.get('confidence_score') != 'LOW'
            ]
            h = sum(1 for x in actionable if x.get('severity') == 'HIGH')
            m = sum(1 for x in actionable if x.get('severity') == 'MEDIUM')
            f.write(f"| {company} | {h} | {m} | {len(actionable)} |\n")
        f.write("\n---\n\n")

        # Build risk_scores lookup for per-company section
        risk_by_company = {}
        if risk_scores:
            for rs in risk_scores:
                risk_by_company[rs['company']] = rs

        # Build composite_signals lookup for per-company section
        cs_by_company = defaultdict(list)
        if composite_signals:
            for cs in composite_signals:
                cs_by_company[cs['company']].append(cs)

        # One section per company
        for company in sorted(by_company.keys()):
            company_findings = by_company[company]
            f.write(f"## {company}\n\n")

            # Narrative first (blockquote)
            narrative = next(
                (x for x in company_findings if x.get('pattern') == 'Company Narrative'), None
            )
            if narrative:
                f.write(f"> {narrative['insight']}\n\n")

            # Risk score line (after narrative)
            if company in risk_by_company:
                rs = risk_by_company[company]
                f.write(f"**Risk Score:** {rs['risk_score']:.1f}/100 ({rs['priority']}) — {rs['executive_summary']}\n\n")

            # Composite Signals subsection (before individual findings)
            if cs_by_company.get(company):
                f.write("### Composite Signals\n\n")
                for cs in cs_by_company[company]:
                    f.write(f"- **{cs['composite_signal_type']}** ({cs['severity']}, {cs['confidence']} confidence): {cs['explanation']}\n")
                f.write("\n")

            # HIGH/MEDIUM confidence findings only (no SUMMARY, no LOW)
            regular = [
                x for x in company_findings
                if x.get('severity') not in ('SUMMARY',)
                and x.get('confidence_score') != 'LOW'
            ]
            sorted_regular = sorted(
                regular, key=lambda x: 0 if x.get('severity') == 'HIGH' else 1
            )

            for finding in sorted_regular:
                sev  = finding.get('severity', 'MEDIUM')
                conf = finding.get('confidence_score', 'MEDIUM')
                emoji = severity_emoji.get(sev, '⚪')
                f.write(f"### {emoji} {finding['pattern']} ({sev}) [{conf} confidence]\n\n")
                f.write(f"{finding['insight']}\n\n")

                # DQ annotation: show anomaly_type and confidence_reason if present
                atype   = finding.get('anomaly_type', '')
                areason = finding.get('confidence_reason', '')
                if atype:
                    dq_line = f"**DQ:** `{atype}`"
                    if areason:
                        dq_line += f" — {areason}"
                    f.write(f"{dq_line}\n\n")

                data_items = [(k, v) for k, v in finding.items() if k not in skip_keys]
                if data_items:
                    for key, val in data_items:
                        f.write(f"- {key}: {val}\n")
                    f.write("\n")

            f.write("---\n\n")

        # Low confidence section — grouped by anomaly_type with legend
        if low_conf_findings:
            f.write("## Low Confidence Findings (Verify Data)\n\n")
            f.write(
                "These findings triggered detection rules but require verification. "
                "They are grouped by the data quality classification assigned by the DQ layer:\n\n"
            )
            f.write("| Classification | Meaning |\n")
            f.write("|---|---|\n")
            f.write("| `DATA_ISSUE` | Non-standalone (YTD cumulative) row with value outside plausible range — likely pipeline artifact |\n")
            f.write("| `ACCOUNTING_EVENT` | Standalone row with implausible value — may be legitimate one-time item (impairment, restatement) |\n")
            f.write("| `LOW_CONFIDENCE_SIGNAL` | Isolated spike with no adjacent persistence or peer confirmation — needs context |\n")
            f.write("| `EVENT_DRIVEN_BUT_PLAUSIBLE` | Peer-confirmed in same period — likely industry-wide event, still verify |\n")
            f.write("\n")

            # Group by anomaly_type, then by company within each group.
            # Any unknown/legacy type (e.g. old taxonomy strings) lands in UNCLASSIFIED.
            known_atypes = {'DATA_ISSUE', 'ACCOUNTING_EVENT', 'LOW_CONFIDENCE_SIGNAL',
                            'EVENT_DRIVEN_BUT_PLAUSIBLE'}
            by_atype: dict = defaultdict(list)
            for finding in low_conf_findings:
                atype = finding.get('anomaly_type') or ''
                bucket = atype if atype in known_atypes else 'UNCLASSIFIED'
                by_atype[bucket].append(finding)

            # Deterministic order
            atype_order = ['DATA_ISSUE', 'ACCOUNTING_EVENT', 'LOW_CONFIDENCE_SIGNAL',
                           'EVENT_DRIVEN_BUT_PLAUSIBLE', 'UNCLASSIFIED']
            for atype in atype_order:
                group = by_atype.get(atype, [])
                if not group:
                    continue
                f.write(f"### {atype} ({len(group)})\n\n")
                by_company_low: dict = defaultdict(list)
                for finding in group:
                    by_company_low[finding.get('company', 'Unknown')].append(finding)
                for company in sorted(by_company_low.keys()):
                    f.write(f"**{company}**\n\n")
                    for finding in by_company_low[company]:
                        reason = finding.get('confidence_reason', '')
                        reason_str = f" *(DQ: {reason})*" if reason else ""
                        f.write(f"- **{finding['pattern']}**: {finding['insight']}{reason_str}\n")
                    f.write("\n")
            f.write("---\n\n")

        # Summary & Next Steps
        f.write("## Summary & Next Steps\n\n")
        f.write("These findings are based on public financial data (CVM/B3 filings). ")
        f.write("Key limitations of public data:\n\n")
        f.write("- Account-level detail only (no sub-ledger or cost center breakdown)\n")
        f.write("- Quarterly granularity (monthly patterns invisible)\n")
        f.write("- Consolidated view (subsidiary-level patterns hidden)\n")
        f.write("- No operational KPIs (production volumes, utilization rates)\n\n")
        f.write("**What internal data would unlock:**\n\n")
        f.write("- Cost center level decomposition of COGS\n")
        f.write("- Material cost vs labor vs overhead split\n")
        f.write("- Product line profitability\n")
        f.write("- Plant-level efficiency metrics\n")
        f.write("- Monthly seasonality patterns\n")
        f.write("- Transfer pricing between business units\n\n")
        f.write("*This is the gap between Layer 1 (what public data shows) and ")
        f.write("Layer 2 (what internal data reveals). The real value is in Layer 2.*\n")

    print(f"\n  Report saved: {report_path}")

    # Also save findings as structured CSV for further analysis
    if all_findings:
        findings_df = pd.DataFrame(all_findings)
        findings_csv = OUTPUT_DIR / "findings_structured.csv"
        findings_df.to_csv(findings_csv, index=False, encoding='utf-8-sig')
        print(f"  Structured findings: {findings_csv}")

    return report_path


# =============================================================================
# Post-processing helpers
# =============================================================================

def _cap_company_findings(
    findings: list, max_per_company: int, magnitude_key: str = None
) -> list:
    """Keep at most max_per_company findings per company, HIGH severity first."""
    by_company = defaultdict(list)
    for f in findings:
        by_company[f.get('company', '')].append(f)
    result = []
    for company_findings in by_company.values():
        sorted_f = sorted(
            company_findings,
            key=lambda f: (
                0 if f.get('severity') == 'HIGH' else 1,
                -abs(f.get(magnitude_key, 0)) if magnitude_key else 0,
            ),
        )
        result.extend(sorted_f[:max_per_company])
    return result


def _add_confidence_scores(findings: list) -> list:
    """Add confidence_score to non-anomaly findings based on magnitude vs. detection threshold."""
    THRESHOLDS = {
        'Margin compression':       ('annual_change_pp', 2.0),
        'Margin expansion':         ('annual_change_pp', 2.0),
        'High margin volatility':   ('volatility',       5.0),
        'Cost composition drift':   ('shift_pp',         3.0),
        'Revenue-cost decoupling':  ('divergence_pp',   10.0),
        'YoY quarter comparison':   ('yoy_change_pp',   15.0),
    }
    for f in findings:
        if 'confidence_score' in f:   # Statistical anomaly already classified inline
            continue
        pattern = f.get('pattern', '')
        if pattern in THRESHOLDS:
            key, base = THRESHOLDS[pattern]
            ratio = abs(f.get(key, 0) or 0) / base
        elif pattern == 'Peer divergence':
            gap = f.get('gap_pp')
            z   = f.get('z_score')
            if gap is not None:
                base = 10.0 if 'Margin' in f.get('metric', '') else 15.0
                ratio = gap / base
            elif z is not None:
                ratio = abs(z)   # detection threshold is 1.0
            else:
                ratio = 1.0
        elif pattern == 'Potential cost reclassification':
            ratio = abs(f.get('correlation', 0)) / 0.5   # base threshold is -0.5
        else:
            f['confidence_score'] = 'MEDIUM'
            continue
        f['confidence_score'] = 'HIGH' if ratio >= 2.0 else ('LOW' if ratio < 1.3 else 'MEDIUM')

        # DQ override: DATA_ISSUE forces LOW; ACCOUNTING_EVENT caps at MEDIUM.
        # Applied after ratio-based scoring so DQ classification always wins.
        anomaly = f.get('anomaly_type', '')
        if anomaly == 'DATA_ISSUE':
            f['confidence_score'] = 'LOW'
        elif anomaly == 'ACCOUNTING_EVENT' and f.get('confidence_score') == 'HIGH':
            f['confidence_score'] = 'MEDIUM'

    return findings


def _dedup_yoy_vs_anomalies(all_findings: list) -> list:
    """Drop YoY findings that duplicate a Statistical anomaly for the same company+period."""
    anomaly_keys = set()
    for f in all_findings:
        if f.get('pattern') == 'Statistical anomaly':
            try:
                dt = pd.to_datetime(f['period'])
                anomaly_keys.add((f['company'], dt.year, dt.quarter))
            except Exception:
                pass
    result = []
    for f in all_findings:
        if f.get('pattern') == 'YoY quarter comparison':
            try:
                parts = f['period'].split()   # "Q3 2024" → ['Q3', '2024']
                q, yr = int(parts[0][1:]), int(parts[1])
                if (f['company'], yr, q) in anomaly_keys:
                    continue
            except Exception:
                pass
        result.append(f)
    return result


def _add_macro_context_to_findings(findings: list) -> list:
    """Append macro context to insights for period-specific findings."""
    period_patterns = {'Revenue-cost decoupling', 'Statistical anomaly', 'YoY quarter comparison'}
    for f in findings:
        if f.get('pattern') not in period_patterns:
            continue
        ctx = _get_macro_context(str(f.get('period', '')))
        if ctx:
            f['insight'] = f"{f['insight']} [Macro context: {ctx}]"
            f['macro_context'] = ctx
    return findings


# Templates for confidence_reason field, keyed on anomaly_type
_CONFIDENCE_REASON_TEMPLATES = {
    'DATA_ISSUE':                 'Non-standalone row; {metric}={value:.1f} outside plausible range {lo:.0f}–{hi:.0f}',
    'ACCOUNTING_EVENT':           'Standalone row; {metric}={value:.1f} outside plausible range {lo:.0f}–{hi:.0f} — possible one-time item',
    'VALID_SIGNAL':               'Adjacent periods also anomalous — consistent structural pattern',
    'EVENT_DRIVEN_BUT_PLAUSIBLE': 'Peer confirmation in same period — likely industry-wide event',
    'LOW_CONFIDENCE_SIGNAL':      'Isolated spike; no adjacent persistence or peer confirmation',
}

# Patterns that carry a specific `period` field parseable as a date / quarter string
_PERIOD_SPECIFIC_PATTERNS = {'Statistical anomaly', 'YoY quarter comparison', 'Revenue-cost decoupling'}


def _enrich_findings_with_dq(findings: list, df: pd.DataFrame) -> None:
    """Enrich every finding in-place with `anomaly_type`, `confidence_reason`,
    and (for DATA_ISSUE) a downgraded `confidence_score`.

    The df must already have `_row_confidence` and `is_standalone` columns
    (i.e. validate_metric_ranges + assign_data_confidence must have been called first).

    Algorithm:
    - Period-specific findings (Statistical anomaly, YoY, Revenue-cost decoupling):
        1. Parse period → look up the matching df row for company + period
        2. Read is_standalone and _row_confidence from that row
        3. adjacent_periods_anomalous: True if another finding for the same
           company + metric exists within 2 quarters of this finding's date
        4. has_peer_confirmation: True if ≥ 1 other company has a finding for the
           same metric within the same calendar year
        5. Call classify_anomaly_type() to get anomaly_type
        6. Build confidence_reason from template
    - Non-period findings (Margin trends, Cost drift, Peer comparison, etc.):
        1. If the company has any _row_confidence == 'LOW' rows → LOW_CONFIDENCE_SIGNAL
        2. Otherwise → VALID_SIGNAL
    """
    # Pre-compute: set of (company, metric, period_date) for period-specific findings
    # to support adjacent-period and peer-confirmation lookups
    period_finding_dates: dict[tuple, list[pd.Timestamp]] = defaultdict(list)
    for f in findings:
        if f.get('pattern') not in _PERIOD_SPECIFIC_PATTERNS:
            continue
        try:
            period_str = str(f.get('period', ''))
            if 'Q' in period_str:
                parts = period_str.split()
                q, yr = int(parts[0][1:]), int(parts[1])
                month = q * 3
                dt = pd.Timestamp(f'{yr}-{month:02d}-01') + pd.offsets.MonthEnd(0)
            else:
                dt = pd.to_datetime(period_str)
            period_finding_dates[(f['company'], f.get('metric', ''))].append(dt)
        except Exception:
            pass

    # Pre-compute: which companies have _row_confidence == 'LOW'
    if '_row_confidence' in df.columns:
        low_conf_companies = set(
            df.loc[df['_row_confidence'] == 'LOW', 'DENOM_CIA'].unique()
        )
    else:
        low_conf_companies = set()

    for f in findings:
        company   = f.get('company', '')
        metric    = f.get('metric', '')
        pattern   = f.get('pattern', '')

        # ------------------------------------------------------------------ #
        # Non-period findings: trend / peer / volatility patterns             #
        # ------------------------------------------------------------------ #
        if pattern not in _PERIOD_SPECIFIC_PATTERNS:
            if company in low_conf_companies:
                f['anomaly_type']      = 'LOW_CONFIDENCE_SIGNAL'
                f['confidence_reason'] = 'Company has data rows with low plausibility confidence'
            else:
                f['anomaly_type']      = 'VALID_SIGNAL'
                f['confidence_reason'] = 'Trend analysis on plausible data'
            continue

        # ------------------------------------------------------------------ #
        # Period-specific findings                                             #
        # ------------------------------------------------------------------ #
        period_str = str(f.get('period', ''))
        value      = f.get('value', 0.0) or 0.0

        # Parse the finding's period to a Timestamp
        try:
            if 'Q' in period_str:
                parts = period_str.split()
                q, yr = int(parts[0][1:]), int(parts[1])
                month = q * 3
                finding_dt = pd.Timestamp(f'{yr}-{month:02d}-01') + pd.offsets.MonthEnd(0)
            else:
                finding_dt = pd.to_datetime(period_str)
        except Exception:
            # Cannot parse period — fall back to non-standalone VALID_SIGNAL
            f.setdefault('anomaly_type', 'LOW_CONFIDENCE_SIGNAL')
            f.setdefault('confidence_reason', 'Period could not be parsed for DQ lookup')
            continue

        # Look up the matching df row for is_standalone
        is_standalone = True   # default if not found
        if 'DT_REFER' in df.columns and 'DENOM_CIA' in df.columns:
            mask = (df['DENOM_CIA'] == company) & (
                pd.to_datetime(df['DT_REFER'], errors='coerce') == finding_dt
            )
            matched = df[mask]
            if not matched.empty and 'is_standalone' in matched.columns:
                is_standalone = bool(matched['is_standalone'].iloc[0])

        # Adjacent-period check: another finding for same company + metric within 2 quarters
        key = (company, metric)
        sibling_dates = [d for d in period_finding_dates.get(key, []) if d != finding_dt]
        adjacent_periods_anomalous = any(
            abs((d - finding_dt).days) <= 95   # ~2 quarters = ~184 days; use 95 (~1 quarter) to be conservative
            for d in sibling_dates
        )

        # Peer confirmation: ≥ 1 other company has a finding for same metric in same year
        finding_year = finding_dt.year
        has_peer_confirmation = any(
            comp != company
            for (comp, m), dates in period_finding_dates.items()
            if m == metric and any(d.year == finding_year for d in dates)
        )

        # Classify
        anomaly_type = classify_anomaly_type(
            value, metric, 0.0, 0.0,   # normal_low/high unused — function uses PLAUSIBILITY_THRESHOLDS
            is_standalone=is_standalone,
            has_peer_confirmation=has_peer_confirmation,
            adjacent_periods_anomalous=adjacent_periods_anomalous,
        )

        # Build confidence_reason
        tpl = _CONFIDENCE_REASON_TEMPLATES.get(anomaly_type, anomaly_type)
        thresholds = PLAUSIBILITY_THRESHOLDS.get(metric, (0.0, 0.0))
        lo, hi = thresholds
        try:
            reason = tpl.format(metric=metric, value=value, lo=lo, hi=hi)
        except (KeyError, ValueError):
            reason = tpl

        f['anomaly_type']      = anomaly_type
        f['confidence_reason'] = reason

        # Force confidence_score to LOW for DATA_ISSUE findings
        if anomaly_type == 'DATA_ISSUE':
            f['confidence_score'] = 'LOW'


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Pattern Discovery — EBITDA Driver Decomposition")
    print(f"Run date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Load the analysis data
    analysis_file = ANALYSIS_DIR / "ebitda_driver_analysis.csv"

    if not analysis_file.exists():
        print("\n  Error: Analysis file not found.")
        print("  Run 01_download_and_parse.py first.")
        exit(1)

    df = pd.read_csv(analysis_file)
    print(f"\n  Loaded {len(df)} rows for {df['DENOM_CIA'].nunique()} companies")

    # Split by period type — mixing annual and quarterly data in the same time
    # series inflates period-over-period changes and masks real trends.
    df['period_type'] = df['_doc_type'].map({'DFP': 'annual', 'ITR': 'quarterly'})
    df_annual = df[df['_doc_type'] == 'DFP'].copy()
    df_quarterly = df[df['_doc_type'] == 'ITR'].copy()
    print(f"  Annual (DFP): {len(df_annual)} rows | Quarterly (ITR): {len(df_quarterly)} rows")

    # Filter quarterly data to standalone-only rows (YTD cumulative rows excluded)
    if 'is_standalone' in df_quarterly.columns:
        df_quarterly = df_quarterly[df_quarterly['is_standalone'] == True].copy()
        print(f"  Standalone quarterly rows: {len(df_quarterly)}")

    # Load quality stats if available (written by 01_download_and_parse.py)
    quality_stats = None
    quality_stats_path = ANALYSIS_DIR / "quality_stats.json"
    if quality_stats_path.exists():
        try:
            with open(quality_stats_path) as qf:
                quality_stats = json.load(qf)
            quality_stats['date_range'] = tuple(quality_stats['date_range'])
        except (json.JSONDecodeError, KeyError):
            quality_stats = None

    # Enrich df with plausibility flags and row-level confidence BEFORE pattern detection.
    # This adds _plausibility_flags, _has_plausibility_issue, and _row_confidence to df,
    # which _enrich_findings_with_dq() uses after all patterns are detected.
    df = validate_metric_ranges(df)
    df = assign_data_confidence(df)

    # Run all pattern detection (cap at 5 findings per company per pattern)
    all_findings = []

    print("\n  Running Pattern 1: Margin Trend Analysis (annual)...")
    p1 = analyze_margin_trends(df_annual, periods_per_year=1)
    all_findings.extend(_cap_company_findings(p1, 2, 'annual_change_pp'))

    print("  Running Pattern 2: Cost Composition Drift (annual)...")
    p2 = analyze_cost_drift(df_annual)
    all_findings.extend(_cap_company_findings(p2, 5, 'shift_pp'))

    print("  Running Pattern 3: Revenue-Cost Decoupling (annual)...")
    p3 = analyze_revenue_cost_decoupling(df_annual)
    all_findings.extend(_cap_company_findings(p3, 2, 'divergence_pp'))

    print("  Running Pattern 4: Peer Comparison (sector-based, latest period)...")
    p4 = analyze_peer_comparison(df, sector_map=SECTOR_MAP)
    all_findings.extend(_cap_company_findings(p4, 5, 'gap_pp'))

    print("  Running Pattern 5: Anomaly Detection (quarterly)...")
    p5 = detect_anomalies(df_quarterly)
    all_findings.extend(_cap_company_findings(p5, 2))

    print("  Running Pattern 6: YoY Quarter Comparison (quarterly)...")
    p6 = analyze_yoy_comparison(df_quarterly, max_findings_per_company=3)
    all_findings.extend(_cap_company_findings(p6, 3, 'yoy_change_pp'))

    # Post-processing: remove YoY findings that duplicate anomaly findings
    all_findings = _dedup_yoy_vs_anomalies(all_findings)

    # Add confidence scores
    _add_confidence_scores(all_findings)

    # Append macro context to period-specific findings
    _add_macro_context_to_findings(all_findings)

    # Enrich every finding with anomaly_type, confidence_reason, and DQ-adjusted confidence_score.
    # Must run after _add_confidence_scores so the DQ override in _add_confidence_scores applies,
    # and after validate_metric_ranges / assign_data_confidence (already called above).
    _enrich_findings_with_dq(all_findings, df)

    # Build composite signals
    composite_signals = build_composite_signals(all_findings, df)
    print(f"\n  Composite signals: {len(composite_signals)} across {len({s['company'] for s in composite_signals})} companies")
    if composite_signals:
        cs_df = pd.DataFrame(composite_signals)
        cs_path = OUTPUT_DIR / "composite_signals.csv"
        cs_df.to_csv(cs_path, index=False, encoding='utf-8-sig')
        print(f"  Saved: {cs_path.name}")
        for sig in sorted(composite_signals, key=lambda s: s['company']):
            print(f"    {sig['company'].split()[0]}: {sig['composite_signal_type']} ({sig['confidence']})")

    # Score company risk
    by_company_findings = defaultdict(list)
    for f in all_findings:
        by_company_findings[f.get('company', '')].append(f)

    risk_scores = []
    for company in sorted(df['DENOM_CIA'].unique()):
        score = score_company_risk(
            company,
            by_company_findings.get(company, []),
            composite_signals,
            df,
        )
        risk_scores.append(score)
    risk_scores.sort(key=lambda s: s['risk_score'], reverse=True)

    if risk_scores:
        rs_df = pd.DataFrame([{
            'company': s['company'],
            'risk_score': s['risk_score'],
            'priority': s['priority'],
            'top_drivers': ' | '.join(s['top_risk_drivers']),
            'composite_signals': ' | '.join(s['composite_signal_types']),
            'executive_summary': s['executive_summary'],
        } for s in risk_scores])
        rs_path = OUTPUT_DIR / "company_risk_scores.csv"
        rs_df.to_csv(rs_path, index=False, encoding='utf-8-sig')
        print(f"\n  Company risk scores saved: {rs_path.name}")
        print("\n  Risk Priority Ranking:")
        for s in risk_scores:
            print(f"    {s['priority']:8s} ({s['risk_score']:5.1f}/100) — {s['company']}")

    # Synthesize per-company narratives
    narratives = synthesize_company_narratives(all_findings, df)
    all_findings.extend(narratives)

    actionable = [f for f in all_findings if f.get('severity') not in ('SUMMARY',)]
    low_conf = [f for f in actionable if f.get('confidence_score') == 'LOW']
    print(f"\n  Total findings: {len(actionable)} actionable "
          f"({len(actionable) - len(low_conf)} high/medium confidence, "
          f"{len(low_conf)} low confidence)")

    # Generate report
    report_path = generate_findings_report(
        all_findings, df,
        quality_stats=quality_stats,
        composite_signals=composite_signals,
        risk_scores=risk_scores,
    )

    print("\n" + "=" * 60)
    print("Pattern discovery complete.")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Review data/findings/pattern_discovery_report.md")
    print("  2. Bring findings to Claude for interpretation and storytelling")
    print("  3. Build presentation around the most compelling findings")
