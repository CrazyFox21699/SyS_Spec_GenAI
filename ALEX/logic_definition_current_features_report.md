# Logic & Definition Tab — Current Feature Report

**Date:** 2026-06-14  
**Author:** Discovery-only analysis — no code changes made.  
**Primary files inspected:**  
- `web/static/js/app.js` (frontend, ~14 000 lines)  
- `web/main.py` (backend FastAPI, ~7 000+ lines)  
- `web/review_workbench.py`  
- `web/project_memory.py`  
- `web/project_testcode_memory.py`  
- `src/engine/logic_review_builder.py`  
- `src/engine/understanding_loop.py`  
- `src/pipeline.py`  

---

## 1. Feature Summary

The **Logic & Definitions** tab (page ID `logic-review`, URL `/logic`) is Step 2 in the ALEX workflow. Its purpose is to bridge the gap between the raw parsed spec and trustworthy test-case input/output rows. Main responsibilities:

- Display one **logic group** (one parsed control) at a time via a dropdown selector.
- Show the **interactive logic tree** (AND/OR/edge/timer nodes) side-by-side with the raw **source table** rows from the uploaded spec.
- Surface all **missing signal definitions** that block test-case generation and let the engineer fix them.
- Let the engineer or M365 Copilot AI resolve definitions via: typed clarification notes, uploaded attachment files, or a full Copilot AI session (context → plan → write → review).
- Run a **path simulator** to manually check which logic branches activate for a given signal assignment.
- Show a **path × test-case coverage matrix** and propose missing paths.
- Show a **verification pattern matrix** (same-Given/different-Then detection) and let the engineer promote patterns into project memory.
- Show an **AI patch review panel** (Knowledge Reconciliation) where AI-generated updates to test cases can be accepted or rejected.
- Show a **hypothesis review panel** for Copilot reasoning sessions.
- Show an in-tab **workbook editor** for the final test-case rows belonging to the current logic group.
- Feed all saved state into **test code generation** via `project_memory.yaml` / `project_testcode_memory.md`.

---

## 2. UI Features

### 2.1 Spec Overview / Formal Spec Context Panel
| Field | Detail |
|---|---|
| **Element name** | `renderSpecOverviewPanel` / `renderFormalSpecContextPanel` |
| **What it does** | Displays spec profile (logic spec classifier score), section zones, state lifecycle (initial/start/finish), retention rules, Excel review-cell annotations, and signal registry. |
| **Input data** | `data.spec_profiles`, `data.state_machines`, `data.retention_rules`, `data.review_annotations`, `data.signals` from `/api/review/logic-review` |
| **Output** | Read-only panel; no user action |
| **Status** | Implemented — renders if data is present; hidden when empty |

---

### 2.2 Logic Group Selector
| Field | Detail |
|---|---|
| **Element name** | `<select id="logic-group-select">` |
| **What it does** | Dropdown of all logic groups in the job. Changing selection re-renders the full tab for the selected group. |
| **Input data** | `data.logic_review_items` list from `/api/review/logic-review` |
| **Output** | Re-triggers `renderLogicReview({ skipSummary: true })` with the new `state.selectedLogicId` |
| **Status** | Implemented |

---

### 2.3 Logic Group Hero Header
| Field | Detail |
|---|---|
| **Element name** | `.alex-hero` header |
| **What it does** | Shows control name, outcome label, parse status badge (ok / partial / failed), semantic badges (section zone, decision mode, timer qualifiers, edge events). |
| **Input data** | `item.control_name`, `item.outcome_label`, `item.parse_status`, `item.section_zone`, `item.decision_mode`, `item.timer_qualifiers`, `item.tree_nodes` |
| **Output** | Read-only display |
| **Status** | Implemented |

---

### 2.4 Interactive Logic Tree (left panel)
| Field | Detail |
|---|---|
| **Element name** | `renderInteractiveLogicTree()` inside `.logic-compare-grid` |
| **What it does** | Renders the parsed AND/OR/leaf tree as clickable nodes. Clicking a node highlights the matching source table row and vice versa. Active nodes are highlighted when the path simulator runs. Supports edge events (Σ sentinel, T timer chips). |
| **Input data** | `item.tree_nodes`, `item.tree_lines`, `simResult.active_node_ids`, `state.logicTreeFocus` |
| **Output** | Highlights source table rows; updates `state.logicTreeFocus`; re-renders active nodes after simulation |
| **Status** | Implemented |

---

### 2.5 Source Table (right panel, linked)
| Field | Detail |
|---|---|
| **Element name** | `renderVisualSourcePreview()` inside `.logic-compare-grid` |
| **What it does** | Displays the raw Excel/Word table rows (row_no, raw_condition, depth, detected_type). Clicking a row highlights the matching tree node. |
| **Input data** | `item.visual_source`, `item.table_rows`, `state.logicTreeFocus.highlightTerms`, `state.logicTreeFocus.highlightRowNos` |
| **Output** | Bi-directional highlight with tree |
| **Status** | Implemented |

