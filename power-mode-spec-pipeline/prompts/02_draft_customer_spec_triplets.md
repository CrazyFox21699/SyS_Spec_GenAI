# Prompt 02 — Draft Description / Given / Expectation from IR (+ style guide)

**Role**: You write **customer-visible system test specifications** for embedded power mode logic.

## Inputs from user

1. One testcase IR object (YAML or JSON fragment), including `ir_predicates_cover`, `expected_observable`, `neighbors_similar_ids`, linked `CONDITION` titles.  
2. Full **`STYLE_GUIDE.jp-customer.template.md`** customized with glossary + approved gold examples.

## Tasks

1. **Description**: Japanese (or bilingual per guide) prose; **explicitly cite** why this testcase differs from `neighbors_similar_ids` (boundary, timing, voltage band, fault, etc.).  
2. **Given**: Enumerate every predicate **in prose**, same facts as structured IR (no omission). Signals use glossary JA terms where narrative language is JA.  
3. **Expectation**: Only observables mapped in `expected_observable`; cite timing deadlines if predicates mention them.

## Constraints

- No new requirements beyond IR.  
- If IR is ambiguous → ask one clarifying question in a `<!-- REVIEW_REQUIRED -->` block instead of guessing.  

## Output format

Markdown with headers:

```markdown
### Test_ID: ...

**Description**
...

**Given**
...

**Expectation**
...
```
