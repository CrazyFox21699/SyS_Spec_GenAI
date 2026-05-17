# Power mode spec pipeline (starter kit)

Implements part of your **LLM-assisted power‑mode specs** workspace plan (see `llm-assisted_power-mode_specs_*` under your Cursor `.cursor/plans` directory). Use together with **whitelisted Ollama** (batch) and **Copilot** (IDE).

## Contents

| Path | Purpose |
|------|---------|
| `schemas/condition-ir.schema.json` | Canonical JSON Schema for conditions + testcase traceability (`COND_*`, `ST_PWR_*`). |
| `examples/sample_testcase_bundle.yaml` | Minimal worked example JA/EN-ish fields and predicate structure. |
| `STYLE_GUIDE.jp-customer.template.md` | Tone, uniqueness rules, glossary + gold-sample slots for few-shot prompting. |
| `prompts/*.md` | Copy into Ollama / Copilot: extract IR → draft spec → QA → `gtest` skeleton. |

## Suggested workflow

1. Export Excel snippet + referenced Word headings → Prompt **01** → fill `conditions` in YAML/JSON.  
2. Build `test_cases[]` tying `linked_conditions`.  
3. Prompt **02** + style guide → customer **Description / Given / Expectation**.  
4. Prompt **03** until `VERDICT: APPROVED`.  
5. Prompt **04** → paste stubs into repo test tree; bind to your harness APIs manually.

## Next steps (outside this repo)

- Add a CSV/Excel ingestion script (`ingestion-index` in plan todos).  
- Optional: terminology linter script + fuzzy duplicate Description warning over all `*.yaml`.

## No secrets

Keep customer documents inside policy boundaries; prompts should include only redacted or approved excerpts.
