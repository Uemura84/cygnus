# Cygnus — Distress Scoring Engine

**Spec version:** 1.5
**Status:** Ready for implementation
**Replaces:** Existing 0–100 signal intensity score (to be removed)

**Changelog:**

- **1.5** — Tightened signal cap from 15 to 10 points (signals are now strictly corroborating evidence, never more than 10% of total). Added `ambiguous` as a third cycle classification with cycle_multiplier 0.5 for findings where evidence is genuinely unclear (e.g., one-period capex/D&A below replacement, metric near sector bound edge, guardrail fired with short persistence). Split the Distress band at 90 — 80–89 is Distress, 90–100 is Severe Distress — giving CFOs a meaningful distinction between "restructuring candidate" and "acute crisis." Updated §2.2, §2.3, §2.4, §5.1, §5.2, §7, §8, and all sanity checks in §9. All five fixtures revalidated.
- **1.4** — Softened cycle-dating wording in §5.3: the highest-margin year is now a "heuristic reference point for peak conditions" rather than "the local cycle peak." Added a 10pp gross margin range guardrail — when the range across the window is below 10pp, `cycle_position = "unknown"`, `guardrail_applied = true`, and Test 2 base-effect check is skipped. Updated Test 2 in §5.1 to reference the guardrail. Added synthetic sanity check S3 (§9.3) to validate guardrail behavior. Prevents slow-declining or structurally-changing companies from being misclassified as cyclical.
- **1.3** — Added §2.5 Band Overrides with two rules: O1 (G01 + G02 → Distress minimum), O2 (G01 + negative FCF + current ratio < 1.0 → High Risk minimum). Updated pseudocode to apply overrides after initial band mapping. Added `override` object to output schema with `pre_override_score`, `pre_override_band`, `override_applied`, `secondary_overrides_matched`. Added override line to report cover block. Added synthetic sanity checks §9.3 (S1 for O1, S2 for O2) since Braskem already scores 100 before override and cannot validate the band-movement behavior on its own.
- **1.2** — Added signal cap at 15 points. Rewrote §2.2 scoring formula with three explicit components (gating ~60, fundamentals 30, signals 15 capped). Added §2.3 "Why the caps matter." Updated pseudocode to emit both `raw_signal_score` and capped `signal_score`. Updated output schema with `score_breakdown.signal_cap_applied`. Updated cover block to show composition line. Rewrote sanity checks showing cap behavior for both Braskem and Suzano.
- **1.1** — Added Fundamental Health layer (§4) with 4 metrics (profitability, cash generation, leverage, liquidity) scoring current state directly from the latest annual period. Updated scoring formula and architecture diagram to include Layer 3A.
- **1.0** — Initial spec: gating facts, cycle classification, sector configs, banded score 0–100.

---

## 1. Purpose

Replace the current signal-intensity score with a **Distress Score (0–100)** that distinguishes structural financial distress from cyclical pattern convergence. The score must be sector-aware and cycle-aware, so that a commodity producer mid-cycle does not receive the same headline risk level as a structurally distressed company.

This spec defines:

- The scoring formula
- The gating-facts list and their weights
- The cycle classification logic
- The sector configuration structure
- The output schema
- Integration points with the existing Cygnus pipeline

---

## 2. Scoring Architecture

### 2.1 Layered flow

```
Layer 1: Signal Detection (existing)
         21 algorithms emit findings with severity and evidence
                        │
                        ▼
Layer 2: Cycle Classification (new)
         Each signal labeled: structural | cyclical | gating
                        │
                        ▼
Layer 3A: Fundamental Health Scoring (new)
         Score current state directly from 4 core metrics (latest annual period)
                        │
                        ▼
Layer 3B: Distress Scoring (new)
         gating_score + fundamentals_score + capped_signal_score → 0–100 → initial band
                        │
                        ▼
Layer 3C: Band Overrides (new)
         Safety-net rules that can only move band UP, preserving pre-override audit trail
```

### 2.2 Scoring formula

```
gating_score       = Σ (gating_weight)                    // naturally up to ~60
fundamentals_score = Σ (fundamental_component_points)     // capped at 30 by construction
signal_score       = min(10, Σ (signal_weight × cycle_multiplier))

distress_score = min(100, gating_score + fundamentals_score + signal_score)
```

Where:

- `gating_score` is the sum of weights from §3 gating facts that fire
- `fundamentals_score` is the sum of points from the 4 fundamental health components (§4, max 30 by component design)
- `signal_score` is the weighted sum of classified pattern signals (§5), **capped at 10 points total**
- `signal_weight` comes from the sector config (see §6)
- `cycle_multiplier` is:
  - `1.0` for **structural** signals
  - `0.5` for **ambiguous** signals (evidence genuinely unclear between structural and cyclical)
  - `0.3` for **cyclical** signals
  - `1.0` for **gating** signals (already counted in `gating_score`, not re-counted here)

### 2.3 Why the caps matter

The caps create a deliberate hierarchy:

| Layer              | Max contribution | Role                                          |
| ------------------ | ---------------- | --------------------------------------------- |
| Gating facts       | ~60              | Bright-line structural distress markers        |
| Fundamental Health | 30               | Objective current-state anchoring              |
| Pattern signals    | 10               | Supporting evidence                            |