---

### 2.6 Parser Notes Collapsible
| Field | Detail |
|---|---|
| **Element name** | `<details>` "Parser notes" |
| **What it does** | Shows list of parser warnings/notes generated during spec analysis. |
| **Input data** | `item.parser_notes` |
| **Output** | Read-only |
| **Status** | Implemented |

---

### 2.7 Path Simulator Panel
| Field | Detail |
|---|---|
| **Element name** | `renderPathSimulatorPanel()` + `#btn-logic-sim-run` |
| **What it does** | Lists each signal from the logic tree as an editable input. "Run what-if" sends assignments to backend, receives which nodes are active (ACTIVE / INACTIVE / Partial), and highlights them in the tree. |
| **Input data** | `item.trace_rows` signals; user-typed values in `.logic-sim-input` fields |
| **Output** | POST `/api/review/logic-simulate`; updates `state.pathSimResult[logic_id]`; re-renders tree with `active_node_ids` |
| **Status** | Implemented |

---

### 2.8 Footnote Attachments Panel
| Field | Detail |
|---|---|
| **Element name** | `renderFootnoteAttachmentsPanel()` + `#reference-file-upload` |
| **What it does** | Shows cross-file logic materialized from footnote references. Allows upload of a reference file (Excel/Word/PDF) to merge definitions for the current logic group. |
| **Input data** | GET `/api/review/footnote-materializations`; upload POST `/api/review/attach-reference-file` |
| **Output** | Merged `condition_definitions` added to bundle; `_rebuild_understanding` called; tab re-renders |
| **Status** | Implemented — panel hidden when no footnote attachments exist |

---

### 2.9 Path × TC Matrix Panel
| Field | Detail |
|---|---|
| **Element name** | `renderPathTcMatrixPanel()` + `#btn-path-tc-propose` |
| **What it does** | Shows a table of logic paths (full/partial/missing coverage), how many TCs cover each path, and which signals each path covers. "Propose missing TCs" generates new test-case candidates for uncovered paths. |
| **Input data** | GET `/api/review/path-tc-matrix`; POST `/api/review/path-tc-propose` |
| **Output** | Proposal stored in `state.pathRegenProposal[logic_id]`; panel re-renders |
| **Status** | Implemented — panel hidden when `matrix.ok` is false or no paths |

---

### 2.10 Verification Pattern Matrix
| Field | Detail |
|---|---|
| **Element name** | `renderVerificationMatrixPanel()` + "Promote" buttons |
| **What it does** | Detects test cases sharing the same Given fingerprint but different Then signals (1→N), or test cases with partial Then assertions (missing signals). "Promote" saves a pattern to project memory for Copilot to reuse. |
| **Input data** | GET `/api/review/verification-matrix`; POST `/api/review/promote-verification-pattern` |
| **Output** | Saved pattern in `bundle.ai_assists.project_memory.verification_patterns`; `project_memory.yaml` updated |
| **Status** | Implemented |

---

### 2.11 Evidence & Dependency Trace Collapsible
| Field | Detail |
|---|---|
| **Element name** | `.alex-evidence-panel` |
| **What it does** | Shows raw Excel source rows (row_no, condition, depth, type) and dependency trace rows. |
| **Input data** | `item.table_rows`, `item.trace_rows`, `item.issues` |
| **Output** | Read-only |
| **Status** | Implemented |

---

### 2.12 Definitions Section — Term List Sidebar
| Field | Detail |
|---|---|
| **Element name** | `.definition-term-list` / `.definition-term-chips` |
| **What it does** | Chip buttons, one per signal/term that was referenced in the logic tree. Resolved (green), added-from-note (yellow), missing (red) are counted in the summary. Clicking a chip focuses that term in the main panel. |
| **Input data** | GET `/api/review/definition-inbox` → `inbox.terms` |
| **Output** | Sets `state.inboxFocus[logic_id]`; re-renders definition panel for selected term |
| **Status** | Implemented |

---

### 2.13 Term Detail Panel
| Field | Detail |
|---|---|
| **Element name** | `.definition-term-detail` |
| **What it does** | For the focused term: shows term name, reason code (not_found / conflicting_definitions / normalized_match / engineer_note_only / added_file_only / spec_definition_found), reason detail, and a list of known definitions with source attribution (file/sheet/table/row). |
| **Input data** | `inbox.terms[n].definitions`, `inbox.terms[n].reason_code`, `inbox.terms[n].reason_detail` |
| **Output** | Read-only |
| **Status** | Implemented |

---

### 2.14 Copilot Workbench Panel (4-step session)
| Field | Detail |
|---|---|
| **Element name** | `renderCopilotWorkbench()` inside `.definition-panel` |
| **What it does** | A 4-step flow: **1 Context → 2 Plan → 3 Write → 4 Review**. Stepper shows current step. Engineer note textarea for clarification. |
| **Status** | Implemented |

**Sub-actions in Copilot workbench:**

