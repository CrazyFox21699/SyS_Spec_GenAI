# Prompt 03 — Audit spec prose vs canonical IR

**Role**: Requirement consistency checker — catch omissions, hallucinations, and tone regressions before customer review.

## Inputs

1. Customer spec Markdown (Prompt 02 output).  
2. Same testcase IR (structured).  
3. Style guide excerpts (forbidden synonyms, bilingual rules).

## Checklist output

Produce Markdown report:

| Check | PASS/FAIL | Notes |
|-------|-----------|-------|
| Every IR predicate echoed in Given | ... | cite missing IDs |
| No expectation beyond `expected_observable` | ... | |
| Description unique vs neighbor cases listed | WARN/PASS | |
| Terminology vs glossary | ... | |
| Register / tone (JA rules) | ... | |

Finish with **`VERDICT: APPROVED | REVISE`** and bullet actions if REVISE.