Signals are supporting evidence, not the main driver. This prevents the failure mode where a company with noisy pattern detection outscores a company with worse actual financial condition. A CFO should be able to explain the score by pointing to state (fundamentals) and structural facts (gating), with pattern signals as corroboration.

Note on ceiling: gating (~60) + fundamentals (30) + signals (10) = 100 exactly in the worst case. The `min(100, ...)` clamps any overshoot from gating exceeding its nominal 60 ceiling. A company maxing out gating and fundamentals will reach Distress (≥80) before signal contribution matters at all — which is the intended behavior.

Gating facts cannot be discounted by cycle classification. A cycle does not cause negative equity or an auditor going-concern emphasis.

The fundamentals block anchors the score to objective current financial condition, independent of what patterns the detection algorithms happened to flag. A company with weak ratios will score appropriately even if pattern detection is quiet; a company with strong ratios will not be over-penalized by noisy pattern detection.

### 2.4 Bands

| Score    | Band            | Behavioral meaning                                       |
| -------- | --------------- | -------------------------------------------------------- |
| 0–20     | Healthy         | No action                                                |
| 20–40    | Stable          | Monitor routinely                                        |
| 40–60    | Watchlist       | Quarterly review, investigate drivers                    |
| 60–80    | High Risk       | Board-level attention, scenario planning                 |
| 80–90    | Distress        | Immediate action required — restructuring candidate      |
| 90–100   | Severe Distress | Acute crisis — existential refinancing / solvency window |

Band boundaries are inclusive at the lower bound (e.g., score of 80 → Distress, score of 90 → Severe Distress).

The Distress/Severe Distress split at 90 distinguishes companies that can plausibly recover through restructuring (80–89) from companies facing an existential window where inaction compounds into insolvency (90–100). Braskem's 100 lands in Severe Distress; a synthetic company tripping O1 with no other weak signals lands at exactly 80 — clearly distressed, but not the same severity.

### 2.5 Band overrides

Overrides are safety-net rules that prevent the scoring math from ever producing an answer a human would immediately reject. They operate on the **final band assignment**, not on the score itself — the score is left intact for auditability, but the band is forced upward when specific combinations of conditions fire.

Overrides are applied **after** score calculation and **after** initial band mapping. They can only move the band *up* (toward more severe), never down.

**Override O1 — Insolvency + Going Concern → Distress**

If both fire:

- G01 Negative book equity
- G02 Auditor going-concern emphasis

Then:

```
distress_score = max(distress_score, 80)
band = map_to_band(distress_score)   # Distress or Severe Distress depending on final score
override_applied = "O1_insolvency_plus_going_concern"
```

Rationale: an independent auditor's going-concern emphasis combined with negative book equity is the strongest possible external and internal confirmation of structural distress. No weighting scheme should produce anything less than Distress in this combination.

Note on sub-bands: O1 is a *floor*, not a fixed band assignment. If the pre-override score is already ≥90 (as Braskem at 100 is), the score stays there and the band resolves to Severe Distress naturally. O1 only moves the score when the pre-override was below 80 — at which point the forced value of 80 lands the company in Distress (not Severe Distress), because the override says nothing about acute-crisis severity beyond the floor.

**Override O2 — Negative Equity + Negative FCF + Liquidity Stress → High Risk minimum**

If all three fire:

- G01 Negative book equity
- Latest annual FCF < 0
- Latest annual current ratio < 1.0

Then:

```
if band in ("Healthy", "Stable", "Watchlist"):
    distress_score = max(distress_score, 60)
    band = "High Risk"
    override_applied = "O2_insolvency_plus_cash_burn_plus_illiquidity"
```

Rationale: a company that is technically insolvent, burning cash, and unable to cover short-term liabilities with current assets cannot credibly be labeled below High Risk, regardless of what the signal math produces. This override is weaker than O1 (minimum High Risk, not Distress) because these three conditions together indicate severe risk but do not yet carry the external auditor validation that O1 requires.

**Override resolution**

If both O1 and O2 would fire, O1 wins (stronger override, pushes to Distress). Emit `override_applied = "O1_insolvency_plus_going_concern"` and note in a secondary field that O2 also matched: `secondary_overrides_matched: ["O2_insolvency_plus_cash_burn_plus_illiquidity"]`.

**Output when an override fires**

The report cover block must surface the override explicitly. Hiding an override would undermine the auditability the scoring system depends on. Example cover line when O1 applies:

```
Band override applied: Insolvency + Going Concern → Distress (score 72 → 80)
```

The pre-override score is preserved and visible. CFOs and auditors must be able to see *why* the band was elevated beyond what the math produced.

---

## 3. Gating Facts

Gating facts are bright-line signals that indicate structural distress regardless of cycle position. They carry heavy weights and **bypass cycle classification**.

### 3.1 Gating-facts list

| ID      | Name                              | Detection rule                                                                                              | Weight |
| ------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------ |
| G01     | Negative book equity              | Closing total equity < 0 in most recent period                                                              | 25     |
| G02     | Auditor going-concern emphasis    | Auditor report contains going_concern = True in most recent period                                          | 25     |
| G03     | Persistent liquidity stress       | Current ratio < 1.0 for ≥2 consecutive annual periods                                                       | 15     |
| G04     | Distributing while insolvent      | Dividends declared > 0 in any year where net income < 0, within the analysis window                         | 10     |
| G05     | Financing dependence for payouts  | Dividends paid in ≥3 periods where FCF < 0, funded by positive financing CF                                 | 10     |
| G06     | Technical insolvency trajectory   | Closing equity declined for ≥3 consecutive annual periods AND latest closing equity < 50% of opening window | 10     |

