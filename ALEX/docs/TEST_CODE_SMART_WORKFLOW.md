# Test Code — Copilot orchestrator (default)

**Default path:** full testcase set via Copilot API — edit `project_instruction.md` only if needed.

```text
Import Excel → load sample .cc → Generate All with Copilot API → review NEEDS_REVIEW/ERROR → approve SAVED → Export Final .cc
```

Copilot Web fallback: Copy Batch Prompt + Import Batch Result (partial scopes in Advanced).

Smart Mode, YAML mapping, and config bundle import are **Advanced / fallback** only.

# Test Code — Smart Workflow (fallback)

## Default flow

1. **Import testcase Excel** (existing import flow).
2. **Load sample code** — upload `.cpp`, paste sample, or load project references.
3. **Analyze Project Context** — infers `code_rules.md`, `signal_mapping.yaml`, `api_catalog.yaml`, and `gtest_template.md` into project overrides from samples, drafts, and testcase I/O. No manual YAML required first.
4. **Check Coverage** (optional) — shows how many testcases are ready for local template generation.
5. **Auto-propose missing mappings** (optional) — proposes mappings with confidence and evidence; review in the table; **Accept selected** writes learned mappings only after you approve.
6. **Generate Code — Smart Mode** — analyze if config is sparse → propose mappings → auto-accept only ≥90% confidence → local template batch for ready cases → marks others for review.
7. **Review Issues** — filters to `NEEDS_REVIEW` / `ERROR`.
8. **Merge Saved Code** — unchanged; only `SAVED` snippets are merged.

## Config files

`code_rules.md`, `signal_mapping.yaml`, `gtest_template.md`, and `api_catalog.yaml` are **internal memory** stored under `bundle/code_config/layers/project_overrides/`. They are optional overrides; use **Advanced → Project Code Config** to edit or import a Copilot bundle.

## Copilot / API

- **Smart Mode** uses local template generation by default (`use_api_for_hard` is off).
- **Ask Copilot — copy mapping prompt** sends a compact prompt for missing mappings.
- Per-testcase Copilot Web/API and AI review pack remain under **Manual coding context & generation** and **Advanced**.

## Safety

- Inferred mappings below 90% confidence are **not** auto-applied.
- Each proposal includes confidence, source evidence, and affected testcase count.
- Quality gate and save/merge behavior are unchanged.

## Exemplar-based batch generation (default Copilot path)

Use when one testcase already has good code as a **style reference** for other rows in the same imported Test Group (no similarity regrouping).

1. Save good GTest code for one testcase.
2. **Mark as Exemplar** — stores Before/After, code, and sample context.
3. Filter testcases (case filter / navigation) to define targets.
4. **Copy Exemplar Batch Prompt** → paste into M365 Copilot web (or **Run Exemplar Batch API**).
5. **Import Exemplar Batch Result** — ALEX parses `[TESTCASE_CODE]` blocks, runs quality gate, sets SAVED / NEEDS_REVIEW / ERROR per case.
6. **Merge Saved Code** — unchanged (SAVED only).

Smart Mode / local template / config editors remain under Advanced as fallback.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/review/mark-code-exemplar` | Mark current testcase as exemplar |
| `POST /api/review/clear-code-exemplar` | Clear exemplar |
| `POST /api/review/exemplar-batch-prompt` | Build batched prompt(s) for targets |
| `POST /api/review/import-exemplar-batch` | Parse paste and attach per testcase |
| `POST /api/review/run-exemplar-batch-api` | Run exemplar batch via M365 API |

M365 background task kind: `code_exemplar_batch`.

## Run report

After **Analyze Project Context**, **Check Coverage**, **Auto-propose**, **Accept mappings**, or **Smart Mode**, the workflow bar shows a **Smart Workflow Run Report** with counts (SAVED / NEEDS_REVIEW / ERROR / mergeable), top missing signals, repeated quality issues, unknown APIs, and duplicate test names.

- **Copy Run Report** — copies Markdown to the clipboard
- **Export Run Report Markdown** — downloads `alex-smart-run-report-<job>.md`

Refresh anytime: `GET /api/review/smart-workflow-run-report?job_id=...`

## API endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/review/analyze-project-context` | Infer and write config overrides |
| `POST /api/review/propose-missing-mappings` | Build mapping proposals + Copilot prompt |
| `POST /api/review/accept-proposed-mappings` | Apply accepted proposals |
| `POST /api/review/generate-code-smart-mode` | End-to-end smart generation |
| `GET /api/review/smart-workflow-run-report` | Rebuild run report from current job state |

See also [CONFIG_BUNDLE_IMPORT.md](./CONFIG_BUNDLE_IMPORT.md) for Copilot bundle paste/import.