| Button | What it does | API |
|---|---|---|
| **Hiểu spec (Copilot)** | Starts `copilot_context_plan` M365 task (runs context build + plan generation in background) | POST `/api/review/copilot/m365-tasks` kind=`copilot_context_plan` |
| **Viết testcase** | Starts `copilot_write` M365 task (writes draft test cases using plan) | POST `/api/review/copilot/m365-tasks` kind=`copilot_write` |
| **Apply đã chọn** | Applies selected draft diffs to test candidates | POST `/api/review/copilot/confirm` |
| **Ảnh spec** (file upload) | Uploads image/PDF/DOCX attachment for the logic group | POST `/api/review/logic-attachments` |
| **Send follow-up** | Sends a follow-up message in the same Graph Copilot conversation | POST `/api/review/copilot/follow-up` |
| **Copy M365 brief** | Builds M365 brief text and copies to clipboard | Client-only via `buildCopilotM365Brief()` |
| **Build Context (context step)** | Explicit context pack build step | GET `/api/review/copilot/context` |
| **Generate plan** | Runs `copilot_plan` M365 task | POST `/api/review/copilot/m365-tasks` kind=`copilot_plan` |
| **Save plan** | Saves manually edited plan items | PATCH `/api/review/copilot/plan` |

---

### 2.15 Engineer Note Textarea + Local Apply
| Field | Detail |
|---|---|
| **Element name** | `#definition-workbench-note` + `#btn-definition-local-apply` |
| **What it does** | Engineer types constraints like `SIG = 1` or `HUY >= 1, < 5`. "Apply locally" parses the note into `engineer_definitions` without calling AI. Autosaved to `localStorage` via `writeDefinitionDraft(logicId, text)`. |
| **Input data** | Free-text engineer note |
| **Output** | POST `/api/review/logic-clarification` with `local_only: true`; updates `bundle.ai_assists.engineer_definitions`; updates linked test candidates |
| **Status** | Implemented |

---

### 2.16 Copilot Query History Panel
| Field | Detail |
|---|---|
| **Element name** | `.definition-history-panel` (collapsible) |
| **What it does** | Lists the last 8 Copilot definition-query answers (term, question, answer, suggested matches, follow-up questions). |
| **Input data** | `inbox.query_history` from `/api/review/definition-inbox` |
| **Output** | Read-only |
| **Status** | Implemented |

---

### 2.17 Knowledge Reconciliation Panel
| Field | Detail |
|---|---|
| **Element name** | `renderKnowledgeReconciliationPanel()` |
| **What it does** | Shows AI-proposed patches for test candidates (before/after expected_input diffs). User selects patches to apply or rejects all. Shows logic_comply status (pass/fail/warn) per patch. |
| **Input data** | GET `/api/review/knowledge-apply` |
| **Output** | POST `/api/review/knowledge-apply/confirm` or POST `/api/review/knowledge-apply/reject` |
| **Status** | Implemented — panel hidden when no pending patches |

---

### 2.18 Hypothesis Review Panel
| Field | Detail |
|---|---|
| **Element name** | `renderHypothesisReviewPanel()` |
| **What it does** | Shows latest Copilot reasoning session: claims (term + definition), open questions, testcase patch plan. Engineer can accept selected claims or paste a hypothesis JSON. |
| **Input data** | GET `/api/reasoning/{logic_id}` → `session.hypotheses[-1]` |
| **Output** | POST `/api/reasoning/accept-claims`; triggers `_rebuild_understanding` |
| **Status** | Implemented — panel hidden when no session hypotheses |

---

### 2.19 Final Workbook Rows (Logic scope)
| Field | Detail |
|---|---|
| **Element name** | `.workbook-workspace--logic` section |
| **What it does** | Shows `renderWorkbookTestcaseBar` (summary counts) and `renderWorkbookFocusEditor` (inline editable grid for the test candidates belonging to this logic group). Editable columns: test_function, event, use_case, operation, expected_input, expected_output, review_status, engineer_confirmation_required. |
| **Input data** | GET `/api/review/workbench` filtered to `logic_id == item.logic_id` |
| **Output** | POST `/api/review/workbench-row` on cell change; invalidates GTest workspace cache if I/O changes |
| **Status** | Implemented |

---

## 3. Backend APIs

All APIs are in `web/main.py` unless noted.