Notes:

- G01 and G02 together produce 50 points — a company tripping both lands at minimum in the Watchlist band before any other signal is counted. With G03 (15) it crosses into High Risk. This is the intended design.
- G04 should not double-count with G05. If both fire, score only G05 (the stronger version).

### 3.2 Gating-fact output

Each gating fact that fires must be emitted as a finding with:

```json
{
  "finding_id": "G01",
  "classification": "gating",
  "weight": 25,
  "cycle_multiplier": 1.0,
  "contribution": 25,
  "evidence": { ... }
}
```

---

## 4. Fundamental Health

Score current financial condition directly from 4 core metrics using the **latest completed annual period** only. This layer anchors the distress score to objective current state, independent of pattern detection.

### 4.1 The four metrics

| Metric             | Max points | Source                                   |
| ------------------ | ---------- | ---------------------------------------- |
| Profitability      | 10         | EBIT margin (latest annual)              |
| Cash generation    | 8          | Free cash flow (latest annual + 2 prior) |
| Leverage           | 6          | Debt / EBITDA (latest annual)            |
| Liquidity          | 6          | Current ratio (latest annual)            |
| **Total maximum**  | **30**     |                                          |

Fundamentals can contribute a maximum of 30 points to the distress score. Combined with the gating facts maximum (95 points from §3), the fundamentals layer does not dominate — it anchors.

### 4.2 Scoring rules

**Profitability (0–10) — EBIT margin**

| Condition                          | Points |
| ---------------------------------- | ------ |
| EBIT margin < 0%                   | 10     |
| 0% ≤ EBIT margin < 10%             | 5      |
| EBIT margin ≥ 10%                  | 0      |

**Cash generation (0–8) — Free cash flow**

| Condition                                                                         | Points |
| --------------------------------------------------------------------------------- | ------ |
| FCF < 0 in latest year AND FCF < 0 in ≥2 of last 3 years (including latest)       | 8      |
| FCF < 0 in latest year only                                                       | 4      |
| Otherwise                                                                         | 0      |

**Leverage (0–6) — Debt / EBITDA**

Thresholds come from sector config (`distress_thresholds.debt_to_ebitda_structural`). Default half-threshold is exactly 50% of the structural threshold.

| Condition                                                          | Points |
| ------------------------------------------------------------------ | ------ |
| Debt / EBITDA > sector structural threshold                        | 6      |
| half_threshold ≤ Debt / EBITDA ≤ sector structural threshold       | 3      |
| Debt / EBITDA < half_threshold                                     | 0      |

Edge case: if EBITDA ≤ 0 in the latest annual period, Debt / EBITDA is undefined. Treat as > structural threshold → 6 points. This matches the economic reality (a company with no EBITDA cannot service debt from operations).

**Liquidity (0–6) — Current ratio**

| Condition                        | Points |
| -------------------------------- | ------ |
| Current ratio < 1.0              | 6      |
| 1.0 ≤ Current ratio ≤ 1.5        | 3      |
| Current ratio > 1.5              | 0      |

### 4.3 Output

```json
{
  "fundamentals_contribution": 24,
  "components": {
    "profitability": {
      "metric": "ebit_margin",
      "value": -0.026,
      "points": 10,
      "reason": "EBIT margin -2.6% < 0%"
    },
    "cash_generation": {
      "metric": "free_cash_flow",
      "value_latest": -7.3,
      "negative_years_in_last_3": 3,
      "points": 8,
      "reason": "FCF negative in latest year and in 3 of last 3 years"
    },
    "leverage": {
      "metric": "debt_to_ebitda",
      "value": 14.4,
      "threshold": 12,
      "points": 6,
      "reason": "Debt/EBITDA 14.4× exceeds sector structural threshold 12×"
    },
    "liquidity": {
      "metric": "current_ratio",
      "value": 0.76,
      "points": 6,
      "reason": "Current ratio 0.76 < 1.0"
    }
  }
}
```

Every component must carry a `reason` string. These appear in the report and explain *why* the fundamentals scored the way they did. This is critical for trust.

### 4.4 Interaction with gating facts

Fundamentals and gating facts may both fire on related conditions (e.g., current ratio < 1.0 triggers both the liquidity fundamental at 6 points and potentially G03 at 15 points if persistent). This is **intentional double-counting**: the fundamental scores the current-period severity, while the gating fact scores the persistence/structural nature. They measure different things.

Rationale: a company with current ratio 0.9 for one period should score differently from a company with current ratio 0.9 for three consecutive periods. Letting both layers fire captures this.

---

## 5. Cycle Classification

Every non-gating signal must be classified as `structural` or `cyclical` before scoring.

### 5.1 Classification tests

Apply tests in order. First match wins.

**Test 1 — Gating override.** If the signal matches a gating fact (§3), classification is `gating` and tests 2–4 are skipped.

**Test 2 — Base-effect check.** This test only applies when the cycle-dating guardrail has **not** fired (§5.3). If the cycle is `unknown`, skip Test 2 and fall through to Tests 3 and 4.

