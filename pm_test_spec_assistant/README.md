# ALEX (v0.2 upgrade)

**ALEX** (working name) is a local tool for automotive / power-mode engineers: **classify** customer documents, **extract** control logic with **evidence trace**, **review** and **approve** understanding, then export `TestSpec_<Module>_EN.xlsx` or `TestSpec_<Module>_JP.xlsx`.

Code lives in `pm_test_spec_assistant/` during upgrade (folder rename to `alex/` planned later).

- **Deterministic-first** — AND/OR/NOT structure comes from fixed parsers, not from AI.
- **Review-first** — issues and vague areas are surfaced; unsafe candidates are blocked.
- **Local-first review** — deterministic parser owns structure, while local Copilot CLI and local OCR can assist under explicit guardrails.

**Current scope:** final workbook review, definition tracing, Copilot-assisted rewrite, and local OCR for diagram text / embedded images.

---

## What this tool is / is not

| Expectation | Reality |
|-------------|---------|
| Built-in Copilot | **Yes, via local Copilot CLI device login and runtime check.** |
| Auto-approved test cases | **No.** Candidates are `blocked` / `review_required` when logic is unclear. |
| Perfect parsing of any Word table | **No.** Two-column control tables are the main strength; complex merges may be `partial` or `failed`. |
| Diagram understanding | **Partial.** Local OCR reads visible text from images, Word embedded images, and PDF embedded images; full shape/layout semantics are still not automatic. |
| RAG / chatbot replacement | **No.** Self-contained extraction and review pipeline. |

---

## Design center: traceability chain

```text
Signal value change → condition tree → state transition → hardware/interface output → test scenario candidate
```

Principles:

1. **Deterministic core, probabilistic assist** — parsers own structure; any LLM is advisory only.
2. **Fail closed** — unknown or ambiguous logic → issue + blocked candidates, never silent TRUE/FALSE.
3. **Excel is the contract** — primary deliverable for engineers; YAML/MD for debug and automation.
4. **Human sign-off** — export warns when blocking errors remain in strict mode.

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│  Inputs: .docx, .xlsx, .pdf, images, .cpp/.h                │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  src/pipeline.py — run_analyze()                            │
│  • classify → extract → reconcile → condition trees         │
│  • issues + unresolved refs → candidates + safety           │
│  • final workbook review + AI queue + capability summary  │
│  • Excel + review MD + ui_bundle.yaml                       │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌──────────────────────┐  ┌──────────────────────────────────┐
│  CLI: app.py         │  │  Web: run_web.py → web/main.py   │
│  --input --output    │  │  http://127.0.0.1:8765           │
└──────────────────────┘  └──────────────────────────────────┘
```

| Layer | Location | Role |
|-------|----------|------|
| CLI | `app.py` | Batch `analyze --input --output` |
| Web UI | `run_web.py`, `web/` | FastAPI + static SPA |
| Pipeline | `src/pipeline.py` | Single orchestration entry |
| Parsers | `src/parsers/` | Word, Excel, PDF, two-column tables, code |
| Engine | `src/engine/` | AST, issues, traceability, candidates, understanding |
| Classifiers | `src/classifiers/` | Four engineer-facing file types |
| Export | `src/exporters/excel_exporter.py` | Excel workbooks |
| Copilot bridge | `web/copilot_bridge.py` | Local Copilot CLI login, runtime verification, row rewrite |
| Local OCR | `src/parsers/ocr_local.py` | Diagram / embedded-image OCR and structure hints |

---

## Supported file types

### Engineer-facing types (web UI)

| UI label | Typical extensions | Pipeline role |
|----------|-------------------|---------------|
| **System Spec** | `.docx`, `.pdf` | Main extraction, two-column logic tables |
| **Test Spec** | `.xlsx`, `.xlsm` | Reference rows, test patterns |
| **Sample Code** | `.cpp`, `.h` | Reference (`TEST_F`, etc.) |
| **Test Code** | `.cpp`, `.h` | Same ingest path as sample code |

Also ingestible: images (`.png`, …) as **diagram** metadata, `.md`, etc. Word lock files (`~$…`) are rejected.

### Heuristic classification (CLI / config)

| Kind | Extensions | Detection |
|------|------------|-----------|
| System specification | `.docx`, `.pdf` | Signal / interface keywords, tables |
| Behavior / logic | `.xlsx`, `.xlsm` | State-name patterns, transition-like rows |
| Test reference Excel | `.xlsx` | Test-spec keywords in sheets |
| Diagrams / timing | `.pdf`, images | PDF text layer; images → metadata only |
| Code reference | `.cpp`, `.h`, … | `TEST_F`, `EXPECT_EQ`, … |

Sample inputs: `../pm_sample_inputs/` (e.g. `edited_Shutoff_Condition_Spec.docx`, files under `input/`).

---

## Install

```bash
cd pm_test_spec_assistant
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npm install -g @github/copilot
brew install tesseract
```

`Tesseract` is optional but strongly recommended. Without it, image and embedded-diagram OCR fall back to metadata only.

---

## Run — Web UI (recommended)

```bash
python run_web.py
```

Open **http://127.0.0.1:8765** (hard-refresh if the UI looks stale after updates). The app shows a short Toyota welcome splash once on initial page load, using the flat borderless logo at `web/static/img/toyota-logo-flat.png`, then fades into the normal workflow.

### Web tabs (current)

| Tab | Purpose |
|-----|---------|
| **1. Review** | Upload / classify files, sign in to M365 and/or GitHub Copilot CLI, then run one analysis pass |
| **2. Logic & Definitions** | Per logic group: compare Tree vs Raw expression, inspect collapsed source evidence, resolve definitions, select AI provider, and review affected workbook rows. Large jobs use compact dropdown selectors for logic groups, definition terms, and test cases instead of hundreds of chips |
| **3. Diagram Graph** | Validate detected states/transitions and source evidence when the spec includes state-machine or diagram content |
| **4. Library** | Polarion-style trace canvas. Pick a local folder as the library root, then build a focus + spokes diagram: drop a file from Finder/Explorer onto a slot (auto-copied into the library folder) **or** click an empty slot to browse the folder and pick. Each row carries a free-form relationship label (e.g. `Satisfies`, `Validated By`, `Implemented By`); `+` adds another slot to a row, `+ Add relationship` adds a new row |
| **5. Final File** | Review/edit the final `System Test Spec` shape and export EN or JP workbook |
| **6. Guide** | In-app operator manual: workflow, AI provider usage, Resolve with AI, status meanings, and troubleshooting |

### Quick start (web)

1. Open **Spec review**.
2. Click **Load sample package** (copies `pm_sample_inputs` into `web_data/uploads/`) or **Upload** your files.
3. Check the spec file(s) and set **Type** if the automatic label is wrong.
4. Click **Review specification**.
5. When progress completes, open **Logic & Definitions**.
6. Fix missing terms in **Logic & Definitions**. Use **AI provider** = `Auto`, `M365`, `GitHub Copilot CLI`, or `Ollama`, then click **Resolve with AI**.
7. If needed, open collapsed **source table / detected context** beside the Logic Tree to verify the original table or nearby state-machine context.
8. Open **Library** (Tab 4) and paste an absolute path to your local spec folder. Drag a file from Finder/Explorer onto the focus card to set the centre item, then drop more files onto each spoke slot. Click the relationship label to rename it (free-form: `Satisfies`, `Validated By`, etc.); use the `+` at the end of a row to add another slot, or **+ Add relationship** to start a new row. Slots accept OS drops (file is copied into the library folder) or clicks (browse the local folder and pick) — no other info is stored.
9. Review/edit the workbook in **Final File**. Generated, cloned, and manual test cases can be soft-deleted from the focused test case editor before export.
10. Use **Guide** when you need the in-app workflow, provider notes, or troubleshooting.

### Top bar

- **Job** — short id of the last review run
- **Selected** — `N / total` files checked for the next run
- **Rows Ready / Rows Blocked / Missing Terms / Logic Groups** — final workbook review health

### Persistence

| Location | Contents |
|----------|----------|
| `web_data/uploads/` | Uploaded / sample-copied files |
| `web_data/output/analysis_YYYYMMDD_HHMMSS_<id>/` | One folder per review run |
| `web_data/output/<job_id>/reasoning/<logic_id>/session.json` | Per-logic reasoning session: prompt/evidence hashes, turns, open questions, hypotheses |
| `web_data/m365/session.json` | Local M365 OAuth session (gitignored); access tokens refresh automatically until Microsoft requires sign-in again |
| Browser `localStorage` | Last `job_id` (reloads summary from disk on startup) |

### AI providers + OCR guardrails

- The deterministic parser still owns AND/OR/NOT structure.
- **Resolve with AI** uses the selected provider:
  - `Auto`: try M365, then GitHub Copilot CLI, then Ollama when enabled/reachable.
  - `M365`: Microsoft Graph Copilot chat; requires Azure app login and Copilot license.
  - `GitHub Copilot CLI`: local CLI fallback; `AUTH OK` means the machine has an existing Copilot CLI login.
  - `Ollama`: offline/experimental fallback, not the primary complex-logic path.
- AI patches are validated before they become trusted workbook rows. Evidence gaps should become review-required/open questions, not silent export-ready changes.
- Reasoning sessions are stored per logic group so future Copilot/M365 turns can be audited by prompt hash and evidence hash. AI hypotheses now pass through a cited-claim guardrail (`schemas/reasoning_hypothesis.schema.json`): executable claims and testcase patch plans need citations, otherwise they are kept review-required/open-question instead of silently trusted.
- Testcase reconciliation is tracked for every knowledge apply. Provider patches are classified as `update_existing`, `add_new`, `retire`, or `needs_review`, with citation status and a summary saved under `ai_assists.knowledge_apply[logic_id].reconciliation`.
- M365 device-code login is persistent on this machine. Sign in again only after Sign out/Clear, deleted `web_data/m365`, token expiry, or revoked consent.
- Local OCR reads visible text from image attachments, embedded Word media, and embedded PDF page images.
- OCR text is still review-required; shape/layout semantics are not treated as fully trusted logic.

---

## Run — CLI

```bash
python app.py analyze --input ./input --output ./output
```

| Flag / config | Meaning |
|---------------|---------|
| `--force` | Skip backup of existing artifacts before overwrite |
| `config.yaml` | State patterns, keywords, timing, strict mode, LLM toggle |

Subcommands `classify`, `extract`, `generate-review`, `generate-test-spec` print guidance; **full flow is `analyze`**.

---

## Processing pipeline (`run_analyze`)

Approximate order:

1. **Classify** selected files → `classified_files.yaml`
2. **Extract** by type: signals, Word logic blocks, Excel transitions, condition definitions, two-column tables, footnotes/aliases, code refs, diagram metadata
3. **Reconcile** logic blocks across sources
4. **Build condition trees** and **normalize timing**
5. **Collect issues** and **unresolved** condition references (fail-closed)
6. **Generate test candidates** (logic, transitions, references)
7. **Apply candidate safety** — block when parse is `failed` / `partial` or strict blocking issues exist
8. **Build logic review items** — one card per control for the UI
9. **Build spec understanding report** — % understood, gaps, clarification prompts
10. **Export Excel**, review markdown, and `ui_bundle.yaml`

**Strict mode** (`config.yaml` → `ui.strict_mode: true`, default): blocking errors affect export messaging; unsafe candidates stay blocked.

**Ollama** (`llm.enabled` in config, default `false`): optional Japanese interpretation only; **not** used for logic structure in the web UI (`enable_ollama: false` on every review request).

---

## Logic parsing (core skill)

Specialized path for **Word two-column control tables** (Logic | Condition):

| Module | Role |
|--------|------|
| `src/engine/indentation_ast_parser.py` | Row path / column depth; OR+AND pairs; AND-root multi-column; fail-closed on ambiguous mixed paths |
| `src/engine/two_column_logic_parser.py` | Footnotes, aliases, `parse_table_to_logic_block` |

Per control output includes: `parse_status` (`ok` \| `partial` \| `failed`), expression string, AST, `parser_reason`, source references.

Gate-spine / boolean flag notes:

- Raw expression can be readable even when some tree leaves need review.
- Signal-only predicates such as `PWR_REQ_VALID`, `VEHICLE_SAFE`, or `NORMAL_ROUTE` are treated as boolean predicates (`== 1`) when safe.
- Remaining `opaque` leaves should show raw text and keep review status honest.
- Logic Review keeps source evidence collapsed by default; open **Show source table / detected context** only when you need to compare against the original table or state-machine evidence.
- For Word/Excel control tables, ALEX carries a visual source snapshot (table-like preview from original cells) beside the Logic Tree instead of showing long repeated row locators by default.

Excel transition detection remains **heuristic** (state-like tokens in rows).

Unit tests: `tests/test_indentation_ast_parser.py`.

---

## Spec understanding report

Built in `src/engine/spec_understanding_report.py`, stored in `ui_bundle.yaml` as `spec_understanding`.

| Field | Meaning |
|-------|---------|
| `overall.understanding_percent` | 0–100: OK controls minus penalties for errors / partial / failed |
| `overall.status` | `good` \| `partial` \| `low` |
| `overall.headline` | Short summary for engineers |
| `gaps[]` | Incomplete parse, errors, unresolved condition names |
| `copilot_prompt` (per gap) | Strict “quote source only” text for optional paste into IDE |

Older jobs on disk without this field get it **recomputed on load** (`web/bundle_helpers.py`).

---

## Outputs

### Per job (`output/` or `web_data/output/<job_id>/`)

| File | Meaning |
|------|---------|
| `ui_bundle.yaml` | Web + machine state: logic, issues, candidates, understanding, summary |
| `classified_files.yaml` | File type and reasons |
| `extracted_signals.yaml` | Signal registry (best-effort) |
| `state_machine.yaml` | States + transition rows |
| `condition_trees.yaml` | Condition AST + timing notes |
| `logic_blocks.yaml` | Control logic blocks |
| `timing_constraints.yaml` | Normalized timing |
| `traceability.yaml` | Transition context + trace rows |
| `generated_test_spec.yaml` / `.md` | **Candidates only** |
| `japanese_interpretations.yaml` | JP snippets + optional LLM hypotheses |
| `review/01_*.md` … `08_*.md`, `review_questions.md` | Human review package |

### Excel exports (web **Export** tab)

| Download | Content |
|----------|---------|
| `generated_test_spec.xlsx` | Test spec candidates |
| `review_package.xlsx` | Two-column rows, logic AST, review data |
| `logic_traceability.xlsx` | Traceability matrix / path coverage |
| `issue_list.xlsx` | Issues for tracking |

---

## Review-first workflow

### CLI

1. Run `analyze`.
2. Read `output/review/01_*.md` through `08_*.md` and `review_questions.md`.
3. Fix `config.yaml` or source documents; re-run.
4. Treat `generated_test_spec.*` as a starting point only after review.

### Web

1. **Spec review** — run review, read % understood and gaps.
2. **Logic review** — verify each control’s table, tree, and expression.
3. **Issues** — resolve blocking errors before trusting export.
4. **Export** — download Excel for formal process.

---

## Safety and review rules (enforced in code)

- Every important item can carry `source_status`, `confidence`, `review_required`, `review_status`.
- Issues and `unresolved_items` are not hidden.
- LLM output is advisory only (`source: llm_generated`).
- **Candidate safety** (`src/engine/candidate_safety.py`) blocks candidates linked to failed/partial logic.
- Strict clarification prompts forbid inventing logic structure.

---

## Web API (main endpoints)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/upload` | Add files to uploads |
| POST | `/api/load-sample` | Copy sample inputs into uploads |
| GET | `/api/files` | List files + selection |
| POST | `/api/files/select` | Save selection and file type |
| POST | `/api/analyze` | Start background review |
| GET | `/api/analysis/status` | Progress (in-memory or disk) |
| GET | `/api/review/dashboard` | Spec review screen payload |
| GET | `/api/review/spec-understanding` | Understanding % and gaps |
| GET | `/api/review/logic-review` | Logic review cards |
| GET | `/api/issues` | Issue list |
| GET | `/api/jobs`, `/api/jobs/{id}/summary` | Job list / summary |
| GET | `/api/export/*-xlsx` | Excel downloads |
| GET | `/api/export/ui-bundle` | Full `ui_bundle.yaml` |

