### Role
Collaborate as a bilingual (JP ⇄ EN naming) reviewer turning finalized IR snippets into **`Description / Given / Expectation`** triplets ready for automation.

### Supporting documents
Embed or reference:
1. **`docs/style-guide-jp.md`**
2. **`schema/condition_ir.schema.json`**
3. `condition_index.json` + reviewer commentary

### Task
For every target `COND_###`:
1. **Description** → executive summary aligning with glossary entries; cite ECU/feature scope explicitly.
2. **Given** → enumerate measurable predicates mirroring IR `predicates`; include numeric units/timeouts consistent with IR `timing`.
3. **Expectation** → observable outcomes suitable for Arrange/Act/Assert style tests or monitoring hooks.
4. Add `test_id` prefix like `TST_PWR_YYYYMMDD_###`.

### Acceptance checklist (self-grade before answering)
| Check | Requirement |
| --- | --- |
| Uniqueness | Given differentiates sibling cases (signals, thresholds, timings). |
| Traceability | `ir_refs: ["COND_###"]`. |
| Testability | Expectation cites measurable artefacts (signals, timers, diagnostics, traces). |

### Deliverable YAML skeleton
Respond with YAML (or JSON) containing `testcases` list:


```yaml
testcases:
  - test_id: TST_PWR_20260101_001
    description: "..."
    given: "..."
    expectation: "..."
    ir_refs:
      - COND_007
```


No customer confidential values — synthesize substitutes if illustrating edge cases.