| Method | Path | Purpose | Reads from | Writes to |
|---|---|---|---|---|
| GET | `/api/review/logic-review` | Main data loader for the tab | `bundle.logic_review_items`, `bundle.ai_assists`, `build_ai_queue(bundle)` | — |
| GET | `/api/review/definition-inbox` | Term resolution status per logic group | `bundle.logic_review_items`, `bundle.ai_assists` (engineer_defs, supplemental, query_history) | — |
| POST | `/api/review/logic-simulate` | Path simulator | `bundle.logic_review_items[n].tree_model` | — |
| POST | `/api/review/rebuild-understanding` | Manual re-run of understanding gate | `bundle` | `bundle`, `ui_bundle.yaml` |
| GET | `/api/review/footnote-materializations` | Footnote cross-file attachments | `bundle.footnote_materializations`, `bundle.logic_blocks` | — |
| POST | `/api/review/attach-reference-file` | Upload reference file to merge definitions | uploaded file | `bundle.ai_assists.supplemental_definitions[logic_id]`, `ui_bundle.yaml` |
| GET | `/api/review/path-tc-matrix` | Logic-path × test-case coverage | `bundle` via `build_path_tc_matrix()` | — |
| POST | `/api/review/path-tc-propose` | Generate test proposals for uncovered paths | `bundle` via `build_path_regen_proposals()` | `bundle`, `ui_bundle.yaml` |
| GET | `/api/review/overview` | Spec overview + issues | `bundle` via `build_overview_dashboard()` | — |
| GET | `/api/review/workbench` | Workbook rows (test candidates) | `bundle` via `build_customer_testspec_preview()` | — |
| POST | `/api/review/workbench-row` | Save edits to a workbook row | request body | `bundle.test_candidates`, `ui_bundle.yaml` |
| GET | `/api/review/knowledge-apply` | Pending AI patches for review | `bundle.ai_assists.knowledge_apply` | — |
| POST | `/api/review/knowledge-apply/confirm` | Apply selected knowledge patches | `bundle` | `bundle`, `ui_bundle.yaml` |
| POST | `/api/review/knowledge-apply/reject` | Reject all pending patches | `bundle.ai_assists.knowledge_apply` | `bundle`, `ui_bundle.yaml` |
| GET | `/api/reasoning/{logic_id}` | Load reasoning session | `web_data/output/{job_id}/reasoning/{logic_id}/session.json` | — |
| POST | `/api/reasoning/accept-claims` | Accept hypothesis claims | reasoning session file | `bundle`, `ui_bundle.yaml` |
| POST | `/api/review/logic-clarification` | Save engineer note + local-apply or AI-apply | request body, `bundle` | `bundle.ai_assists.engineer_definitions`, `ui_bundle.yaml` |
| POST | `/api/review/definition-query` | M365 Copilot definition lookup (deprecated/legacy) | `bundle`, M365 Copilot API | `bundle.ai_assists.definition_queries`, `ui_bundle.yaml` |
| GET | `/api/review/copilot/context` | Build context pack for Copilot | `bundle`, engineer note | `bundle.ai_assists`, `ui_bundle.yaml` |
| POST `/PATCH` | `/api/review/copilot/plan` | Run / save Copilot plan | `bundle`, M365 Copilot | `bundle.ai_assists.copilot_sessions[logic_id].plan` |
| POST | `/api/review/copilot/write` | Write test-case drafts via Copilot | plan, `bundle` | Copilot draft diffs in session |
| POST | `/api/review/copilot/confirm` | Apply selected draft diffs to candidates | `bundle.ai_assists.copilot_sessions[logic_id].draft_diffs` | `bundle.test_candidates`, `ui_bundle.yaml` |
| GET | `/api/review/copilot/session` | Load current Copilot session state | `bundle.ai_assists.copilot_sessions[logic_id]` | — |
| POST | `/api/review/copilot/follow-up` | Send follow-up in same M365 Graph conversation | session `conversation_id`, M365 API | session, `bundle` |
| GET | `/api/review/m365-brief` | Build M365 Copilot brief document | `bundle`, reasoning session | `web_data/output/{job_id}/m365_brief/{logic_id}/brief.md` |
| POST | `/api/review/copilot/m365-tasks` | Start async M365 background task | request payload | `web_data/output/{job_id}/m365_tasks.json` |
| GET | `/api/review/copilot/m365-tasks/{task_id}` | Poll task status | m365_tasks.json | — |
| GET | `/api/review/verification-matrix` | Build Given/Then fingerprint matrix | `bundle` via `build_verification_matrix()` | — |
| POST | `/api/review/promote-verification-pattern` | Save pattern to project memory | `bundle.ai_assists.project_memory.verification_patterns` | `bundle`, `ui_bundle.yaml` |
| GET | `/api/review/project-memory` | Load merged project memory | `config/project_memory.yaml`, `bundle.ai_assists.project_memory`, `gtest_state.code_variable_map` | — |
| PUT | `/api/review/project-memory` | Save project memory updates | request body | `bundle.ai_assists.project_memory`, `ui_bundle.yaml`, `gtest_state` |
| POST | `/api/review/logic-attachments` | Upload image/doc attachment for logic group | uploaded files | `web_data/output/{job_id}/logic_attachments/{logic_id}/`, `bundle` |
| GET | `/api/review/logic-attachments` | List attachments for logic group | directory listing | — |
| GET | `/api/review/audit-log` | Export engineer/AI action log | `bundle.ai_assists.knowledge_apply`, reasoning sessions | — |
| GET | `/api/export/logic-traceability-xlsx` | Export logic traceability as XLSX | `bundle` | downloaded file (XLSX) |
| GET | `/api/jobs/{job_id}/diagnostic` | Run parser diagnostic | `bundle` | — |
| GET | `/api/review/structured-overlay` | Get accepted signal constraints | `bundle.ai_assists.structured_overlay[logic_id]` | — |
| PUT | `/api/review/structured-overlay` | Save constraints | request body | `bundle`, `ui_bundle.yaml` |
| POST | `/api/review/compile-constraints` | Compile accepted constraints into definitions | `bundle`, `_cfg()` | `bundle`, `ui_bundle.yaml` |