---

## Configuration (`config.yaml`)

| Section | Purpose |
|---------|---------|
| `classification` | State regexes, keywords for file/signal/test detection |
| `timing` | Patterns and default interpretation for timing text |
| `llm` | `enabled: false` by default; Ollama URL/model if enabled |
| `output.backup_existing_files` | Backup before overwrite (CLI) |
| `ui.strict_mode` | Default strict behavior for web/ pipeline |

---

## Ollama (optional, CLI / config only)

Set `llm.enabled: true` and run Ollama locally (`base_url`, `model` in config).

- LLM output is tagged `source: llm_generated` with `review_required`.
- The tool **does not** use the LLM for final traceability or AND/OR/NOT parsing.
- The web UI does not expose an Ollama toggle; review requests send `enable_ollama: false`.

---

## Project layout

```text
pm_test_spec_assistant/
├── app.py                 # CLI entry
├── run_web.py             # Web server entry
├── config.yaml            # Classification, timing, strict mode, LLM off
├── requirements.txt
├── src/
│   ├── pipeline.py        # run_analyze()
│   ├── parsers/           # word, excel, pdf, two_column_table, code
│   ├── engine/            # AST, issues, candidates, understanding, traceability
│   ├── classifiers/       # file_classifier.py (4 UI types)
│   ├── exporters/         # excel_exporter.py
│   ├── llm/               # ollama_client.py (optional)
│   └── models/            # signal, state, condition, timing, testcase
├── web/
│   ├── main.py            # FastAPI routes
│   ├── jobs.py            # In-memory job registry
│   ├── bundle_helpers.py  # Backfill spec_understanding on load
│   └── static/            # index.html, app.js, style.css
├── web_data/
│   ├── uploads/           # User / sample files
│   └── output/            # analysis_<timestamp>_<id>/
├── tests/                 # Parser unit tests
└── docs/
    └── DESIGN_PLAN_COPILOT_LOOP.md   # Target Copilot-in-loop design notes
```

