# Pilot rollout Runbook — Power-spec kit (Step 6)

Purpose: Operationalize LLM-assisted spec-to-test authoring for **power modes** across one pilot ECU/feature slice before widening adoption.

---

## Prerequisites
- Repo path contains `power-spec-kit/` artefacts (schema, scripts, prompts, templates).
- Python **3.11+** installed; `pip install -r requirements.txt` for YAML tooling.
- `condition_index.json` generated from authoring sources (CSV primary).
- Stakeholders agree on glossary ownership (`docs/style-guide-jp.md` filled-in section).

---

## Pilot scope guardrails
1. Freeze **maximum 15** `COND_###` identifiers for iteration 1 to bound review churn.
2. Select only requirements with **measurable predicates** — defer narrative-only bullets.
3. Pair every pilot triplet with a **hardware or HIL analogue** reviewer sign-off checklist item.

---

## Phase A — ingest & classify
1. Export Excel rows to UTF-8 CSV (`Save As → CSV UTF-8` on Windows, `UTF-8` on macOS).
2. Run `python3 scripts/ingest_conditions.py --csv your.csv --out condition_index.json`.
3. Triage `unresolved_references[]` with domain experts; either attach evidence or mark `WONT_FIX` with rationale in tracker.

## Phase B — LLM IR extraction
1. Feed `prompts/extract_ir.md` + `condition_index.json` + completed glossary.
2. Validate each node against `schema/condition_ir.schema.json` (`#/$defs/condition_ir`).
3. Store output beside repo as `ir/pilot_power_ir.json` (example path) under version control.

## Phase C — triplet drafting & review
1. Run `prompts/draft_spec_triplets.md` using IR + style guide.
2. Manual pass per `prompts/review_spec.md`.
3. Execute `python3 scripts/validate_spec.py pilot_tests.yaml --ir-index condition_index.json --strict`.

## Phase D — test skeleton & CI hook
1. Apply `prompts/generate_gtest.md` with `templates/gtest_test.cpp.template`.
2. Wire tests into existing harness; ensure compile on pilot branch.
3. Add CI job step: `validate_spec.py` with `--strict` on committed YAML.

## Phase E — retrospective & scale decision
| Metric | Target for exit |
| --- | --- |
| IR merge lead time | ≤ 2 business days |
| Unresolved references | 0 CRITICAL |
| Validator strict pass | Green on pilot suite |

Document lessons; expand scope **only after** glossary + toolchain owners sign.

---

### Rollback
If pilot violates schedule, revert to manual spec authoring **without deleting** artefacts—archive `condition_index.json` snapshot tagged by date.
