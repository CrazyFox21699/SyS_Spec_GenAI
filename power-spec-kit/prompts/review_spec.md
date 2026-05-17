### Goal
Conduct a deterministic review on LLM-produced triplets/spec YAML before codegen.

### Prerequisites
Triplets authored per `prompts/draft_spec_triplets.md`; IR validated separately.

### Automated gate
Run:


```bash
python3 scripts/validate_spec.py path/to/tests.yaml \
  --ir-index condition_index.json \
  [--strict]
```

### Manual checklist
1. **Signal vocabulary** — aligns with glossary & IR `predicate.signal` literals.
2. **Timing coherence** — debounce/hold values match IR `timing`.
3. **Dependency closure** — if description references another mode, triplets cite both `COND_` IDs (`ir_refs` lists all required conditions).
4. **Negative-path coverage** — at least one triplet probes forbidden transition / inhibit factor when specifications mention it.
5. **Residual risk registry** — list open items referencing `condition_index.json → unresolved_references`.

### Deliverable template
Produce markdown report:

```
## verdict: approve | revise | blocked
### blocking issues (must fix)
...
### polish (optional)
...
### traceability matrix (test_id × COND_*)
...
```