---

## 4. Data Flow

```
Upload spec (docx / xlsx / pdf)
    ↓
src/pipeline.py  (full parse run)
    ├── Word/Excel/PDF parsers → condition_definitions, footnote_definitions,
    │   logic_blocks, signals, two_column_tables, code_definitions
    ├── src/engine/table_logic_parser.py → logic AST (tree)
    ├── src/engine/logic_review_builder.py::build_logic_review_items()
    │   → logic_review_items[] (one per control)
    │   → trace_rows[] (one per signal referenced in tree)
    │   → parse_status (ok / partial / failed)
    │   → unresolved_refs[] (signals missing from condition_definitions)
    └── bundle saved → web_data/output/{job_id}/ui_bundle.yaml

         ↓  (on tab load)

GET /api/review/logic-review
    → logic_review_items[], ai_queue[], term_roles, ai_assists, signals
    → renders: tree, source table, semantic badges, parser notes, source evidence

GET /api/review/definition-inbox
    → terms[] (each with resolution, reason_code, definitions list, query history)
    → renders: term chips, term detail panel

         ↓  (engineer reviews + fixes)

Engineer types note, e.g. "SIG_PWR = 1"
    POST /api/review/logic-clarification (local_only=true)
    → _extract_engineer_definitions() parses note → engineer_definitions dict
    → apply_engineer_definitions_to_candidates() updates test candidates
    → _rebuild_understanding() → refreshes logic_review_items, gate counts
    → bundle saved

Engineer uploads attachment (xlsx / docx / pdf / image / txt)
    POST /api/review/logic-attachments
    → _extract_supplemental_definitions() → supplemental_definitions for logic_id
    → _rebuild_understanding()

         ↓  (AI resolution)

GET /api/review/copilot/context
    → build_context() → context_pack (signals, candidates, footnotes, patterns)
    → saved to bundle.ai_assists.copilot_sessions[logic_id]

POST /api/review/copilot/plan (via M365 task)
    → M365 Copilot API → testcase plan
    → saved to copilot_sessions[logic_id].plan

POST /api/review/copilot/write (via M365 task)
    → plan → write draft diffs per test candidate
    → saved to copilot_sessions[logic_id].draft_diffs

POST /api/review/copilot/confirm (Apply selected)
    → draft diffs → test_candidates updated (expected_input / expected_output)
    → _rebuild_understanding()

         ↓  (human approval / knowledge reconciliation)

AI patch review panel:
POST /api/review/knowledge-apply/confirm
    → patches applied to test_candidates
    → _rebuild_understanding()

Verification pattern promoted:
POST /api/review/promote-verification-pattern
    → bundle.ai_assists.project_memory.verification_patterns
    → available in next Copilot code-gen context

         ↓  (used downstream)

Test Code tab:
    project_testcode_memory.md (code style, signal rules, I/O maps)
    ← read from web_data/.alex/project_testcode_memory.md
    ← or per-job: output/{job_id}/bundle/code_config/project_testcode_memory.md

    Expected input / expected output from approved test candidates
    → GTest TEST_F block comment (Given: / When: / Then:)
    → sanitize_generated_cpp_body() with mapped_output_signals from memory
```

---

## 5. Current Data Model

Fields that exist in `logic_review_items[]` (one per control / logic group):

| Field | Type | Description |
|---|---|---|
| `logic_id` | str | Unique ID (usually same as `control_name`) |
| `control_name` | str | Signal/control name from spec table header |
| `outcome_label` | str | Short English outcome description |
| `parse_status` | str | `"ok"` / `"partial"` / `"failed"` |
| `section_zone` | str | Spec section type: `control_conditions`, `definitions`, `state_charts`, etc. |
| `decision_mode` | str | `"sequential"` (priority) or `"boolean"` |
| `timer_qualifiers` | list | Timer symbols and qualifier type |
| `tree_nodes` | list | AST nodes with `node_id`, `node_type`, `parent_node_id`, `atom_kind`, `value_domain` |
| `tree_lines` | list | Fallback text-tree lines |
| `tree_model` | dict | Full tree dict used for simulation |
| `table_rows` | list | `row_no`, `raw_condition`, `depth`, `detected_type`, `parser_reason` |
| `visual_source` | list | Source rows for visual preview |
| `parser_notes` | list | Parser warning messages |
| `trace_rows` | list | Per-term: `term`, `status` (missing/resolved), `preview` |
| `unresolved_refs` | list | Signal names with no trusted definition |
| `source_evidence` | dict/str | Source file attribution |
| `candidates` | list | Linked test-candidate IDs |
| `issues` | list | Linked issues from issue_collector |
| `attached_logic` | list | Footnote-attached cross-file logic |