---

## Known limitations (v0.1)

- Excel transition detection is heuristic.
- Complex merged Word/Excel logic may stay `partial` / `failed` with explicit issues.
- Images are not interpreted (metadata + manual review).
- PDF quality depends on text layer.
- No in-app AI assistant — clipboard prompts only.
- Test Candidates is not a separate web tab (data remains in bundle and Excel).
- Understanding-only Excel sheet not exported separately (data in `ui_bundle.yaml` and UI).
- Full pipeline integration tests are limited; parser tests in `tests/`.

---

## Relation to other repo folders

This tree is **self-contained**. It does not modify `power-spec-kit/`, `power-mode-spec-pipeline/`, or other sibling projects. Sample inputs are read from `../pm_sample_inputs/` when using **Load sample package**.

---

## Further reading

| Document | Purpose |
|----------|---------|
| `docs/ALEX_M365_REASONING_UPGRADE_PLAN.md` | **Primary roadmap** — M365 co-reasoning for complex customer logic, auth tiers, phased delivery |
| `docs/DESIGN_PLAN_COPILOT_LOOP.md` | Original Copilot-in-loop UX (clipboard / IDE era) |
| `docs/COPILOT_PROMPTS.md` | Standard prompt templates per issue type |
| `docs/TEST_SPEC_IO_FORMAT.md` | Expected input/output column format |