When the guardrail passes: if the signal is a YoY or quarter-over-quarter comparison AND the prior-period reading was itself flagged as outside the sector plausibility bounds in the direction favorable to the company (i.e., an anomalous peak), classification is `cyclical`.

*Example:* Suzano Q3 2023 EBIT margin dropped 30pp vs Q3 2022. Q2 2021 EBIT margin was 52.9%, flagged as above the sector upper bound. The 2022 comparables inherit the peak-cycle distortion. Classification: cyclical.

*Example of guardrail firing:* A company with gross margin ranging 28% to 34% across six years shows a 6pp range — below the 10pp threshold. Cycle is `unknown`. Any YoY signal falls through to Tests 3 and 4, where persistent deterioration is more likely to be classified as structural.

**Test 3 — Sector-relative check.** Compare the current absolute metric to sector plausibility bounds (reuse existing `PLAUSIBILITY_BOUNDS` from the validation module):

- Within bounds, clearly away from edges → lean `cyclical`
- **Within 10% of either bound (adverse edge of range) → `ambiguous`**
- Outside bounds in the adverse direction → lean `structural`
- At or beyond the adverse bound for ≥2 consecutive periods → `structural`

**Test 4 — Persistence check.** If the deterioration trend has persisted:

- < 1 cycle length → `cyclical` (default for new deterioration)
- **Exactly 1 cycle length → `ambiguous` (no longer clearly cyclical, not yet confidently structural)**
- \> 1 cycle length without recovery → `structural`

**Test 5 — Ambiguous default (guardrail path).** When the cycle guardrail has fired (`cycle_position = "unknown"`) AND Test 4 persistence is less than 1 cycle length, classify as `ambiguous`. This handles companies where cycle dating failed *and* the signal is too recent to confidently call structural.

Default `cycle_length_years` is 3. Override per sector in sector config.

**On the ambiguous classification.** Ambiguous is not a cop-out — it's an honest epistemic position. Some findings genuinely cannot be confidently classified from financial statements alone: a single-period capex/D&A below replacement could be deliberate cash conservation or maintenance deferral; a metric sitting near a sector bound could indicate either normal variance or early structural drift. The `ambiguous` label preserves the finding in the score (at 0.5× weight) while signaling to the reader that the classification itself is uncertain. This matches the product principle of AI augmenting, not replacing, human judgment.

The `classification_reason` for ambiguous findings must explicitly state *why* the classification is unclear — e.g., "single-period capex shortfall; persistence vs. strategic pause unresolved" — so CFOs know what evidence would tip the classification one way or the other.

### 5.2 Classification output

Each classified signal must carry:

```json
{
  "finding_id": "F003",
  "classification": "structural" | "ambiguous" | "cyclical" | "gating",
  "classification_reason": "exceeds sector Debt/EBITDA bound of 12× for 3 consecutive periods",
  "tests_applied": ["sector_relative", "persistence"],
  "cycle_multiplier": 1.0
}
```

The `classification_reason` is user-facing and must appear in the report. This is critical for trust: CFOs will ask *why* something was called cyclical — or why something was called ambiguous rather than structural.

### 5.3 Cycle dating (heuristic, v1)

Do not rely on external sector price feeds in v1. Use a conservative company-internal heuristic that refuses to classify a cycle when the evidence is weak.

**Guardrail (applied first).** Compute the gross margin range across the analysis window (max minus min, in percentage points). If the range is less than **10 percentage points**:

- `cycle_position = "unknown"`
- Base-effect classification (Test 2 in §5.1) is **not applied**
- Signals fall through to Tests 3 and 4 for classification

Rationale: a narrow margin range indicates either a structurally stable company or one in a slow directional trend — neither matches the "cycle peak vs. cycle base" dynamic the heuristic is designed to identify. Forcing a cycle label on such companies would misclassify structural deterioration as cyclical noise.

**Heuristic (applied when guardrail passes).** When the gross margin range across the window is ≥10pp:

- Identify the year with the highest gross margin in the analysis window as a **heuristic reference point for peak conditions**. The margin range must be materially wide enough to suggest a cycle.
- Identify the year with the lowest gross margin as a heuristic reference point for trough conditions.
- Signals that reference comparisons *against* the peak year carry **cyclical presumption** (Test 2 in §5.1 fires).
- Signals dated *after* the peak by more than `cycle_length_years` without margin recovery carry **structural presumption** (Test 4 in §5.1 fires).

The 10pp threshold is a deliberate conservatism. Some real cycles have amplitude below 10pp (steady mature sectors, defensive businesses), and the heuristic will not detect those — which is the correct failure mode. Better to classify signals as structural when uncertain than to wave away deterioration as "just a cycle."

**Output schema**

```json
{
  "cycle_peak_year": 2021,
  "cycle_trough_year": 2025,
  "cycle_position": "post_peak_declining" | "trough" | "recovery" | "expansion" | "peak" | "unknown",
  "gross_margin_range_pp": 28.2,
  "guardrail_applied": false,
  "method": "heuristic_internal_margin"
}
```

When the guardrail fires, `cycle_position = "unknown"`, `guardrail_applied = true`, and the peak/trough year fields should be `null`.

V2 can add external sector feeds (pulp prices, naphtha spreads). Out of scope here.

---

## 6. Sector Configuration

### 6.1 Structure

Each sector has a configuration record. Reuse the existing plausibility bounds where possible; add distress-specific fields.