Fields in `inbox` per logic group (from `build_definition_inbox`):

| Field | Description |
|---|---|
| `terms[n].term` | Signal name |
| `terms[n].resolution` | `definition_found` / `added_context_found` / `missing_definition` |
| `terms[n].reason_code` | `not_found` / `conflicting_definitions` / `normalized_match` / `engineer_note_only` / `added_file_only` / `spec_definition_found` |
| `terms[n].definitions` | List of found definitions with `kind`, `match_mode`, `source`, `definition` text |
| `terms[n].ai_hint` | Optional AI resolution hint |
| `terms[n].footnotes`, `aliases`, `logic_groups`, `candidate_ids` | Cross-references |
| `attachments` | Uploaded logic attachment metadata |
| `query_history` | Last 8 Copilot answers |
| `unused_added_definitions` | Supplemental defs not matched to any term |

Fields in `test_candidates` (workbook rows) relevant to this tab:

| Field | Editable | Description |
|---|---|---|
| `candidate_id` | No | Unique TC ID |
| `logic_id` | No | Parent logic group |
| `test_function` | Yes | Function/feature name |
| `test_group` | No | Group label (from logic group) |
| `event` | Yes | Trigger event description |
| `use_case` | Yes | Use-case free text |
| `operation` | Yes | Operation description |
| `expected_input` | Yes | Given / input signal assignments |
| `expected_output` | Yes | Then / output assertions |
| `review_status` | Yes | `pending` / `ready` / `approved` / `blocked` |
| `engineer_confirmation_required` | Yes | `yes` / `no` |
| `open_questions` | Yes (non-EN) | Open question field |

Fields in `project_memory` (IO/signal mapping, affects code gen):

| Field | Description |
|---|---|
| `io_variable_map` | dict: signal name → C++ accessor or type annotation |
| `signal_roles` | dict: signal name → `"input"` / `"output"` / `"both"` |
| `shared_preconditions` | list: reusable Given blocks |
| `verification_patterns` | list: promoted Given→Then fingerprint patterns |
| `copilot_hints` | `prefer_reuse_patterns`, `max_patterns_in_prompt` |

---

## 6. Existing Diagnostics / Validation

### 6.1 Parse Status Badge
- **Values:** `ok` (green) / `partial` (yellow) / `failed` (red)
- **Source:** `item.parse_status` in `logic_review_items`
- **Meaning:** Whether the spec table parser fully, partially, or failed to interpret the logic tree

### 6.2 Unresolved Refs Warning
- **Trigger:** `item.unresolved_refs.length > 0`
- **Display:** Inline `<p><b>Missing definitions:</b> SIG_A, SIG_B</p>` below the hero header
- **Status:** Implemented

### 6.3 AI Queue Status
- **Values (per logic group):**
  - `ready_for_ai` — definitions are sufficient
  - `blocked_missing_definition` — one or more signals unresolved
  - `needs_engineer_answer` — parse partial/failed, or row needs engineer confirmation
  - `ai_drafted` — Copilot wrote drafts; engineer review pending
  - `completed` — all rows ready/approved
  - `no_rows` — no test candidates linked yet
- **Source:** `build_ai_queue()` in `web/review_workbench.py`
- **Display:** In the top-level job summary bar (not directly in this tab, but drives tab state)

### 6.4 Term Resolution Status
- **Per-term in definition inbox:**
  - `definition_found` — exact or normalized spec definition present
  - `added_context_found` — engineer note / supplemental file provided definition
  - `missing_definition` — no definition found anywhere
- **Reason codes:** `not_found`, `conflicting_definitions` (multiple different defs), `normalized_match` (case/punctuation mismatch), `engineer_note_only`, `added_file_only`, `spec_definition_found`

### 6.5 Parser Notes
- Each `logic_review_items[n].parser_notes` lists warnings: unrecognized cell types, depth mismatches, ambiguous rows.
- Displayed in collapsible "Parser notes" section.

### 6.6 Path Coverage Gaps
- `matrix.paths[n].coverage_status` = `full` / `partial` / `missing`
- Aggregated as `paths_full`, `paths_partial`, `paths_missing` in the matrix summary
- "Propose missing TCs" generates candidates for uncovered paths

### 6.7 Verification Pattern Detection
- **1→N (same Given, different Then):** Shows variants per Given fingerprint
- **Partial assertions:** Test cases that have the same Given but are missing some Then signals
- `logic_comply` per patch: `pass` / `fail` / `warn`

### 6.8 Understanding Gate Counts
- After any save/apply, `_rebuild_understanding()` returns:
  - `understanding_percent` — how much of the spec is understood (0–100%)
  - `gate_counts.ready` — signals fully resolved
  - `gate_counts.needs_llm` — signals that need AI to resolve
  - `gate_counts.needs_engineer` — signals that need engineer input
  - `unresolved_cleared` — how many were cleared by this action
  - `footnote_materialized` — how many footnote logic blocks were attached

