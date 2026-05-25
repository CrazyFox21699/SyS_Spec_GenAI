# ALEX (v0.3 upgrade)

**ALEX** (working name) is a local tool for automotive / power-mode engineers: **classify** customer documents, **extract** control logic with **evidence trace**, **review** and **approve** understanding, then export `TestSpec_<Module>_EN.xlsx` or `TestSpec_<Module>_JP.xlsx`.

Code lives in `pm_test_spec_assistant/` during upgrade (folder rename to `alex/` planned later).

- **Deterministic-first** — AND/OR/NOT structure comes from fixed parsers, not from AI.
- **Review-first** — issues and vague areas are surfaced; unsafe candidates are blocked.
- **Local-first review** — deterministic parser owns structure, while local Copilot CLI and local OCR can assist under explicit guardrails.

**Current scope:** final workbook review, definition tracing, Copilot-assisted rewrite, and local OCR for diagram text / embedded images.

---

## Recent updates (May 2026)

| Area | What changed |
|------|----------------|
| **Condition tree parser** | `condition_tree_builder.py` splits top-level **OR before AND**, detects compound sub-expressions inside parentheses, and maps signal-only flags (`PWR_REQ_VALID`, `NORMAL_ROUTE`, …) to **boolean predicates** instead of `opaque` leaves when safe. |
| **Excel table-native AST** | New `gate_spine_ast.py` builds AST directly from Excel/Word **gate-spine rows** (token + Detail column). `excel_parser.py` uses this first, then falls back to text expression parsing. |
| **Diagram Graph UI** | Fixed **states = 0** bug: semantic graph nodes use field `state`, not `name`. Tab now shows states/edges from transition tables and OCR mentions correctly. |
| **Diagram inference** | `diagram_semantic_builder.py` infers missing `from_state` / `to_state` from arrow text in transition conditions (`OFF -> ACCESSORY`). |
| **Evidence display** | Compact source chips (`file › sheet · r64`) replace raw JSON locators in trace tables, logic source evidence, and readable source labels. |
| **Copilot brief workflow** | `brief_readiness.py` + enriched `m365_brief.py`: readiness banner (blockers/warnings) before **Copy brief**; `knowledge_patch_validation.py` gates import/apply; per-TC logic compliance in reconciliation panel. |
| **In-app Guide** | Tab **Guide** uses collapsible `<details>` sections (Vietnamese operator notes) with per-tab help links that jump to the right anchor. |
| **Logic reconciler** | Removed sample-specific alias hardcode (`SHUTOFF → SHUT_OFF_PERMISSION`); name matching is generic case-insensitive only. |
| **Golden regression** | `GPT_GenLogic.xlsx` in `../pm_sample_inputs/` is the structural regression fixture; `golden_spec_scoreboard.py` tracks parse/evidence metrics in tests. |
| **M365 auth tiers** | MSA / no-Copilot-license accounts show badge + auto-fallback; see [`docs/M365_COPILOT_ACTIVATION_GUIDE.md`](docs/M365_COPILOT_ACTIVATION_GUIDE.md). |
| **Rate limit (dev)** | `security.rate_limit_per_minute: 120` can trigger **HTTP 429** during heavy UI polling on localhost — increase limit or set `security.enabled: false` for local dev (see [Configuration](#configuration-configyaml)). |

**Hard-refresh** the browser after UI updates (`Ctrl+Shift+R` / `Cmd+Shift+R`); static assets are cache-busted via `?v=` on `app.js`.

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
| M365 co-reasoning | `web/m365_brief.py`, `web/m365_copilot.py` | Evidence brief + Graph Copilot Chat API |
| Local OCR | `src/parsers/ocr_local.py` | Diagram / embedded-image OCR and structure hints |
| Diagram semantics | `src/engine/diagram_semantic_builder.py` | Normalized state graph + evidence-backed edges |

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

Sample inputs: `../pm_sample_inputs/` — e.g. `edited_Shutoff_Condition_Spec.docx`, `GPT_GenLogic.xlsx` (Excel gate-spine + transition table structural fixture), files under `input/`.

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

## Run — Ubuntu công ty (khuyến nghị)

Trên máy Ubuntu **`10.88.152.11`** — tải **ZIP** từ GitHub (không cần `git clone`). Xem [`docs/HUONG_DAN_CAI_DAT_UBUNTU.md`](docs/HUONG_DAN_CAI_DAT_UBUNTU.md):

```bash
cd ~/SyS_Spec_GenAI-main/pm_test_spec_assistant   # sau khi unzip
./cai_dat.sh    # lần đầu
./chay.sh       # mỗi ngày
```

Login: **http://10.88.152.11:8765/login** · `admin` / `Alex@2025!`

`config.yaml` đã cấu hình sẵn cho LAN multi-user (`production`, `0.0.0.0:8765`).

---

## Run — Web UI (dev local)

```bash
python run_web.py
```

Open **http://127.0.0.1:8765** (hard-refresh if the UI looks stale after updates). The app shows a short Toyota welcome splash once on initial page load, using the transparent red logo at `web/static/img/toyota-logo-red.png`, then fades into the normal workflow.

### Web tabs (current)

| Tab | Purpose |
|-----|---------|
| **1. Review** | Upload / classify files, sign in to M365 and/or GitHub Copilot CLI, then run one analysis pass |
| **2. Logic & Definitions** | Per logic group: interactive logic tree (highlight ↔ source table), compare Tree vs Raw expression, trace terms with evidence chips, resolve definitions, **Copy brief for Copilot** (with readiness gate), select AI provider, and review affected workbook rows. Large jobs use compact dropdown selectors for logic groups, definition terms, and test cases instead of hundreds of chips |
| **3. Diagram Graph** | State list + transition edges from Excel transition tables, OCR mentions, and diagram rules; compact evidence on each edge. Select a state → inspect linked conditions and jump to logic |
| **4. Library** | Polarion-style trace canvas. Pick a local folder as the library root, then build a focus + spokes diagram: drop a file from Finder/Explorer onto a slot (auto-copied into the library folder) **or** click an empty slot to browse the folder and pick. Each row carries a free-form relationship label (e.g. `Satisfies`, `Validated By`, `Implemented By`); `+` adds another slot to a row, `+ Add relationship` adds a new row |
| **5. Final File** | Review/edit the final `System Test Spec` shape and export EN or JP workbook |
| **6. Test Code** | Map spec signal names to code symbols; generate Google Test `TEST_F` skeletons (spec as C++ comments + editable body); download `.cpp` snippets |
| **7. Guide** | In-app operator manual with **collapsible sections** (Vietnamese): workflow per tab, AI provider usage, Resolve with AI, Copilot brief, status meanings, and troubleshooting. Tab headers link directly to the matching Guide section |

### Quick start (web)

1. Open **Spec review**.
2. Click **Load sample package** (copies `pm_sample_inputs` into `web_data/uploads/`) or **Upload** your files.
3. Check the spec file(s) and set **Type** if the automatic label is wrong.
4. Click **Review specification**.
5. When progress completes, open **Logic & Definitions**.
6. Fix missing terms in **Logic & Definitions**. Use **AI provider** = `Auto`, `M365`, `GitHub Copilot CLI`, or `Ollama`, then click **Resolve with AI**. For complex controls, open **Copy brief for Copilot** — the readiness banner shows blockers before you paste into Copilot Web or M365.
7. If needed, open collapsed **Show source table / detected context** beside the Logic Tree to verify the original table or nearby state-machine context.
8. Open **Diagram Graph** when the spec includes state transitions — confirm state count matches edges and use **Jump to linked logic** from a transition.
9. Open **Library** (Tab 4) and paste an absolute path to your local spec folder. Drag a file from Finder/Explorer onto the focus card to set the centre item, then drop more files onto each spoke slot. Click the relationship label to rename it (free-form: `Satisfies`, `Validated By`, etc.); use the `+` at the end of a row to add another slot, or **+ Add relationship** to start a new row. Slots accept OS drops (file is copied into the library folder) or clicks (browse the local folder and pick) — no other info is stored.
10. Review/edit the workbook in **Final File**. Generated, cloned, and manual test cases can be soft-deleted from the focused test case editor before export.
11. Open **Test Code** to scaffold Google Test bodies: set harness config, map spec → code variables, regenerate from Given/When/Then, then download `.cpp` or a bundle for approved rows.
12. Use **Guide** when you need the in-app workflow, provider notes, or troubleshooting.

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
| `web_data/library.yaml` | Library tab state with **local folder paths** (gitignored); use `web_data/library.yaml.example` as template |
| Browser `localStorage` | Last `job_id` (reloads summary from disk on startup) |

**Handoff to company:** run `python scripts/sanitize_for_company_deploy.py` before zipping — removes tokens, uploads, analysis jobs, and home-directory paths. Full checklist: [`docs/COMPANY_DEPLOYMENT.md`](docs/COMPANY_DEPLOYMENT.md).

### AI providers + OCR guardrails

- The deterministic parser still owns AND/OR/NOT structure.
- **Resolve with AI** uses the selected provider:
  - `Auto`: try **Ollama first**, then M365 Copilot, then GitHub Copilot CLI when enabled/reachable.
  - `M365`: Microsoft Graph Copilot Chat API. **Requires a work/school account with the `Microsoft 365 Copilot` add-on SKU.** Personal Microsoft accounts (MSA) and work accounts without the Copilot add-on are auto-skipped — see [`docs/M365_COPILOT_ACTIVATION_GUIDE.md`](docs/M365_COPILOT_ACTIVATION_GUIDE.md) for the IT activation request.
  - `GitHub Copilot CLI`: local CLI fallback; `AUTH OK` means the machine has an existing Copilot CLI login.
  - `Ollama`: offline/experimental fallback, not the primary complex-logic path.
  - **Paste from Copilot Web**: button in the Knowledge workbench that accepts a JSON answer copied from [copilot.microsoft.com](https://copilot.microsoft.com) (free, works for MSA). The pasted patches still run through the logic-compliance validation loop.
- AI patches are validated before they become trusted workbook rows. Evidence gaps should become review-required/open questions, not silent export-ready changes.
- Reasoning sessions are stored per logic group so future Copilot/M365 turns can be audited by prompt hash and evidence hash. AI hypotheses now pass through a cited-claim guardrail (`schemas/reasoning_hypothesis.schema.json`): executable claims and testcase patch plans need citations, otherwise they are kept review-required/open-question instead of silently trusted.
- Testcase reconciliation is tracked for every knowledge apply. Provider patches are classified as `update_existing`, `add_new`, `retire`, or `needs_review`, with citation status, **per-TC logic compliance**, and a summary saved under `ai_assists.knowledge_apply[logic_id].reconciliation`.
- **Copy brief for Copilot** (`GET /api/review/m365-brief`) builds a frozen evidence brief per `logic_id` (issues, missing defs, source excerpt, tree text, path intent). `brief_readiness` returns blockers/warnings before copy; pasted/imported knowledge JSON is validated by `knowledge_patch_validation.py` and only saved when validation passes.
- M365 device-code login is persistent on this machine. Sign in again only after Sign out/Clear, deleted `web_data/m365`, token expiry, or revoked consent. At login ALEX decodes the `id_token.tid` claim and probes `/me/licenseDetails` to detect MSA / unlicensed accounts; the M365 badge then shows `MSA (NO API)` or `NO LICENSE` and the Resolve flow auto-falls back to Copilot CLI / Ollama. See [`docs/M365_COPILOT_ACTIVATION_GUIDE.md`](docs/M365_COPILOT_ACTIVATION_GUIDE.md).
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
2. **Extract** by type: signals, Word logic blocks, Excel gate-spine / transitions, condition definitions, two-column tables, footnotes/aliases, code refs, diagram metadata, merged-cell evidence
3. **Reconcile** logic blocks across sources (generic name match; no sample-specific aliases)
4. **Build condition trees** (table-native AST or text parser) and **normalize timing**
5. **Build diagram semantics** — state graph from transitions, OCR state labels, state rules
6. **Collect issues** and **unresolved** condition references (fail-closed)
7. **Generate test candidates** (logic, transitions, references)
8. **Apply candidate safety** — block when parse is `failed` / `partial` or strict blocking issues exist
9. **Build logic review items** — one card per control for the UI
10. **Build spec understanding report** — % understood, gaps, clarification prompts
11. **Export Excel**, review markdown, and `ui_bundle.yaml`

**Strict mode** (`config.yaml` → `ui.strict_mode: true`, default): blocking errors affect export messaging; unsafe candidates stay blocked.

**Ollama** (`llm.enabled` in config, default `false`): optional Japanese interpretation only; **not** used for logic structure in the web UI (`enable_ollama: false` on every review request).

---

## Logic parsing (core skill)

Specialized paths for **Word two-column control tables** (Logic | Condition) and **Excel gate-spine tables** (Control | Condition | Detail):

| Module | Role |
|--------|------|
| `src/engine/indentation_ast_parser.py` | Row path / column depth; OR+AND pairs; AND-root multi-column; fail-closed on ambiguous mixed paths |
| `src/engine/two_column_logic_parser.py` | Footnotes, aliases, `parse_table_to_logic_block` |
| `src/engine/gate_spine_ast.py` | **Table-native AST** from gate-spine token rows + Detail column (timing hints like `T_x elapsed`) |
| `src/engine/condition_tree_builder.py` | Text expression fallback: top-level OR/AND split, boolean predicates, timing atoms |
| `src/engine/logic_tree_renderer.py` | Flatten AST to indented tree lines for UI |

Per control output includes: `parse_status` (`ok` \| `partial` \| `failed`), expression string, AST, `parser_reason`, source references, optional `visual_source` table snapshot.

Gate-spine / boolean flag notes:

- Raw expression can be readable even when some tree leaves need review.
- Signal-only predicates such as `PWR_REQ_VALID`, `VEHICLE_SAFE`, or `NORMAL_ROUTE` are treated as boolean predicates (`== 1`) when safe.
- Nested groups like `(NORMAL_ROUTE OR (BACKUP_ROUTE AND T_SHUT_CONFIRM elapsed))` parse as structured OR/AND nodes, not a single `timing_condition` leaf.
- Remaining `opaque` leaves show raw text and keep review status honest.
- Logic Review keeps source evidence collapsed by default; open **Show source table / detected context** only when you need to compare against the original table or state-machine evidence.
- For Word/Excel control tables, ALEX carries a visual source snapshot (table-like preview from original cells) beside the Logic Tree. Evidence locators use compact chips (`GPT_GenLogic.xlsx › Sheet · r64`) instead of raw JSON.
- Excel **gate-spine** regions prefer `build_gate_spine_ast()`; expression-string parsing is fallback only.

Excel transition detection remains **heuristic** but **State Transition Interpretation** tables populate `from_state` / `to_state` when columns are present. `diagram_semantics` in `state_machine.yaml` aggregates states and edges for the Diagram Graph tab.

Unit tests: `tests/test_indentation_ast_parser.py`, `tests/test_condition_tree_builder.py`, `tests/test_gate_spine_ast.py`, `tests/test_excel_semantic_parser.py`.

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
| `state_machine.yaml` | States + transition rows + **`diagram_semantics`** (normalized state graph for UI) |
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
| GET | `/api/review/logic-review` | Logic review cards (tree nodes, visual source, trace) |
| GET | `/api/review/m365-brief` | Copilot brief + `readiness` gate for a logic group |
| GET | `/api/review/states` | States, transitions, `diagram_semantics` for Diagram Graph |
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
| `ui.strict_mode` | Default strict behavior for web / pipeline |
| `security` | `enabled`, `require_token`, `max_upload_mb`, **`rate_limit_per_minute`** (default 120). On localhost, heavy analyze polling can hit **429 Rate limit exceeded** — raise to `600`+ or set `enabled: false` for solo dev |
| `deployment.mode` | `local` (default) or `production` — affects DB init and queue behavior |
| `assist` | AI provider defaults: M365, Copilot CLI, Ollama, knowledge batch size |

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
├── config.yaml            # Classification, timing, strict mode, security, LLM off
├── requirements.txt
├── src/
│   ├── pipeline.py        # run_analyze()
│   ├── parsers/           # word, excel, pdf, two_column_table, code, ocr_local
│   ├── engine/            # AST, issues, candidates, understanding, traceability,
│   │                      #   gate_spine_ast, diagram_semantic_builder, golden_spec_scoreboard
│   ├── classifiers/       # file_classifier.py (4 UI types)
│   ├── exporters/         # excel_exporter.py, customer_testspec_exporter.py
│   ├── library/           # library_state.py (Tab 4 trace canvas)
│   ├── llm/               # ollama_client.py (optional)
│   └── models/            # signal, state, condition, timing, testcase
├── web/
│   ├── main.py            # FastAPI routes
│   ├── ai_provider.py     # Resolve with AI orchestration
│   ├── m365_brief.py      # Copilot brief export
│   ├── brief_readiness.py # Brief copy gate
│   ├── knowledge_patch_validation.py
│   ├── knowledge_reconciliation.py
│   ├── m365_auth.py, m365_copilot.py
│   ├── copilot_bridge.py  # GitHub Copilot CLI
│   ├── security.py        # Rate limit, upload cap, optional API token
│   ├── review_workbench.py
│   ├── bundle_helpers.py  # Backfill spec_understanding on load
│   └── static/            # index.html, app.js, css/
├── web_data/
│   ├── uploads/           # User / sample files
│   └── output/            # analysis_<timestamp>_<id>/
├── tests/                 # Parser, brief, golden scoreboard, M365 auth tests (250+)
└── docs/
    ├── ALEX_M365_REASONING_UPGRADE_PLAN.md
    ├── M365_COPILOT_ACTIVATION_GUIDE.md
    └── DESIGN_PLAN_COPILOT_LOOP.md
```

---

## Testing

```bash
cd pm_test_spec_assistant
source .venv/bin/activate
pytest -q
```

Notable suites:

| Test file | Covers |
|-----------|--------|
| `test_condition_tree_builder.py` | OR/AND nesting, boolean predicates, opaque detection |
| `test_gate_spine_ast.py` | Excel gate-spine table-native AST + Detail column |
| `test_diagram_semantic_builder.py` | State graph, edge dedup, arrow inference |
| `test_brief_readiness.py`, `test_m365_brief.py` | Copilot brief + readiness gate |
| `test_knowledge_patch_validation.py` | Knowledge JSON schema / compliance gate |
| `test_golden_spec_scoreboard.py` | `GPT_GenLogic.xlsx` structural baseline when sample present |

---

## Known limitations (v0.3)

- Excel transition detection is heuristic; empty `from_state`/`to_state` cells rely on arrow text inference or engineer review.
- Complex merged Word/Excel logic may stay `partial` / `failed` with explicit issues — Copilot brief + human review is the intended path.
- Diagram shape/layout semantics rely on OCR text and engineer confirmation; confirmed edges can be linked to logic overlays from the Diagram Graph tab.
- PDF quality depends on text layer.
- M365 Copilot requires work/school license and Azure app setup; GitHub Copilot CLI, **Paste from Copilot Web**, and Ollama remain fallbacks.
- Test Candidates is not a separate web tab (data remains in bundle and Excel).
- Understanding-only Excel sheet not exported separately (data in `ui_bundle.yaml` and UI).
- Parser coverage on arbitrary customer specs is partial (~50% structural patterns without co-reasoning); `GPT_GenLogic.xlsx` is used as a **structural** regression fixture, not a product requirement for signal names.
- Full end-to-end integration tests are limited; **250+** unit tests cover parsers, brief readiness, knowledge validation, diagram semantics, and golden scoreboard (`tests/test_golden_spec_scoreboard.py`).

### Troubleshooting (common)

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| **429 Rate limit exceeded** in server log | >120 `/api/*` calls/min from localhost during analyze polling | Raise `security.rate_limit_per_minute` in `config.yaml` or disable `security.enabled` for local dev; restart `run_web.py` |
| **Diagram: States 0, Edges N** | Stale browser cache or pre-fix bundle | Hard-refresh; re-run analyze; ensure `diagram_semantics.states[].state` is populated |
| **Tree shows `opaque` for readable flags** | Old job bundle or unsupported expression shape | Re-analyze; check `tests/test_condition_tree_builder.py` patterns |
| **M365 badge MSA (NO API)** | Personal Microsoft account or no Copilot SKU | Use Copilot Web paste, GitHub Copilot CLI, or Ollama — see M365 activation guide |

---

## Relation to other repo folders

This tree is **self-contained**. It does not modify `power-spec-kit/`, `power-mode-spec-pipeline/`, or other sibling projects. Sample inputs are read from `../pm_sample_inputs/` when using **Load sample package**.

---

## Further reading

| Document | Purpose |
|----------|---------|
| `docs/ALEX_M365_REASONING_UPGRADE_PLAN.md` | **Primary roadmap** — M365 co-reasoning for complex customer logic, auth tiers, phased delivery |
| `docs/M365_COPILOT_ACTIVATION_GUIDE.md` | IT-facing checklist to assign the `Microsoft 365 Copilot` add-on + grant tenant consent, with engineer verification commands and fallback options |
| `docs/COMPANY_DEPLOYMENT.md` | Sanitize personal data and package ALEX for a clean company-machine install |
| `docs/HUONG_DAN_CAI_DAT_UBUNTU.md` | **Cài Ubuntu công ty** — `./cai_dat.sh` + `./chay.sh` |
| `docs/M365_DEV_PROGRAM_SETUP.md` | Sandbox tenant alternative when company tenant blocks app registration |
| `docs/DESIGN_PLAN_COPILOT_LOOP.md` | Original Copilot-in-loop UX (clipboard / IDE era) |
| `docs/COPILOT_PROMPTS.md` | Standard prompt templates per issue type |
| `docs/TEST_SPEC_IO_FORMAT.md` | Expected input/output column format |