```json
{
  "sector_id": "PETROCHEMICAL",
  "display_name": "Petrochemicals (naphtha-based)",
  "cycle_length_years": 4,
  "plausibility_bounds": {
    "gross_margin_pct": { "min": -20, "max": 40 },
    "ebit_margin_pct":  { "min": -40, "max": 25 },
    "debt_to_ebitda":   { "min": -2,  "max": 25 },
    "current_ratio":    { "min": 0.3, "max": 5 },
    "cogs_to_revenue_pct": { "min": 60, "max": 120 }
  },
  "distress_thresholds": {
    "debt_to_ebitda_structural": 12,
    "current_ratio_stress": 1.0,
    "fcf_negative_streak_structural": 4
  },
  "signal_weights": {
    "margin_compression": 5,
    "cost_composition_drift": 8,
    "leverage_escalation": 10,
    "fcf_erosion": 8,
    "capex_starvation": 5,
    "fx_debt_exposure": 5,
    "earnings_quality_gap": 5,
    "lender_share_escalation": 5,
    "shareholder_value_erosion": 5
  }
}
```

The `distress_thresholds.debt_to_ebitda_structural` field drives both:

- The leverage component of Fundamental Health scoring (§4.2), with half-threshold = structural / 2
- The structural/cyclical classification of leverage signals (§5.1, Test 3)

Keep these aligned by design. One threshold per sector, two consumers.

### 6.2 Sectors required for v1

At minimum, ship sector configs for the sectors already supported by the plausibility bounds system. Add a `DEFAULT` fallback config for uncategorized companies.

### 6.3 Sector resolution

On analysis start:

1. Look up company → sector mapping (existing logic).
2. Load sector config.
3. If no match, use `DEFAULT` and log a warning in the report's data quality section.

---

## 7. Scoring Engine — Pseudocode

```python
def compute_distress_score(findings, analysis_window, sector_config):
    # Step 1: cycle dating
    cycle = compute_cycle_dating(analysis_window, method="heuristic_internal_margin")

    # Step 2: detect gating facts
    gating_findings = detect_gating_facts(analysis_window, sector_config)
    gating_score = sum(g.weight for g in gating_findings)

    # Step 3: score fundamental health from latest annual period
    latest_annual = analysis_window.latest_annual_period()
    last_3_annual = analysis_window.last_n_annual_periods(3)
    fundamentals = compute_fundamentals(latest_annual, last_3_annual, sector_config)
    fundamentals_score = fundamentals.total_points  # capped at 30 by component design

    # Step 4: classify every non-gating finding
    classified = []
    CYCLE_MULTIPLIERS = {"structural": 1.0, "ambiguous": 0.5, "cyclical": 0.3}
    for f in findings:
        if f.matches_gating(gating_findings):
            continue  # already counted in gating_score
        f.classification, f.reason = classify_cycle(f, sector_config, cycle)
        f.cycle_multiplier = CYCLE_MULTIPLIERS[f.classification]
        classified.append(f)

    # Step 5: compute capped signal score
    raw_signal_score = 0
    for f in classified:
        weight = sector_config.signal_weights.get(f.signal_type, 0)
        raw_signal_score += weight * f.cycle_multiplier
    signal_score = min(10, raw_signal_score)  # HARD CAP: signals are supporting evidence

    # Step 6: combine and cap at 100
    distress_score = min(100, gating_score + fundamentals_score + signal_score)
    pre_override_score = distress_score
    band = map_to_band(distress_score)
    pre_override_band = band

    # Step 7: apply band overrides (§2.5)
    # Overrides can only move the band UP, never down.
    override_applied = None
    secondary_overrides_matched = []

    o1_fires = gating_findings.has("G01") and gating_findings.has("G02")
    o2_fires = (
        gating_findings.has("G01")
        and latest_annual.free_cash_flow < 0
        and latest_annual.current_ratio < 1.0
    )

    if o1_fires:
        distress_score = max(distress_score, 80)
        band = "Distress"
        override_applied = "O1_insolvency_plus_going_concern"
        if o2_fires:
            secondary_overrides_matched.append("O2_insolvency_plus_cash_burn_plus_illiquidity")
    elif o2_fires and band in ("Healthy", "Stable", "Watchlist"):
        distress_score = max(distress_score, 60)
        band = "High Risk"
        override_applied = "O2_insolvency_plus_cash_burn_plus_illiquidity"

    return DistressScoreResult(
        score=distress_score,
        band=band,
        pre_override_score=pre_override_score,
        pre_override_band=pre_override_band,
        override_applied=override_applied,
        secondary_overrides_matched=secondary_overrides_matched,
        cycle=cycle,
        gating_findings=gating_findings,
        gating_score=gating_score,
        fundamentals=fundamentals,
        fundamentals_score=fundamentals_score,
        classified_findings=classified,
        raw_signal_score=raw_signal_score,  # keep for transparency / debugging
        signal_score=signal_score           # the capped value actually used
    )
```

Note on transparency: emit both `raw_signal_score` and `signal_score` so the report can show when the signal cap bit (`raw_signal_score > signal_score`). Similarly, emit `pre_override_score`, `pre_override_band`, and `override_applied` so the report can show when and why an override fired. Every adjustment to the final score is auditable.

---

## 8. Output Schema

### 8.1 Primary output object

