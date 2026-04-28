# Knowledge Directory — Cygnus Reasoning Engine

This directory contains the YAML knowledge files that drive the deterministic
reasoning layer between Step 6 (signal detection) and Step 7 (AI narrative).

The domain expert owns these files. They are the single source of truth for
what financial mechanisms Cygnus can recognize and explain.

---

## Files

| File | Purpose |
|---|---|
| `canonical_concepts.yaml` | Minimal canonical finance vocabulary (15 concepts) |
| `financial_relationships.yaml` | Financial mechanism registry (15 relationships) |
| `explanation_templates.yaml` | Diagnosis-to-explanation mappings (5 templates) |
| `suggestions/` | Auto-generated suggestions for expert review (Sprint B) |

---

## canonical_concepts.yaml

Defines the normalized financial vocabulary that findings and relationships
reference. Each concept has an `id` (the YAML key), a `label`, and a
`category`.

### Format

```yaml
concept_id:
  label: "Human-Readable Name"
  category: performance | working_capital | cash | capital_structure
```

### Categories

- `performance` — P&L concepts (revenue, cogs, gross_profit, ebitda, net_income)
- `working_capital` — balance-sheet working-capital concepts (AR, inventory, AP, WC, CCC)
- `cash` — cash-flow concepts (OCF, FCF, capex)
- `capital_structure` — leverage and equity concepts (debt, equity)

### How to add a new concept

1. Add a new YAML entry with a unique snake_case key.
2. Set `label` (display name) and `category` (one of the four above).
3. Reference the new concept in any relationships that involve it.
4. Add the concept to the `ALGORITHM_CONCEPTS` mapping in
   `backend/pipeline/reasoning_engine.py` for any algorithm that touches it.

---

## financial_relationships.yaml

Defines known financial mechanisms. Each relationship describes a causal
pattern that the reasoning engine matches against Step 6 findings.

### Format

```yaml
relationship_id:
  description: "Human-readable explanation of the mechanism"
  category: profitability | balance_sheet | cash_flow | governance | cross_module

  concepts:
    core: [concept_id, ...]              # Canonical concepts involved
    driver_candidates: [concept_id, ...] # What might be driving the pattern
    outcome_concepts: [concept_id, ...]  # What is affected downstream

  requires:
    - algorithm: normalized_algorithm_name
      condition: "optional condition expression"  # omit for unconditional match
    - algorithm: another_algorithm
      # no condition = matches if any finding with this algorithm exists

  distinguishers:                        # optional
    - check: "condition_expression"
      if_true: "Interpretation when condition is true"
      if_false: "Interpretation when condition is false"

  connects_to: [other_relationship_id, ...]  # downstream effects
  weight: 1.0                                # scoring weight (default 1.0)
```

### Concepts block

Every relationship must have a `concepts` block with three sub-keys:

- `core` — all canonical concepts that this mechanism involves.
- `driver_candidates` — concepts that could be the root cause.
- `outcome_concepts` — concepts that are affected as a downstream consequence.

All concept references must exist in `canonical_concepts.yaml`. The loader
validates this at startup.

### Condition language

Conditions are simple expressions evaluated against a finding's fields:

| Pattern | Example | Meaning |
|---|---|---|
| Equality | `direction == 'deteriorating'` | String match |
| Numeric comparison | `divergence_pp > 10` | Greater-than |
| Membership | `severity in ['HIGH', 'CRITICAL']` | Value in list |
| Compound | `divergence_pp > 20 and revenue_change_pct < -10` | All must match |
| No condition | *(omit the field)* | Matches any finding with the algorithm |

Supported operators: `==`, `!=`, `>`, `<`, `>=`, `<=`, `in`.

Fields are resolved first from the finding's top-level keys (e.g., `severity`),
then from `data_points` (e.g., `direction`, `divergence_pp`).

### How to add a new relationship

1. Choose a unique snake_case `relationship_id`.
2. Write a `description` (one sentence, what the mechanism is).
3. Set `category` (profitability / balance_sheet / cash_flow / governance / cross_module).
4. Fill the `concepts` block — reference only concepts from `canonical_concepts.yaml`.
5. Add `requires` entries — each names an algorithm (normalized name from
   `reasoning_engine.py`'s `ALGORITHM_CONCEPTS`) and an optional condition.
6. Optionally add `distinguishers` — conditions that refine the interpretation.
7. Set `connects_to` — list of downstream relationship IDs this can chain to.
8. Set `weight` (default 1.0; lower for speculative relationships, higher for
   amplifiers like auditor confirmation).

---

## explanation_templates.yaml

Maps each stacked diagnosis (produced by `signal_stacker.py`) to its candidate
explanations, each referencing a relationship from the registry.

### Format

```yaml
DX-N_diagnosis_name:
  candidate_explanations:
    - relationship: relationship_id       # from financial_relationships.yaml
      label: "Human-readable label"
      score_boost: 1.0                    # multiplier for scoring (default 1.0)
      condition: "optional filter"        # only include if condition is met

  primary_selection: highest_score        # how to pick the primary explanation

  chain_instruction: >
    Narrative guidance for the LLM when using this explanation as the
    primary chain. Tells the LLM how to frame the causal story.
```

### How to add a new template

1. Use the diagnosis key from `signal_stacker.py` (e.g., `DX-6_new_diagnosis`).
2. List candidate explanations — each references a relationship by ID.
3. Set `score_boost` (1.0 = root cause weight; 0.8 = consequence weight).
4. Write a `chain_instruction` — narrative guidance for the AI agent.

---

## suggestions/ directory

Auto-generated by the suggestion engine (Sprint B). Contains:

- `pending_review.yaml` — new relationship candidates from unmatched findings
- `accepted.yaml` — suggestions accepted by the domain expert
- `rejected.yaml` — suggestions rejected (with reason)

Domain expert reviews pending suggestions and promotes or rejects them.
Accepted entries are manually added to `financial_relationships.yaml`.

---

## Relationship to the codebase

```
canonical_concepts.yaml
        ↓ validated by
reasoning_engine.py: load_canonical_concepts()
        ↓ used to validate
financial_relationships.yaml
        ↓ loaded by
reasoning_engine.py: load_relationships()
        ↓ used by (Sprint B)
evidence_chains.py + explanation_ranker.py
        ↓ output consumed by
Step 7 AI Agent (constrained narrative)
```

The full reasoning flow is described in the spec at
`sprint-reasoning-engine.md`. This README documents the YAML formats
for anyone maintaining the knowledge files.