### 6.9 Brief Readiness Validation
- `validate_brief_readiness()` in `web/brief_readiness.py` checks if the M365 brief has enough context (parse_status, missing_definitions, etc.) before sending to Copilot.

### 6.10 Job Diagnostic
- GET `/api/jobs/{job_id}/diagnostic` — shows low-level parser diagnostics when no logic groups are detected.

---

## 7. Export / Save Behavior

| What | Where saved | Format |
|---|---|---|
| Engineer notes | `bundle.ai_assists.engineer_notes[logic_id]` → `ui_bundle.yaml` | YAML string |
| Engineer definitions | `bundle.ai_assists.engineer_definitions` → `ui_bundle.yaml` | YAML dict |
| Supplemental definitions (from file) | `bundle.ai_assists.supplemental_definitions[logic_id]` → `ui_bundle.yaml` | YAML list |
| Logic attachments (files) | `web_data/output/{job_id}/logic_attachments/{logic_id}/` | Original format |
| Reference files (uploaded) | `web_data/output/{job_id}/logic_attachments/{logic_id}/reference_files/` | Original format |
| M365 brief | `web_data/output/{job_id}/m365_brief/{logic_id}/brief.md` | Markdown |
| Reasoning session | `web_data/output/{job_id}/reasoning/{logic_id}/session.json` | JSON |
| Copilot sessions | `bundle.ai_assists.copilot_sessions[logic_id]` → `ui_bundle.yaml` | YAML |
| Knowledge patches (pending/applied) | `bundle.ai_assists.knowledge_apply[logic_id]` → `ui_bundle.yaml` | YAML |
| Project memory | `bundle.ai_assists.project_memory` + `config/project_memory.yaml` | YAML |
| Verification patterns | `bundle.ai_assists.project_memory.verification_patterns` → `project_memory.yaml` | YAML |
| Definition draft (auto-save) | `localStorage` key `alex.draft.<version>.<jobId>.definition.<logicId>` | JSON |
| Logic traceability export | Downloaded on demand | XLSX |

**Reuse by test code generation:**
- `expected_input` / `expected_output` from approved test candidates → Given/When/Then in GTest comments
- `project_testcode_memory.md` (loaded from `web_data/.alex/` or per-job `bundle/code_config/`) → injected into Copilot code-gen prompts
- `project_memory.io_variable_map` → signal → C++ type mapping
- `project_memory.verification_patterns` → reused patterns in code context
- `project_memory.shared_preconditions` → shared Given setup blocks

---

## 8. Integration With Test Code Generation

| Logic & Definition artifact | Effect on test code |
|---|---|
| `expected_input` (approved) | → `Given:` line in TEST_F block comment; passed to Copilot as `expected_input` field |
| `expected_output` (approved) | → `Then:` line; drives EXPECT_THAT assertions; mapped by `get_mapped_output_signals()` from `project_testcode_memory.md` |
| `engineer_definitions[SIG] = "= 1"` | → applied to test candidates; the `= 1` value used to fill `expected_input` when SIG appears in logic conditions |
| `project_memory.io_variable_map` | → used in `sanitize_generated_cpp_body()` to map raw signal names to C++ types; missing entries → `ALEX_REVIEW` comment |
| `project_memory.verification_patterns` | → included in Copilot code context pack; used to detect 1→N patterns and suggest EXPECT_THAT variants |
| `project_testcode_memory.md` (Output Assertion Pattern section) | → entries with `condition: SIG = 1 → EXPECT_THAT(SIG, Eq(1u))` are read by `get_mapped_output_signals()` to exempt signals from ALEX_REVIEW replacement |
| `test_group` + `event` from test candidate | → appear in generated TEST_F block comment (no labels, bare values as of Task 25) |
| `parse_status` of logic group | → affects `queue_status`; groups with `partial`/`failed` parse are flagged `needs_engineer_answer` and may produce weaker GTest code |
| Missing definitions (`unresolved_refs`) | → test candidates get `engineer_confirmation_required = yes`; GTest body may contain `ALEX_REVIEW` comment for unknown signals |
| M365 Copilot write session | → produces `draft_diffs` (expected_input / expected_output updates); after confirm → replaces test candidate fields → used as-is by code gen |

---

## 9. Limitations / Broken Areas

1. **No inline definition editing.** The engineer cannot edit a `condition_definition` row in place from this tab. The only write path is through engineer notes (text parsing) or file upload. Definitions from the parsed spec are read-only in the UI.

2. **Term chip count grows unbounded.** Every ALL_CAPS term referenced in the logic tree gets a chip. There is no grouping, sorting by priority, or filtering by status. For large specs with 50+ signals this becomes unwieldy.

