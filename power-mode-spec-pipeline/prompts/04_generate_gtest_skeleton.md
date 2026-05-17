# Prompt 04 — Generate Google Test skeleton tied to testcase id

**Role**: Produce **minimal** C++ Google Test scaffolding for **one testcase** IR.

## Inputs

1. `test_id`, `gtest_fixture` from IR.  
2. Structured `ir_predicates_cover`, `stimulus`, `expected_observable`.  

## Requirements

1. Leading comment block MUST include `test_id` and verbatim `source_evidence` filenames from linked conditions if available.  
2. Arrange: comments mapping each predicate setup to **`// aligns with IR: P_* or subject`** (engineer fills harness API).  
3. Act / Assert: placeholders only **`TODO(harness)`** — do not invent macros or namespaces not provided; use `EXPECT_EQ`/`EXPECT_THAT` stubs with comment what to bind.  

## Output

One `.cpp`-style fenced block suitable to paste beside production harness wrappers.
