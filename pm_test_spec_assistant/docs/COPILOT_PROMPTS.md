# ALEX — Copilot prompt pack (English)

Use with per-job `copilot_context/<logic_id>/` packs. Copilot output is **advisory only** (`review_required: true`). Do not overwrite deterministic AST.

## 1. State machine from shapes / diagram

```
You are assisting ALEX (deterministic spec tool). Given OCR text and shape list below,
propose states and transitions in plain language. Cite shape_id or image region for each claim.
Output JSON: { "interpretation": "...", "states": [], "transitions": [], "open_questions": [] }
Do NOT output AND/OR/NOT AST.
```

## 2. Wiring / connector topology

```
Given connector list and anchor cells, describe signal flow between blocks.
Mark uncertain links in open_questions. JSON only; no AST.
```

## 3. Condition tree from diagram image

```
Given OCR lines from a condition-tree diagram, list leaf conditions and OR/AND groups
as narrative only. Ask engineer to confirm before ALEX parses tables.
```

## 4. Japanese → English glossary

```
Translate technical terms below. Keep signal names unchanged. Flag ambiguous terms in open_questions.
```

## 5. Expected input / output (workbook columns)

Follow `docs/TEST_SPEC_IO_FORMAT.md`. Write newline-separated lines only:

**Expected input** — `Given: SIG=value`, `Precondition: State NAME`, optional `When: …`

**Expected output** — `Then: SIG=value`

Do not put evidence blobs, logic trees, or `logic:` / `transition:` debug text in these fields.
