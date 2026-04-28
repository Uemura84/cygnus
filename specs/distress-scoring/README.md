# Cygnus Distress Scoring — Test Fixtures

Test fixtures for validating the distress scoring engine against the four sanity checks in spec §9.

## Files

| File                              | Purpose                                              | Expected band    | Expected score |
| --------------------------------- | ---------------------------------------------------- | ---------------- | -------------- |
| `braskem.json`                    | Real distressed company — petrochemical sector       | Severe Distress  | 100            |
| `suzano.json`                     | Real cyclical company — pulp sector                  | Stable           | 23             |
| `synthetic_s1_o1_test.json`       | Synthetic — validates O1 override moves band         | Distress         | 80             |
| `synthetic_s2_o2_test.json`       | Synthetic — validates O2 override moves band         | High Risk        | 60             |
| `synthetic_s3_guardrail_test.json`| Synthetic — validates 10pp cycle guardrail fires     | Healthy          | 13             |
| `expected_outputs.json`           | Expected `DistressScoreResult` for each fixture      | —                | —              |
| `sector_configs.json`             | Sector config stubs (PETROCHEMICAL, PULP, DEFAULT)   | —                | —              |
| `validate_fixtures.py`            | Reference implementation — run to self-check         | —                | —              |

## Fixture schema

Each fixture is a JSON object with five top-level keys:

```json
{
  "company": { "name": "...", "sector_id": "..." },
  "analysis_window": {
    "latest_annual_period": "2025-12-31",
    "annual_periods": [ ... ]
  },
  "gating_inputs": { ... },       // direct inputs for each gating fact G01-G06
  "fundamentals_inputs": { ... }, // latest annual values + last-3-year FCF
  "findings": [ ... ]             // pattern detection outputs from existing algorithms
}
```

The fixtures supply the exact inputs each scoring layer needs. They do NOT contain the full CVM filing data — only what the scoring engine consumes.

## How to use

1. Load `sector_configs.json` into your sector config store.
2. For each fixture file, feed it to `compute_distress_score(...)`.
3. Compare the result against the matching entry in `expected_outputs.json`.
4. All four must pass before shipping.

## Tolerance

Score comparisons are exact integers. Band comparisons are exact strings. No tolerance — the scoring math is deterministic.

If a test fails:

- **Score off by 1–3 points** → check cycle-multiplier arithmetic (0.3 × weight rounding)
- **Score off by 5+ points** → check gating-fact or fundamentals weights in sector config
- **Band correct but override fields missing** → check that override logic emits `pre_override_score`, `pre_override_band`, `override_applied`
- **Braskem passes but S1 fails** → O1 override logic is broken (Braskem masks the bug because it scores 100 without override)
- **Braskem/Suzano pass but S3 fails** → 10pp cycle guardrail is not implemented or is being bypassed. The real-company fixtures both have margin ranges above 10pp so they cannot detect a broken guardrail.

## On the synthetic cases

S1, S2, and S3 are deliberately constructed to exercise logic that real companies mask:

- **S1** forces the O1 override to actually *move* the band (Braskem already scores 100 naturally).
- **S2** forces the O2 override to activate independently of O1.
- **S3** forces the 10pp cycle-dating guardrail to fire (Braskem at 28.2pp range and Suzano at 17.8pp range both pass the guardrail without firing it).

These synthetics are the only fixtures that exercise their respective logic in isolation. Do not remove them.