3. **`definition-query` API (`/api/review/definition-query`) is partially superseded.** The legacy single-term Copilot query endpoint exists but is not wired to any visible button in the current UI (the button was replaced by the full Copilot workbench session). The endpoint still saves to `definition_queries` history.

4. **Path simulator signals default to `trace_rows` terms.** When `simResult` is not yet loaded, the simulator falls back to `item.trace_rows[n].term` with `default: "0"`. For boolean or multi-valued signals, `0` may be wrong; no type hints are shown.

5. **Footnote materialization is best-effort.** `link_footnotes_to_logic_blocks()` and `materialize_footnote_attachments()` work on text footnotes only. Purely visual footnote diagrams without OCR text are not linked.

6. **`build_path_tc_matrix` hides when `matrix.ok` is false** — not surfaced as an error. If the matrix fails to build (e.g., no candidates), the panel simply disappears with no message.

7. **Copilot session stepper is read-only.** The user cannot click a stepper step directly to jump; the step only advances when the corresponding API completes. Re-running context doesn't reset plan/write state.

8. **Draft diffs from Copilot write are all-or-nothing per checkbox.** The diff card shows `expected_input` before/after but not `expected_output` before/after in the same view. The `missing_signals` warning exists but partial signal diffs are not visually separated.

9. **Knowledge reconciliation (`knowledge_apply`) is tied to a single `logic_id`** at the panel level, but `confirm_pending_knowledge()` applies patches globally across all candidates for the logic group. There is no per-candidate granularity.

10. **No undo.** Once patches are applied (knowledge-apply/confirm or copilot/confirm), there is no rollback. The `bundle_version` check (optimistic locking) prevents conflicts but does not provide undo history.

11. **`_extract_engineer_definitions()` is heuristic-based.** It parses free text like `SIG = 1`. Complex multi-condition expressions (`SIG >= 1 AND SIG < 5`) may be partially parsed or silently dropped.

12. **Attachment kind detection is extension-based.** `.txt` files get text-definition parsing, images get OCR metadata. Files with wrong extensions or unusual encodings may silently return 0 definitions.

13. **Understanding percent (`understanding_percent`) is estimated.** The gate builds on `build_resolved_logic_blocks()` which uses heuristics. A 100% understanding score does not guarantee all signals are correctly defined.

14. **`renderCapabilitySummary` is a stub.** The function at app.js:2093 returns `""`. The capability summary data is built server-side but not rendered in the UI.

15. **M365 Copilot integration requires active M365 license.** All Copilot features degrade gracefully (buttons disabled, banners shown) when the M365 session is not active, but the degraded path still shows buttons that look active.

---

## 10. Recommended Next Improvements

### P0 — Must fix

- **P0.1 — Inline definition editing:** Add a simple table on the term detail panel showing `condition_definitions` rows for the focused term, with a pencil icon to edit/override the definition text. Currently the only edit path is free-text parsing which is error-prone.

- **P0.2 — Surfacing path matrix failures:** When `/api/review/path-tc-matrix` returns `matrix.ok = false`, show a small error message instead of silently hiding the panel. Engineers assume coverage is complete when the panel is absent.

- **P0.3 — Simulator signal type hints:** Show the signal's known type / domain next to the input field (boolean, enum, integer range) if available in `condition_definitions`. Prevents default-`0` being wrong for boolean true/false signals.

### P1 — Useful

- **P1.1 — Term list filtering:** Add "show only missing" toggle to the term chip list. For large specs with 50+ signals, engineers can't see at a glance which ones still need work.

- **P1.2 — Path simulator persist last values:** Already partially done (`state.pathSimAssignments`), but the values are lost on page reload. Save them to `localStorage` like the engineer note draft.

- **P1.3 — Diff view for expected_output in copilot confirm panel:** The current diff card only shows `expected_input` before/after. Show `expected_output` before/after in the same article. Engineers need both to make an informed apply decision.

- **P1.4 — Copilot session step navigation:** Allow clicking a completed step chip to view the saved context/plan from that step without re-running it.

- **P1.5 — Remove or hide `definition-query` (legacy endpoint):** Clean up the dead code path. The history panel still shows past queries, which is valuable to keep, but the submit action should route to the new Copilot workbench.

### P2 — Later

- **P2.1 — Bundle diff / undo history:** Save a rolling window of the last N `ui_bundle.yaml` snapshots in `{job_id}/snapshots/` so engineers can roll back a bad AI apply.

- **P2.2 — Term grouping by subsystem:** When a spec has grouped signal prefixes (e.g., `PWR_`, `CND_`), auto-group term chips by prefix with collapse/expand.

- **P2.3 — Export definitions view:** Add a read-only export button on this tab that downloads all resolved definitions (from spec + engineer notes + supplemental) as a clean Markdown or CSV file for offline review.

- **P2.4 — `renderCapabilitySummary` implementation:** The capability summary data is already computed server-side (`build_capability_summary`). Render it as a compact stats block on the tab (e.g., "12 logic groups: 9 ok / 2 partial / 1 failed").