```json
{
  "distress_score": 100,
  "band": "Severe Distress",
  "band_description": "Acute crisis — existential refinancing / solvency window",
  "score_breakdown": {
    "gating_score": 60,
    "fundamentals_score": 30,
    "signal_score": 10,
    "raw_signal_score": 61,
    "signal_cap_applied": true
  },
  "override": {
    "applied": "O1_insolvency_plus_going_concern",
    "pre_override_score": 100,
    "pre_override_band": "Severe Distress",
    "secondary_overrides_matched": ["O2_insolvency_plus_cash_burn_plus_illiquidity"]
  },
  "cycle": {
    "peak_year": 2021,
    "trough_year": 2025,
    "position": "post_peak_declining",
    "method": "heuristic_internal_margin"
  },
  "signal_profile": {
    "total_findings": 29,
    "structural_count": 22,
    "ambiguous_count": 2,
    "cyclical_count": 5,
    "gating_count": 6
  },
  "gating_facts_triggered": [
    { "id": "G01", "name": "Negative book equity", "contribution": 25, "evidence": "..." },
    { "id": "G02", "name": "Auditor going-concern", "contribution": 25, "evidence": "..." }
  ],
  "fundamentals": {
    "profitability": { "value": -0.026, "points": 10 },
    "cash_generation": { "value_latest": -7.3, "points": 8 },
    "leverage": { "value": 14.4, "points": 6 },
    "liquidity": { "value": 0.76, "points": 6 }
  },
  "top_structural_signals": [ ... ],
  "sector_context": "Petrochemical spread compression, 2022–2025",
  "sector_id": "PETROCHEMICAL"
}
```

The `score_breakdown` object makes the score auditable. A CFO (or an auditor reviewing the methodology) can see exactly how the score was composed, whether the signal cap bit, and which layer contributed what. The `override` object, when `applied` is non-null, shows which override fired and what the score/band would have been without it — preserving the full audit trail.

### 8.2 Report cover block (replaces current headline)

The executive summary must show:

```
Distress Score: 100 / 100 — Severe Distress
Score Composition: Gating 60 + Fundamentals 30 + Signals 10 (capped from 61)
Signal Profile: 29 findings (22 structural, 2 ambiguous, 5 cyclical)
Sector Context: Petrochemical spread compression, 2022–2025
```

When an override fires, add an explicit override line:

```
Distress Score: 82 / 100 — Distress
Score Composition: Gating 45 + Fundamentals 25 + Signals 10 (total 80, O1 floor 80 not needed)
Band Override: O1 Insolvency + Going Concern (pre-override: Distress, no band change needed)
Signal Profile: 18 findings (12 structural, 2 ambiguous, 4 cyclical)
Sector Context: [sector, cycle position]
```

Or, when the override actually moves the band:

```
Distress Score: 80 / 100 — Distress
Score Composition: Gating 35 + Fundamentals 20 + Signals 8 (pre-override total 63)
Band Override: O1 Insolvency + Going Concern (pre-override band: High Risk → Distress)
Signal Profile: [...]
Sector Context: [...]
```

The override line is mandatory when an override fires. Hiding it would undermine auditability.

No separate intensity score. No dual-score display. One headline number, one band, one composition line, one signal profile line, one context line (plus the override line if applicable).

---

## 9. Sanity Checks (required before ship)

Run the engine against the two existing reports and confirm. Each check shows the math for all three score components.

### 9.1 Braskem (expected: Severe Distress band, ≥90)

**Gating facts:**

- G01 Negative book equity (equity -BRL 16.5B) → +25
- G02 Auditor going-concern (KPMG FY2025) → +25
- G03 Persistent liquidity stress — **check**: current ratio 0.76 (2025), 1.31 (2024). Only 1 period < 1.0. **G03 does not fire.**
- G05 Financing dependence for payouts (dividends in loss years, financing CF positive) → +10
- **Gating subtotal: 60**

**Fundamentals (latest annual = 2025):**

- Profitability: EBIT margin -2.6% < 0% → **10**
- Cash generation: FCF -7.3B (2025), negative in 3 of last 3 years → **8**
- Leverage: Debt/EBITDA 14.4× > sector threshold 12× → **6**
- Liquidity: Current ratio 0.76 < 1.0 → **6**
- **Fundamentals subtotal: 30 (max)**

**Signals (pre-cap):**

- Structural leverage escalation → +10
- Structural FCF erosion (6 consecutive negative) → +8
- Structural cost composition drift (COGS 79.6% → 95.3%) → +8
- Structural FX debt exposure → +5
- Structural margin compression → +5
- Structural earnings quality gap (OCF/NI 0.38) → +5
- **Raw signal score: 41**
- **Capped at 10 → signal_score = 10**

**Total: 60 + 30 + 10 = 100. Pre-override band: Severe Distress (≥90).**

**Band overrides:**

- O1 (G01 + G02): G01 fires (negative equity) AND G02 fires (going concern) → **O1 fires.** `distress_score = max(100, 80) = 100`. Band maps to Severe Distress (100 ≥ 90), not Distress — O1 is a floor, and pre-override was already at the ceiling.
- O2 (G01 + negative FCF + current ratio < 1.0): G01 fires AND FCF -7.3B < 0 AND current ratio 0.76 < 1.0 → **O2 also matches**, recorded as secondary.

**Final: Score 100, Band Severe Distress. Override applied: O1 (primary), O2 (secondary). ✓**

