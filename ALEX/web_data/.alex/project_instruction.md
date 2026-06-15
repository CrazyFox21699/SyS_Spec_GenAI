Generate Google Test C++ .cc code.

Use project_testcode_memory.md as source of truth.
Use exact code blocks from memory.
Do not invent API names, variables, constants, fixture names, or setup functions.
Precondition is comment-only unless State Setup Pattern exists in memory.
Every TEST_F must include full test design block comment with testcase_id, event, Given, When, Then.
Return MISSING_CONTEXT only when executable mapping is missing.
Return [TESTCASE_CODE] only for real compilable test code.