# Test Code Minimal Plan

Goal: make the Test Code page a single-testcase Copilot workflow. No batch UI, no YAML/config/mapping setup in the normal path, and no testcase regrouping. ALEX must preserve the testcase order and groups imported by the user.

## Main workflow

1. Load input files:
   - testcase/spec file from user
   - sample source files such as `.cc`, `.cpp`, `.h`
   - markdown instruction files
   - structure/context files
   - any other project sample input needed for prompt context
2. Show imported testcases as a vertical list from top to bottom in the exact imported order.
3. User clicks one testcase row.
4. ALEX builds the prompt from:
   - selected testcase
   - imported testcase group/order metadata as-is
   - sample code files
   - structure/context files
   - markdown instructions
   - standard output rules
5. ALEX calls Copilot API for only that testcase.
6. The testcase row shows a spinner while generation is running.
7. Generated code appears in the editor.
8. If code is wrong, user stops, edits markdown/input constraints, and generates that testcase again.
9. User saves/export final `.cc` when satisfied.

## Main screen

Keep only these visible areas:

- Input panel
  - load sample code files
  - load testcase/spec file
  - load markdown instruction files
  - load structure/context files
  - edit project instruction markdown
  - save instruction
- Testcase list
  - one vertical row per testcase
  - row status
  - spinner beside the active testcase
  - click row to generate that testcase
- Code review
  - generated code editor
  - validation warnings
  - save code
  - export `.cc`
- Manual fallback
  - copy selected testcase context + structure prompt for Copilot Web when API is too slow

## Remove from normal UI

- chunk size
- Copy Current Chunk Prompt
- Retry Failed Chunks
- Copy Failed Chunk Prompt
- Review NEEDS_REVIEW / ERROR workflow
- Generate All batch workflow
- Generate Current Group
- Progress Panel as batch/chunk progress
- Advanced
- YAML/config editors
- mapping coverage
- exemplar/local-template/smart fallback buttons

## Updated progress display

Replace batch progress with selected-testcase progress:

- total testcase count
- current testcase ID
- current testcase position, for example `12 / 80`
- current status: idle, generating, saved, needs review, error
- elapsed time for current testcase
- last response time
- last error message if available

Use `testcase`, `selected testcase`, and `generation status`.
Do not use `batch`, `chunk`, `group`, `similar group`, `regroup`, or `exemplar group` in the main UI.

## Prompt rules

Every Copilot prompt must explicitly say:

- use the imported testcase group/order as provided
- do not regroup testcase
- generate only the selected testcase ID
- return code mapped exactly to `testcase_id`
- if uncertain, return `UNRESOLVED` instead of inventing code

## Implementation phases

1. Add Windows setup/run/verify scripts.
2. Hide batch/chunk/advanced controls from the Test Code main screen.
3. Replace batch progress with selected-testcase progress.
4. Wire testcase row click to existing Copilot API generation for one testcase.
5. Add the manual fallback copy button for selected testcase context + structure.
6. Keep old backend features available only if still needed internally, but do not expose them in the normal UI.

## Constraints

- Do not add a new generation mode.
- Do not change backend generation behavior unless needed to route one selected testcase through existing Copilot API code.
- Do not change testcase grouping.
- Do not infer new groups.
- Preserve imported Excel order.
- Do not require YAML/config/mapping for normal use.