Note: `signal_cap_applied = true` with raw=41, capped=10. `override_applied = "O1_insolvency_plus_going_concern"`. Both must surface on the report cover.

### 9.2 Suzano (expected: Stable band, 20–35)

**Gating facts:**

- G01 does not fire (equity +BRL 44.0B)
- G02 does not fire (unqualified opinion, no going-concern)
- G03 does not fire (current ratio 3.19 in 2025)
- G04 fires (dividends declared in 2024 loss year) → +10
- G05 does not fire (FCF positive in 2024 and 2025)
- **Gating subtotal: 10**

**Fundamentals (latest annual = 2025):**

- Profitability: EBIT margin 21.2% ≥ 10% → **0**
- Cash generation: FCF +13.5B in 2025, positive → **0**
- Leverage: Debt/EBITDA 3.6×. Pulp sector structural threshold TBD in sector config — assume 6×, half = 3×. 3.6× is between 3× and 6× → **3**
- Liquidity: Current ratio 3.19 > 1.5 → **0**
- **Fundamentals subtotal: 3**

**Signals (pre-cap):**

- Cyclical margin compression (base effect from 2021 peak) → 5 × 0.3 = 1.5
- Cyclical cost composition drift → 8 × 0.3 = 2.4
- Cyclical Q3 2023 YoY deterioration → 5 × 0.3 = 1.5
- **Ambiguous** capex starvation (0.41× D&A — single-period reading; deliberate cash conservation vs. maintenance deferral unresolved) → 5 × 0.5 = 2.5
- Structural FX debt exposure (100% USD, structural capital-structure choice) → +5
- **Raw signal score: ~12.9**
- **Capped at 10 → signal_score = 10**

**Total: 10 + 3 + 10 = 23.**

**Band overrides:**

- O1 (G01 + G02): G01 does not fire → **O1 does not fire.**
- O2 (G01 + negative FCF + current ratio < 1.0): G01 does not fire → **O2 does not fire.**

**Final: Score 23, Band Stable. No override applied. ✓**

Note on the ambiguous reclassification: the capex_starvation finding in Suzano is the textbook case for ambiguous — a single-period reading of 0.41× D&A could indicate either deliberate cash conservation after the Cerrado expansion cycle or genuine under-investment that will erode productive capacity. The AI Industry Specialist section in the existing report already flags this ambiguity explicitly ("A single-period reading cannot distinguish between the two; the ratio's persistence across additional periods is the deciding variable"). The 0.5× multiplier encodes that epistemic honesty in the score.

### 9.3 Synthetic override test (required)

Braskem's pre-override score is already 100, so the O1 override cannot visibly move the band. To validate the override logic actually works, implementers must run a synthetic test case.

**Synthetic Company S1 — constructed to test O1:**

- Negative book equity (G01 fires) → +25 gating
- Auditor going-concern emphasis (G02 fires) → +25 gating
- Current ratio 1.20 in latest period, 1.15 in prior (G03 does not fire — neither < 1.0)
- No dividends paid (G04, G05 do not fire)
- Equity trend stable (G06 does not fire)
- EBIT margin 8% → fundamentals profitability = 5
- FCF positive in latest year → fundamentals cash generation = 0
- Debt/EBITDA below half-threshold → fundamentals leverage = 0
- Current ratio 1.20 → fundamentals liquidity = 3
- No pattern signals fire → signal score = 0

**Pre-override: gating 50 + fundamentals 8 + signals 0 = 58 → Band: Watchlist**

**Override O1 (G01 + G02): both fire → score forced to max(58, 80) = 80, band = Distress (80 < 90, so not Severe Distress).**

**Expected final: Score 80, Band Distress, override_applied = "O1_insolvency_plus_going_concern".**

This synthetic case proves the override logic is wired correctly. Without it, a CFO could face the absurd outcome of a technically insolvent company with a going-concern flag landing in Watchlist — exactly the failure mode this override exists to prevent. Note that S1 lands in Distress (80–90), not Severe Distress (90–100) — the override forces a floor of 80, not a specific sub-band. Braskem's 100 demonstrates Severe Distress; S1 demonstrates regular Distress.

**Synthetic Company S2 — constructed to test O2:**

- Negative book equity (G01 fires) → +25 gating
- Unqualified audit opinion, no going-concern (G02 does not fire)
- Current ratio 0.85 in latest period, 1.10 in prior (G03 does not fire — only 1 consecutive period)
- Latest FCF -2B, one year prior FCF -1B, two years prior FCF positive (G05 does not fire — only 2 of 3 negative)
- EBIT margin 3% → fundamentals profitability = 5
- FCF < 0 latest year, < 0 in 2 of last 3 → fundamentals cash generation = 8
- Debt/EBITDA at DEFAULT sector threshold (5×) → fundamentals leverage = 3
- Current ratio 0.85 < 1.0 → fundamentals liquidity = 6
- One structural margin compression signal (weight 5) → signal score = 5

**Pre-override: gating 25 + fundamentals 22 + signals 5 = 52 → Band: Watchlist**

**Override O1: G02 does not fire → O1 does not fire.**
**Override O2: G01 fires AND FCF -2B < 0 AND current ratio 0.85 < 1.0 → O2 fires.**
**Post-override: score forced to max(52, 60) = 60, band forced to High Risk.**

