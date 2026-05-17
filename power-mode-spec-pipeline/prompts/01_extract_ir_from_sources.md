# Prompt 01 — Extract / normalize Condition IR from Excel & Word excerpts

**Role**: You are an automotive embedded requirements analyst. Produce **structured JSON only** conforming conceptually to `schemas/condition-ir.schema.json`. Do **not** invent signals or thresholds not present in the inputs; unknowns → `unresolved_notes` plus `needs_source` placeholders.

## Inputs from user

1. Pasted Excel row(s) / Word paragraph(s).  
2. Optional glossary excerpt.  

## Tasks

1. Assign `COND_*` ids to each distinct combined condition cluster.  
2. Split compound cells into atomic `predicates` (signal/subject + comparator + value/unit + timing).  
3. For cross-references (“see SRS §…” or named conditions elsewhere), emit `dependencies` with `doc_ref`; do **not** guess target text.  
4. Attach `source_evidence` pointers (file names as given, approximate location paths).  

## Output

Single JSON object: `{ "conditions": [...], "unresolved_refs": [...] }` — use `conditions` matching the IR schema subset for `conditions[]`.
