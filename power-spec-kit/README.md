# Power-spec kit

Self-contained workflow assets for **LLM-assisted power-mode specification and GoogleTest scaffolding**.  
All paths below are relative to this directory unless noted.

| Area | Path |
| --- | --- |
| IR JSON Schema (single node via `$ref`) | [`schema/condition_ir.schema.json`](schema/condition_ir.schema.json) |
| Example IR bundle | [`examples/sample_ir.json`](examples/sample_ir.json) |
| JP style guide & synthetic gold triplets | [`docs/style-guide-jp.md`](docs/style-guide-jp.md) |
| Pilot rollout (Step 6 plan) | [`docs/pilot-runbook.md`](docs/pilot-runbook.md) |
| Ingestion CLI | [`scripts/ingest_conditions.py`](scripts/ingest_conditions.py) |
| Spec validator | [`scripts/validate_spec.py`](scripts/validate_spec.py) |
| LLM prompt pack | [`prompts/`](prompts/) |
| GTest skeleton | [`templates/gtest_test.cpp.template`](templates/gtest_test.cpp.template) |

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt                    # PyYAML for YAML specs
```

### 1. Ingest spreadsheet export (primary path)

1. In Excel, export the sheet as **CSV UTF-8** (comma, tab, pipe, or semicolon delimiters are detected heuristically).
2. Run:

```bash
python3 scripts/ingest_conditions.py \
  --csv path/to/conditions.csv \
  --out condition_index.json \
  --meta-source-label "program-x phase-2"
```

The command prints counts on stderr; JSON contains `conditions[]`, `unresolved_references[]`, and `metadata`.

Expected headers (Japanese aliases supported — see alias table inside the script):

| Canonical concept | Example English headers |
| --- | --- |
| Title | `title`, `Condition` |
| Applies-to | `applies_to`, `scope`, `ECU` |
| Given / predicates | `givens`, `signals`, `predicates` |
| Dependencies | `dependencies`, `COND_003` comma separated |
| Evidence | `file`, `section` / `sheet` / `page` |

**Structured givens** — If `givens` looks like `SIG==value; BATT>=9.0`, the ingestor emits real IR predicates; otherwise it preserves natural language under `signal: INGEST_NATURAL_LANGUAGE`.

### 2. Optional Word plaintext dump

Export the Word document to `.txt`. Separate logical clauses with blank lines or horizontal rules. Then:

```bash
python3 scripts/ingest_conditions.py \
  --text-word-dump path/to/spec_dump.txt \
  --out condition_index.json
```

### 3. Validate Description / Given / Expectation manifests

YAML (requires PyYAML):

```yaml
testcases:
  - test_id: TST_PWR_20260101_001
    description: "..."
    given: "..."
    expectation: "..."
    ir_refs:
      - COND_007
```

JSON works without extra deps (`examples/sample_testcases.json`):

```bash
python3 scripts/validate_spec.py examples/sample_testcases.json \
  --ir-index examples/sample_condition_index.json \
  --strict
```

### Checks performed

| Check | Severity | Notes |
| --- | --- | --- |
| Missing/blank canonical keys | Error | Requires `description`, `given`, `expectation`, `test_id`; optional `ir_refs` must be strings |
| Thin natural language | Warn | Fewer than two alphanumeric tokens |
| Predicate token overlap | Warn | Compared to IR predicate tokens when `--ir-index` + `ir_refs` provided; placeholders `signal: INGEST_*` only contribute via their string `value` |
| Duplicate descriptions | Warn | Pairwise Jaccard similarity ≥ `--dup-description-threshold` |

### Synthetic sample loop

```bash
python3 scripts/ingest_conditions.py --csv examples/sample_conditions_export.csv --out examples/sample_condition_index.json
python3 scripts/validate_spec.py examples/sample_testcases.json --ir-index examples/sample_condition_index.json --strict
```

## LLM usage order

1. `prompts/extract_ir.md` — structured IR from ingestion output.  
2. `prompts/draft_spec_triplets.md` — triplet YAML/JSON authoring.  
3. `prompts/review_spec.md` — reviewer checklist + `validate_spec.py` gate.  
4. `prompts/generate_gtest.md` — produce test TU snippets using `templates/gtest_test.cpp.template`.

## Dependencies

- **Python**: 3.11+ (`ast` pattern matching not required; stdlib CSV/JSON/regExp only for ingest).
- **`requirements.txt`**: `PyYAML` for YAML testcase files & future tooling symmetry.

Optional `openpyxl` **not** shipped—Excel authors should export CSV to keep the kit dependency-free beyond PyYAML.

## Schema notes

- `schema/condition_ir.schema.json` validates **one** node via root `$ref` to `#/$defs/condition_ir`.
- Bundled manifests (`sample_ir.json`, `condition_index.json`) wrap nodes in `{ "conditions": [ ... ] }`; validate nodes individually against `$defs.condition_ir`.

## Contributing / extending

Keep scripts single-purpose:

- Extend header aliases inside `HEADER_ALIASES` rather than branching ad hoc.
- Prefer recording questionable references inside `unresolved_references[]` instead of silently dropping text.