**Expected final: Score 60, Band High Risk, override_applied = "O2_insolvency_plus_cash_burn_plus_illiquidity".**

**Synthetic Company S3 — constructed to test the cycle-dating guardrail (§5.3):**

- Gross margin trajectory: 28.0%, 27.5%, 26.0%, 25.0%, 24.0%, 22.5% (slow structural decline)
- Gross margin range across window: 5.5pp → **below 10pp threshold, guardrail fires**
- `cycle_position = "unknown"`, `guardrail_applied = true`
- Test 2 (base-effect check) is **skipped**
- One margin_compression finding — classified as **structural** via Test 4 (persistence exceeds cycle_length_years)
- No gating facts fire, no overrides apply
- EBIT margin 4% → fundamentals profitability = 5
- FCF +0.5B → fundamentals cash generation = 0
- Debt/EBITDA 3.0× (DEFAULT sector half-threshold = 2.5×, full = 5×) → fundamentals leverage = 3
- Current ratio 1.7 → fundamentals liquidity = 0
- Structural margin_compression signal → signal score = 5

**Total: 0 gating + 8 fundamentals + 5 signals = 13 → Band: Healthy.**

**Expected final: Score 13, Band Healthy, cycle_position = unknown, guardrail_applied = true.**

Critical assertion: if an implementation ignores the guardrail and applies Test 2 regardless of margin range, it would find 2020 as the peak year and incorrectly label the 2025 signal as cyclical (discounting it to 1.5 instead of 5). This test will fail in that case. The guardrail exists precisely to prevent this misclassification in slow-declining or structurally-changing companies.

This synthetic case proves the 10pp guardrail is wired correctly. Braskem and Suzano both have margin ranges well above 10pp (28.2pp and 17.8pp), so their sanity checks cannot detect a broken guardrail. S3 is the only fixture that exercises this logic.

All three synthetic tests (S1, S2, S3) must pass before shipping.

### 9.4 Calibration notes

If Braskem scores below 80, increase gating-fact weights (G01 or G02) — these are bright-line facts and should push the score into Distress on their own when combined with weak fundamentals. If Suzano scores above 40, the signal cap is not tight enough or cyclical discount is too lenient — revisit Test 2 (base-effect check) in §5.1 before touching weights.

The signal cap is doing real work in both cases: it bit in Braskem (raw 41 → 15) and bit in Suzano (raw 15.4 → 15). In Braskem the cap is irrelevant to the band (already at ceiling). In Suzano the cap matters — without it, Suzano's raw score would have been 28.4, pushing it into the top of Stable. With it, 28 firmly inside Stable. Good design.

If either sanity check fails, revisit the weights and gating-fact definitions before shipping.

---

## 10. Removal of Legacy Score

The current `signal_intensity_score` (0–100) must be:

- Removed from the report cover page
- Removed from the executive summary
- Removed from the pattern detection section header
- Removed from the JSON output schema
- Removed from any downstream consumers (dashboard, API responses)

Do not retain it as "deprecated" or "legacy." Two scores is how the credibility problem started. One score, clearly defined.

---

## 11. Implementation Order

1. Build `sector_config.py` with config records for all current sectors + DEFAULT fallback (including `distress_thresholds` and `signal_weights`)
2. Build `gating_facts.py` with the 6 gating-fact detectors
3. Build `fundamentals_scorer.py` with the 4 component scorers (profitability, cash generation, leverage, liquidity)
4. Build `cycle_classifier.py` with the 4 classification tests and heuristic cycle dating
5. Build `band_overrides.py` with the 2 override rules (O1 insolvency + going concern, O2 insolvency + cash burn + illiquidity)
6. Build `distress_scorer.py` as the orchestrator: combines gating + fundamentals + capped signals, applies overrides
7. Integrate into existing report pipeline, replacing the intensity-score computation
8. Update report templates (executive summary cover block showing score composition line and override line when applicable, pattern detection header)
9. Remove legacy score from all surfaces (§10)
10. Run sanity checks (§9) against Braskem and Suzano reports — including the synthetic O1 and O2 override tests in §9.3
11. Add unit tests: one per gating fact, one per fundamental component boundary, one per classification test, one per band boundary, one verifying the signal cap bites, one per override rule (verifying both fire and non-fire cases), one verifying O1 wins over O2 when both match

---

## 12. Out of Scope (explicit)

- External sector price feeds (pulp prices, naphtha-to-resin spreads). V2.
- Forward-looking distress prediction. V2.
- Peer benchmarking within sector. V2.
- Automated sector classification from filings. Use existing mapping.
- UI changes beyond the executive summary cover block. Separate design work.

---

## 13. Open Questions for Implementation Review

1. Should `DEFAULT` sector config use median values across existing sector configs, or conservative values that tend toward flagging? Recommendation: conservative, with a visible warning.
2. When a company triggers both G04 and G05, G05 wins — confirm this is acceptable given that G04 is a simpler signal CFOs may want to see independently in the findings list even if not double-scored.
3. For the heuristic cycle dating, what happens when a company's analysis window does not contain an obvious peak-trough pattern (e.g., steady decline throughout)? Recommendation: cycle position defaults to `unknown`, and Test 2 (base-effect check) is skipped for that company.
4. Should the band labels be localized (PT-BR) given the CVM-sourced data? Recommendation: yes, but as a display layer, not in the core scoring output.
