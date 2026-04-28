"""Pattern detector — data quality layer and 6 pattern detection algorithms.

All analytical logic is ported verbatim from 02_pattern_discovery.py.
Thresholds, rules, and detection logic are unchanged.

Public API
----------
quality_scan(df) -> dict
    Step 5: validate metric ranges, assign row confidence, return quality summary.
    Saves data/analysis/enriched_{key}.csv with plausibility flag columns.

detect_patterns(df, df_annual, df_quarterly, sector_map) -> list
    Step 6: run all 6 pattern algorithms and post-processing, return findings list.
"""

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# Data Quality Layer
# =============================================================================

# Plausibility thresholds for industrial/petrochemical sectors
PLAUSIBILITY_THRESHOLDS = {
    "Gross_Margin_pct":  (-50.0,  80.0),
    "EBIT_Margin_pct":   (-50.0,  60.0),
    "COGS_pct_Revenue":  ( 20.0, 130.0),
    "SGA_pct_Revenue":   (  0.0,  40.0),
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
        flags_list.append(";".join(issues))
    df["_plausibility_flags"] = flags_list
    df["_has_plausibility_issue"] = df["_plausibility_flags"].apply(lambda x: x != "")
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
        return "DATA_ISSUE"

    # Rule 2: adjacent periods also anomalous → persistent structural pattern, regardless of
    # whether the individual value is plausible
    if adjacent_periods_anomalous:
        return "VALID_SIGNAL"

    # Rule 3: peer confirmation → likely industry-wide event
    if has_peer_confirmation:
        return "EVENT_DRIVEN_BUT_PLAUSIBLE"

    # Rule 4: standalone row outside plausibility → possible one-time accounting item
    if outside_range:
        return "ACCOUNTING_EVENT"

    # Rule 5: isolated, within plausibility range, no confirmation
    return "LOW_CONFIDENCE_SIGNAL"


# Backward-compat alias (kept for existing tests and external callers)
classify_anomaly_type_dq = classify_anomaly_type


def assign_data_confidence(df: pd.DataFrame) -> pd.DataFrame:
    """Add _row_confidence column based on plausibility issues.

    Calls validate_metric_ranges if not already done.
    Returns enriched df.
    """
    if "_has_plausibility_issue" not in df.columns:
        df = validate_metric_ranges(df)

    # Determine standalone: use is_standalone column if present, else assume True
    if "is_standalone" in df.columns:
        is_standalone_series = df["is_standalone"].fillna(True).astype(bool)
    else:
        is_standalone_series = pd.Series([True] * len(df), index=df.index)

    def _conf(row, is_standalone):
        if not row["_has_plausibility_issue"]:
            return "HIGH"
        if is_standalone:
            return "MEDIUM"
        return "LOW"

    df = df.copy()
    df["_row_confidence"] = [
        _conf(row, is_standalone_series.iloc[i])
        for i, (_, row) in enumerate(df.iterrows())
    ]
    return df


# =============================================================================
# Pattern 1: Margin Trend Analysis
# =============================================================================

def analyze_margin_trends(df: pd.DataFrame, periods_per_year: int = 4) -> list:
    """Detect sustained margin compression or expansion."""
    findings = []

    for company in df["company_id"].unique():
        comp = df[df["company_id"] == company].sort_values("period_date").copy()

        if len(comp) < 4:
            continue

        for margin_col in ["Gross_Margin_pct", "EBIT_Margin_pct"]:
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
                direction_pt = "compressão" if annual_change < 0 else "expansão"
                metric_label = margin_col.replace('_pct', '')
                _urgent_en = 'This rate is unsustainable and warrants investigation.' if abs(annual_change) > 5 else 'Monitor closely.'
                _urgent_pt = 'Essa taxa é insustentável e requer investigação.' if abs(annual_change) > 5 else 'Monitorar de perto.'
                findings.append({
                    "company": company,
                    "metric": margin_col,
                    "pattern": f"Margin {direction}",
                    "annual_change_pp": round(annual_change, 2),
                    "current_level": round(series.iloc[-1], 2),
                    "volatility": round(volatility, 2),
                    "periods_analyzed": len(series),
                    "severity": "HIGH" if abs(annual_change) > 5 else "MEDIUM",
                    "insight": (
                        f"{company}: {metric_label} shows "
                        f"{direction} of {abs(annual_change):.1f}pp/year. "
                        f"Current: {series.iloc[-1]:.1f}%, "
                        f"Historical avg: {historical_avg:.1f}%. "
                        f"{_urgent_en}"
                    ),
                    "description_pt": (
                        f"{company}: {metric_label} apresenta {direction_pt} de "
                        f"{abs(annual_change):.1f}pp/ano. "
                        f"Atual: {series.iloc[-1]:.1f}%, "
                        f"Média histórica: {historical_avg:.1f}%. "
                        f"{_urgent_pt}"
                    ),
                })

            # Flag high volatility
            if volatility > 5:
                metric_label = margin_col.replace('_pct', '')
                findings.append({
                    "company": company,
                    "metric": margin_col,
                    "pattern": "High margin volatility",
                    "volatility": round(volatility, 2),
                    "min": round(series.min(), 2),
                    "max": round(series.max(), 2),
                    "range": round(series.max() - series.min(), 2),
                    "severity": "MEDIUM",
                    "insight": (
                        f"{company}: {metric_label} swings "
                        f"from {series.min():.1f}% to {series.max():.1f}% "
                        f"(range: {series.max() - series.min():.1f}pp). "
                        f"High volatility suggests exposure to commodity cycles "
                        f"or pricing power issues."
                    ),
                    "description_pt": (
                        f"{company}: {metric_label} oscila de {series.min():.1f}% a "
                        f"{series.max():.1f}% (amplitude: {series.max() - series.min():.1f}pp). "
                        f"Alta volatilidade sugere exposição a ciclos de commodities "
                        f"ou problemas de poder de precificação."
                    ),
                })

            # Consecutive decline streak (from most recent backward)
            vals = series.values
            streak = 0
            for i in range(len(vals) - 1, 0, -1):
                if vals[i] < vals[i - 1]:
                    streak += 1
                else:
                    break

            if streak >= 3:
                metric_label = margin_col.replace('_pct', '')
                decline_start_idx = len(vals) - 1 - streak
                try:
                    decline_start_year = str(series.index[decline_start_idx])[:4]
                except Exception:
                    decline_start_year = ""
                total_decline_pp = float(vals[decline_start_idx] - vals[-1])
                streak_severity = "HIGH" if streak >= 4 else "MEDIUM"
                streak_label_en = "Persistent" if streak >= 4 else "Sustained"
                streak_label_pt = "Persistente" if streak >= 4 else "Contínua"
                findings.append({
                    "company": company,
                    "metric": margin_col,
                    "pattern": f"Persistent margin decline" if streak >= 4 else "Sustained margin decline",
                    "consecutive_decline_periods": streak,
                    "decline_start_year": decline_start_year,
                    "total_decline_pp": round(total_decline_pp, 2),
                    "severity": streak_severity,
                    "insight": (
                        f"{company}: {metric_label} declined for {streak} consecutive years "
                        f"(−{total_decline_pp:.1f}pp total since {decline_start_year}). "
                        f"Persistent structural deterioration."
                    ),
                    "description_pt": (
                        f"{company}: {metric_label} caiu por {streak} anos consecutivos "
                        f"(−{total_decline_pp:.1f}pp no total desde {decline_start_year}). "
                        f"Deterioração estrutural persistente."
                    ),
                })

    return findings


# =============================================================================
# Pattern 2: Cost Composition Drift
# =============================================================================

def analyze_cost_drift(df: pd.DataFrame) -> list:
    """Detect changes in cost structure that aren't explained by revenue changes."""
    findings = []

    cost_cols = [
        ("COGS_pct_Revenue", "COGS"),
        ("SGA_pct_Revenue", "SG&A"),
        ("Selling_pct_Revenue", "Selling Expenses"),
    ]

    for company in df["company_id"].unique():
        comp = df[df["company_id"] == company].sort_values("period_date").copy()

        if len(comp) < 4:
            continue

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
                is_deterioration = shift > 0
                econ_label    = "deterioration" if is_deterioration else "improvement"
                econ_label_pt = "deterioração"  if is_deterioration else "melhora"
                _cogs_cause_en  = "input costs, product mix, or operational efficiency"
                _cogs_cause_pt  = "custos de insumos, mix de produtos ou eficiência operacional"
                _other_cause_en = "organizational structure or cost allocation methodology"
                _other_cause_pt = "estrutura organizacional ou metodologia de alocação de custos"
                cause_en = _cogs_cause_en  if name == "COGS" else _other_cause_en
                cause_pt = _cogs_cause_pt  if name == "COGS" else _other_cause_pt

                # Direction-aware severity: improvements are demoted one level
                base_severity = "HIGH" if abs(shift) > 5 else "MEDIUM"
                if is_deterioration:
                    severity = base_severity
                else:
                    severity = "MEDIUM" if base_severity == "HIGH" else "LOW"

                findings.append({
                    "company": company,
                    "metric": col,
                    "pattern": "Cost composition drift",
                    "direction": "deteriorating" if is_deterioration else "improving",
                    "first_half_avg": round(first_half, 2),
                    "second_half_avg": round(second_half, 2),
                    "shift_pp": round(shift, 2),
                    "severity": severity,
                    "insight": (
                        f"{company}: {name} burden shifted from {first_half:.1f}% to "
                        f"{second_half:.1f}% of revenue — a {abs(shift):.1f}pp {econ_label}. "
                        f"This structural shift may indicate changes in {cause_en}."
                    ),
                    "description_pt": (
                        f"{company}: {name} variou de {first_half:.1f}% para "
                        f"{second_half:.1f}% da receita — uma {econ_label_pt} de {abs(shift):.1f}pp. "
                        f"Essa mudança estrutural pode indicar alterações em {cause_pt}."
                    ),
                })

        # Check for cost transfer between categories
        # (One goes up while another goes down = potential reclassification)
        if len(available_costs) >= 2:
            for i, (col1, name1) in enumerate(available_costs):
                for col2, name2 in available_costs[i + 1:]:
                    s1 = comp[col1].dropna()
                    s2 = comp[col2].dropna()

                    if len(s1) < 4 or len(s2) < 4:
                        continue

                    # Check correlation — negative correlation suggests transfer
                    if len(s1) == len(s2):
                        corr = s1.corr(s2)
                        if corr < -0.5:
                            findings.append({
                                "company": company,
                                "pattern": "Potential cost reclassification",
                                "categories": f"{name1} ↔ {name2}",
                                "correlation": round(corr, 3),
                                "severity": "HIGH",
                                "insight": (
                                    f"{company}: {name1} and {name2} show strong "
                                    f"negative correlation ({corr:.2f}), suggesting "
                                    f"costs may be shifting between categories. "
                                    f"This could indicate accounting reclassification "
                                    f"or genuine operational changes worth investigating."
                                ),
                                "description_pt": (
                                    f"{company}: {name1} e {name2} apresentam forte correlação "
                                    f"negativa ({corr:.2f}), sugerindo que os custos podem estar "
                                    f"sendo transferidos entre categorias. Isso pode indicar "
                                    f"reclassificação contábil ou mudanças operacionais genuínas "
                                    f"que merecem investigação."
                                ),
                            })

    return findings


# =============================================================================
# Pattern 3: Revenue-Cost Decoupling
# =============================================================================

def analyze_revenue_cost_decoupling(df: pd.DataFrame) -> list:
    """Detect periods where costs don't move proportionally with revenue."""
    findings = []

    # Support both common model column names and legacy CVM Portuguese names
    revenue_col = "revenue" if "revenue" in df.columns else "Receita de Venda de Bens e/ou Serviços"
    cogs_col    = "cogs"    if "cogs"    in df.columns else "Custo dos Bens e/ou Serviços Vendidos"

    if revenue_col not in df.columns or cogs_col not in df.columns:
        return findings

    for company in df["company_id"].unique():
        comp = df[df["company_id"] == company].sort_values("period_date").copy()

        if len(comp) < 4:
            continue

        revenue = comp[revenue_col].dropna()
        # cogs column stores absolute values in common model; legacy stores negative values
        cogs    = comp[cogs_col].dropna().abs()

        if len(revenue) < 4 or len(cogs) < 4:
            continue

        # Compute period-over-period changes
        rev_pct_change  = revenue.pct_change().dropna()
        cogs_pct_change = cogs.pct_change().dropna()

        # Find periods where revenue and COGS diverge significantly
        if len(rev_pct_change) == len(cogs_pct_change):
            delta = (cogs_pct_change.values - rev_pct_change.values) * 100

            # Flag periods with >10pp divergence
            anomalous_periods = np.where(np.abs(delta) > 10)[0]

            if len(anomalous_periods) > 0:
                for idx in anomalous_periods:
                    period_idx = rev_pct_change.index[idx]
                    date = comp.loc[period_idx, "period_date"] if period_idx in comp.index else "Unknown"
                    rev_chg  = rev_pct_change.iloc[idx] * 100
                    cogs_chg = cogs_pct_change.iloc[idx] * 100

                    _pressure_en = "COGS grew faster than revenue (margin pressure)" if delta[idx] > 0 else "Revenue outpaced COGS (margin expansion)"
                    _pressure_pt = "CPV cresceu mais que a receita (pressão de margem)" if delta[idx] > 0 else "Receita superou o CPV (expansão de margem)"
                    findings.append({
                        "company": company,
                        "pattern": "Revenue-cost decoupling",
                        "period": str(date),
                        "revenue_change_pct": round(rev_chg, 1),
                        "cogs_change_pct": round(cogs_chg, 1),
                        "divergence_pp": round(delta[idx], 1),
                        "severity": "HIGH" if abs(delta[idx]) > 20 else "MEDIUM",
                        "insight": (
                            f"{company} ({date}): Revenue changed {rev_chg:+.1f}% "
                            f"but COGS changed {cogs_chg:+.1f}% — "
                            f"a {abs(delta[idx]):.1f}pp divergence. "
                            f"{_pressure_en}. "
                            f"Investigate: product mix shift, input cost changes, "
                            f"or one-time items."
                        ),
                        "description_pt": (
                            f"{company} ({date}): Receita variou {rev_chg:+.1f}% "
                            f"enquanto o CPV variou {cogs_chg:+.1f}% — "
                            f"uma divergência de {abs(delta[idx]):.1f}pp. "
                            f"{_pressure_pt}. "
                            f"Investigar: mudança no mix de produtos, variação nos custos de "
                            f"insumos ou itens extraordinários."
                        ),
                    })

    return findings


# =============================================================================
# Pattern 4: (removed — peer comparison with n=2 produces more noise than signal)
# =============================================================================

# Placeholder kept for historical reference; function is not called from detect_patterns.
def _analyze_peer_comparison_removed(df: pd.DataFrame, sector_map: dict = None) -> list:  # noqa: F401
    """Removed: cross-company comparison with typical n=2 produces z-scores of ±0.71
    regardless of gap size, making sector sector groupings unreliable.
    """
    return []


def _unused_get_sector(company_name: str, sector_map: dict) -> str:
    """Helper kept for internal reference; not called."""
    if sector_map:
        for fragment, sector in sector_map.items():
            if fragment.upper() in company_name.upper():
                return sector
    return "All"


def _unused_peer_block_removed() -> list:  # noqa: F401
    """Stub placeholder — old peer comparison logic removed in Change 1.

    The old function body included:
        - n=2 absolute gap comparisons with threshold 10pp (margins) / 15pp (costs)
        - n≥3 z-score comparisons flagging |z| > 1
    Removed because n=2 always produces z=±0.71, making severity thresholds meaningless,
    and CVM sector groupings mix fundamentally different business models.
    """
    return []


# =============================================================================
# Pattern 5: Anomaly Detection (Statistical Outliers)
# =============================================================================

def detect_anomalies(df: pd.DataFrame) -> list:
    """Flag individual data points that are statistical outliers (IQR method)."""
    findings = []

    metric_cols = ["Gross_Margin_pct", "EBIT_Margin_pct", "COGS_pct_Revenue"]
    available_metrics = [col for col in metric_cols if col in df.columns]

    for company in df["company_id"].unique():
        comp = df[df["company_id"] == company].sort_values("period_date").reset_index(drop=True)

        for metric in available_metrics:
            series = comp[metric].dropna()
            if len(series) < 6:
                continue

            q1  = series.quantile(0.25)
            q3  = series.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            # Identify outlier positions for neighbor-aware classification
            is_outlier = comp[metric].notna() & (
                (comp[metric] < lower) | (comp[metric] > upper)
            )
            outlier_idxs = set(comp[is_outlier].index.tolist())

            for pos in sorted(outlier_idxs):
                row   = comp.iloc[pos]
                value = row[metric]

                # Rule 1: physically impossible value → data issue (pre-enrichment classification)
                if metric in ("Gross_Margin_pct", "COGS_pct_Revenue") and value > 100:
                    anomaly_type    = "DATA_ISSUE"
                    confidence_score = "LOW"
                # Rule 2: adjacent period also an outlier → persistent structural shift
                elif (pos - 1) in outlier_idxs or (pos + 1) in outlier_idxs:
                    anomaly_type    = "VALID_SIGNAL"
                    confidence_score = "HIGH"
                # Rule 3: isolated outlier → low-confidence, needs context
                else:
                    anomaly_type    = "LOW_CONFIDENCE_SIGNAL"
                    confidence_score = "MEDIUM"
                # Note: _enrich_findings_with_dq() will overwrite anomaly_type using the
                # full DQ rules (plausibility thresholds, peer confirmation, row-level context)

                _period_str = row.get('period_date', row.get('DT_REFER', ''))
                _metric_label = metric.replace('_pct', '')
                findings.append({
                    "company":        company,
                    "metric":         metric,
                    "pattern":        "Statistical anomaly",
                    "period":         row["period_date"],
                    "value":          round(value, 2),
                    "normal_range":   f"{round(lower, 1)} - {round(upper, 1)}",
                    "anomaly_type":   anomaly_type,
                    "confidence_score": confidence_score,
                    "severity":       "HIGH",
                    "insight": (
                        f"{company} ({_period_str}): {_metric_label} "
                        f"at {value:.1f}% is outside the normal range "
                        f"({lower:.1f}% to {upper:.1f}%). "
                        f"Investigate one-time items, impairments, or "
                        f"extraordinary events in this period."
                    ),
                    "description_pt": (
                        f"{company} ({_period_str}): {_metric_label} "
                        f"em {value:.1f}% está fora do intervalo normal "
                        f"({lower:.1f}% a {upper:.1f}%). "
                        f"Investigar itens extraordinários, impairments ou "
                        f"eventos excepcionais neste período."
                    ),
                })

    return findings


# =============================================================================
# Pattern 6: YoY Same-Quarter Comparison
# =============================================================================

def analyze_yoy_comparison(
    df: pd.DataFrame, max_findings_per_company: int = 3
) -> list:
    """Compare same-quarter performance year-over-year to control for seasonality.

    Flags changes > 15pp YoY (capital-intensive commodity sectors see routine
    10-20pp swings; lower thresholds generate excessive noise).
    """
    findings = []

    if df.empty or "period_date" not in df.columns:
        return findings

    df = df.copy()
    df["DT_REFER_dt"] = pd.to_datetime(df["period_date"], errors="coerce")
    df["year"]    = df["DT_REFER_dt"].dt.year
    df["quarter"] = df["DT_REFER_dt"].dt.quarter

    metric_cols = ["Gross_Margin_pct", "EBIT_Margin_pct"]
    available   = [c for c in metric_cols if c in df.columns]

    for company in df["company_id"].unique():
        comp = df[df["company_id"] == company].copy()

        for metric in available:
            company_metric_findings = []

            for quarter in range(1, 5):
                q_data = (
                    comp[comp["quarter"] == quarter]
                    .sort_values("year")[["year", metric]]
                    .dropna()
                )
                if len(q_data) < 2:
                    continue

                q_data = q_data.copy()
                q_data["yoy_change"] = q_data[metric].diff()

                for _, row in q_data.dropna(subset=["yoy_change"]).iterrows():
                    if abs(row["yoy_change"]) > 15:  # 15pp threshold for commodity sectors
                        direction    = "improved"  if row["yoy_change"] > 0 else "deteriorated"
                        direction_pt = "melhorou" if row["yoy_change"] > 0 else "deteriorou"
                        _metric_label = metric.replace('_pct', '')
                        company_metric_findings.append({
                            "company":       company,
                            "metric":        metric,
                            "pattern":       "YoY quarter comparison",
                            "period":        f"Q{quarter} {int(row['year'])}",
                            "yoy_change_pp": round(row["yoy_change"], 2),
                            "current_value": round(row[metric], 2),
                            "severity":      "HIGH" if abs(row["yoy_change"]) > 25 else "MEDIUM",
                            "insight": (
                                f"{company}: {_metric_label} in "
                                f"Q{quarter} {int(row['year'])} {direction} by "
                                f"{abs(row['yoy_change']):.1f}pp vs "
                                f"Q{quarter} {int(row['year']) - 1} "
                                f"(now {row[metric]:.1f}%). "
                                f"Same-quarter comparison controls for seasonality."
                            ),
                            "description_pt": (
                                f"{company}: {_metric_label} no "
                                f"T{quarter} {int(row['year'])} {direction_pt} "
                                f"{abs(row['yoy_change']):.1f}pp vs "
                                f"T{quarter} {int(row['year']) - 1} "
                                f"(atual: {row[metric]:.1f}%). "
                                f"Comparação no mesmo trimestre controla a sazonalidade."
                            ),
                        })

            # Keep only the most extreme swings per company+metric
            company_metric_findings.sort(
                key=lambda f: abs(f["yoy_change_pp"]), reverse=True
            )
            findings.extend(company_metric_findings[:max_findings_per_company])

    return findings


# =============================================================================
# Post-processing helpers
# =============================================================================

def _cap_company_findings(
    findings: list, max_per_company: int, magnitude_key: str = None
) -> list:
    """Keep at most max_per_company findings per company, HIGH severity first."""
    by_company = defaultdict(list)
    for f in findings:
        by_company[f.get("company", "")].append(f)
    result = []
    for company_findings in by_company.values():
        sorted_f = sorted(
            company_findings,
            key=lambda f: (
                0 if f.get("severity") == "HIGH" else 1,
                -abs(f.get(magnitude_key, 0)) if magnitude_key else 0,
            ),
        )
        result.extend(sorted_f[:max_per_company])
    return result


def _add_confidence_scores(findings: list) -> list:
    """Add confidence_score to non-anomaly findings based on magnitude vs. detection threshold."""
    THRESHOLDS = {
        "Margin compression":      ("annual_change_pp", 2.0),
        "Margin expansion":        ("annual_change_pp", 2.0),
        "High margin volatility":  ("volatility",       5.0),
        "Cost composition drift":  ("shift_pp",         3.0),
        "Revenue-cost decoupling": ("divergence_pp",   10.0),
        "YoY quarter comparison":  ("yoy_change_pp",   15.0),
    }
    for f in findings:
        if "confidence_score" in f:   # Statistical anomaly already classified inline
            continue
        pattern = f.get("pattern", "")
        if pattern in THRESHOLDS:
            key, base = THRESHOLDS[pattern]
            ratio = abs(f.get(key, 0) or 0) / base
        elif pattern == "Potential cost reclassification":
            ratio = abs(f.get("correlation", 0)) / 0.5   # base threshold is -0.5
        else:
            f["confidence_score"] = "MEDIUM"
            continue
        f["confidence_score"] = "HIGH" if ratio >= 2.0 else ("LOW" if ratio < 1.3 else "MEDIUM")

        # DQ override: DATA_ISSUE forces LOW; ACCOUNTING_EVENT caps at MEDIUM.
        # Applied after ratio-based scoring so DQ classification always wins.
        anomaly = f.get("anomaly_type", "")
        if anomaly == "DATA_ISSUE":
            f["confidence_score"] = "LOW"
        elif anomaly == "ACCOUNTING_EVENT" and f.get("confidence_score") == "HIGH":
            f["confidence_score"] = "MEDIUM"

    return findings


def _dedup_yoy_vs_anomalies(all_findings: list) -> list:
    """Drop YoY findings that duplicate a Statistical anomaly for the same company+period."""
    anomaly_keys = set()
    for f in all_findings:
        if f.get("pattern") == "Statistical anomaly":
            try:
                dt = pd.to_datetime(f["period"])
                anomaly_keys.add((f["company"], dt.year, dt.quarter))
            except Exception:
                pass
    result = []
    for f in all_findings:
        if f.get("pattern") == "YoY quarter comparison":
            try:
                parts = f["period"].split()   # "Q3 2024" → ['Q3', '2024']
                q, yr = int(parts[0][1:]), int(parts[1])
                if (f["company"], yr, q) in anomaly_keys:
                    continue
            except Exception:
                pass
        result.append(f)
    return result


# Templates for confidence_reason field, keyed on anomaly_type
_CONFIDENCE_REASON_TEMPLATES = {
    "DATA_ISSUE":                 "Non-standalone row; {metric}={value:.1f} outside plausible range {lo:.0f}–{hi:.0f}",
    "ACCOUNTING_EVENT":           "Standalone row; {metric}={value:.1f} outside plausible range {lo:.0f}–{hi:.0f} — possible one-time item",
    "VALID_SIGNAL":               "Adjacent periods also anomalous — consistent structural pattern",
    "EVENT_DRIVEN_BUT_PLAUSIBLE": "Peer confirmation in same period — likely industry-wide event",
    "LOW_CONFIDENCE_SIGNAL":      "Isolated spike; no adjacent persistence or peer confirmation",
}

# Patterns that carry a specific `period` field parseable as a date / quarter string
_PERIOD_SPECIFIC_PATTERNS = {"Statistical anomaly", "YoY quarter comparison", "Revenue-cost decoupling"}


def _enrich_findings_with_dq(findings: list, df: pd.DataFrame) -> None:
    """Enrich every finding in-place with anomaly_type, confidence_reason,
    and (for DATA_ISSUE) a downgraded confidence_score.

    The df must already have _row_confidence and is_standalone columns
    (i.e. validate_metric_ranges + assign_data_confidence must have been called first).
    """
    # Pre-compute: set of (company, metric, period_date) for period-specific findings
    period_finding_dates: dict = defaultdict(list)
    for f in findings:
        if f.get("pattern") not in _PERIOD_SPECIFIC_PATTERNS:
            continue
        try:
            period_str = str(f.get("period", ""))
            if "Q" in period_str:
                parts = period_str.split()
                q, yr = int(parts[0][1:]), int(parts[1])
                month = q * 3
                dt = pd.Timestamp(f"{yr}-{month:02d}-01") + pd.offsets.MonthEnd(0)
            else:
                dt = pd.to_datetime(period_str)
            period_finding_dates[(f["company"], f.get("metric", ""))].append(dt)
        except Exception:
            pass

    # Pre-compute: which companies have _row_confidence == 'LOW'
    if "_row_confidence" in df.columns:
        low_conf_companies = set(
            df.loc[df["_row_confidence"] == "LOW", "company_id"].unique()
        )
    else:
        low_conf_companies = set()

    for f in findings:
        company = f.get("company", "")
        metric  = f.get("metric", "")
        pattern = f.get("pattern", "")

        # Non-period findings: trend / peer / volatility patterns
        if pattern not in _PERIOD_SPECIFIC_PATTERNS:
            if company in low_conf_companies:
                f["anomaly_type"]      = "LOW_CONFIDENCE_SIGNAL"
                f["confidence_reason"] = "Company has data rows with low plausibility confidence"
            else:
                f["anomaly_type"]      = "VALID_SIGNAL"
                f["confidence_reason"] = "Trend analysis on plausible data"
            continue

        # Period-specific findings
        period_str = str(f.get("period", ""))
        value      = f.get("value", 0.0) or 0.0

        # Parse the finding's period to a Timestamp
        try:
            if "Q" in period_str:
                parts = period_str.split()
                q, yr = int(parts[0][1:]), int(parts[1])
                month = q * 3
                finding_dt = pd.Timestamp(f"{yr}-{month:02d}-01") + pd.offsets.MonthEnd(0)
            else:
                finding_dt = pd.to_datetime(period_str)
        except Exception:
            f.setdefault("anomaly_type",      "LOW_CONFIDENCE_SIGNAL")
            f.setdefault("confidence_reason", "Period could not be parsed for DQ lookup")
            continue

        # Look up the matching df row for is_standalone
        is_standalone = True
        if "period_date" in df.columns and "company_id" in df.columns:
            mask = (df["company_id"] == company) & (
                pd.to_datetime(df["period_date"], errors="coerce") == finding_dt
            )
            matched = df[mask]
            if not matched.empty and "is_standalone" in matched.columns:
                is_standalone = bool(matched["is_standalone"].iloc[0])

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

        f["anomaly_type"]      = anomaly_type
        f["confidence_reason"] = reason

        # Force confidence_score to LOW for DATA_ISSUE findings
        if anomaly_type == "DATA_ISSUE":
            f["confidence_score"] = "LOW"


# =============================================================================
# Public API
# =============================================================================

def quality_scan(df: pd.DataFrame) -> dict:
    """Run data quality validation on the metrics DataFrame (Step 5).

    Applies validate_metric_ranges and assign_data_confidence.
    Returns a quality summary dict.
    """
    df = validate_metric_ranges(df)
    df = assign_data_confidence(df)

    total = len(df)
    flagged_mask = df["_has_plausibility_issue"].fillna(False)
    n_flagged = int(flagged_mask.sum())
    n_clean   = total - n_flagged
    quality_score = round(n_clean / total, 4) if total > 0 else 1.0

    # Build flags list — one entry per metric violation per row
    flags = []
    for _, row in df[flagged_mask].iterrows():
        period     = str(row.get("period_date", ""))
        confidence = str(row.get("_row_confidence", "MEDIUM"))
        raw_flags  = str(row.get("_plausibility_flags", ""))
        for issue in raw_flags.split(";"):
            issue = issue.strip()
            if not issue:
                continue
            # Format: "Gross_Margin_pct=2.2 outside [-20,80]"
            metric, value, reason = issue, "", issue
            if "=" in issue and " outside " in issue:
                metric_val, rest = issue.split(" outside ", 1)
                if "=" in metric_val:
                    metric, val_str = metric_val.split("=", 1)
                    value  = val_str
                    reason = f"outside {rest}"
            flags.append({
                "period":     period,
                "metric":     metric,
                "value":      value,
                "flag":       "DATA_ISSUE",
                "reason":     reason,
                "confidence": confidence,
            })

    return {
        "total_data_points": total,
        "clean":             n_clean,
        "flagged":           n_flagged,
        "quality_score":     quality_score,
        "flags":             flags,
        "_enriched_df":      df,   # internal: pass enriched df to detect_patterns
    }


def detect_patterns(
    df: pd.DataFrame,
    df_annual: pd.DataFrame,
    df_quarterly: pd.DataFrame,
    sector_map: dict = None,  # kept for backward-compat; unused after Algorithm 4 removal
) -> list:
    """Run pattern detection algorithms and return findings list (Step 6).

    The df must already have _row_confidence and is_standalone columns
    (run quality_scan first).

    Applies all post-processing: dedup, confidence scores, macro context, DQ enrichment.

    Note: Algorithm 4 (Peer Comparison) was removed — see _analyze_peer_comparison_removed.
    """
    all_findings = []

    # Pattern 1: Margin Trend Analysis (annual data)
    p1 = analyze_margin_trends(df_annual, periods_per_year=1)
    all_findings.extend(_cap_company_findings(p1, 2, "annual_change_pp"))

    # Pattern 2: Cost Composition Drift (annual data)
    p2 = analyze_cost_drift(df_annual)
    all_findings.extend(_cap_company_findings(p2, 5, "shift_pp"))

    # Pattern 3: Revenue-Cost Decoupling (annual data)
    p3 = analyze_revenue_cost_decoupling(df_annual)
    all_findings.extend(_cap_company_findings(p3, 2, "divergence_pp"))

    # Pattern 4: Peer Comparison — removed (see _analyze_peer_comparison_removed)

    # Pattern 5: Anomaly Detection (quarterly data)
    p5 = detect_anomalies(df_quarterly)
    all_findings.extend(_cap_company_findings(p5, 2))

    # Pattern 6: YoY Quarter Comparison (quarterly data)
    p6 = analyze_yoy_comparison(df_quarterly, max_findings_per_company=3)
    all_findings.extend(_cap_company_findings(p6, 3, "yoy_change_pp"))

    # Post-processing
    all_findings = _dedup_yoy_vs_anomalies(all_findings)
    _add_confidence_scores(all_findings)
    _enrich_findings_with_dq(all_findings, df)

    return all_findings


def determine_active_modules(df: pd.DataFrame) -> list:
    """Return list of module names for which data is available in df.

    Currently checks:
    - "profitability": income statement metrics (Gross_Margin_pct or revenue column present)
    """
    modules = []
    profitability_cols = {"Gross_Margin_pct", "EBIT_Margin_pct", "revenue",
                          "Receita de Venda de Bens e/ou Serviços"}
    if profitability_cols.intersection(df.columns):
        modules.append("profitability")
    return modules
