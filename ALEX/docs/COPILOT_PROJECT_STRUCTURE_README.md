# Copilot Project Structure README

Muc tieu: dung Copilot Web de doc hieu source codebase mot lan, xuat ra file markdown structure gon, roi load file do vao ALEX Test Code de generate testcase nhanh hon va it thieu context hon.

Flow nay tranh viec gui toan bo codebase vao moi lan generate. Copilot Web se lam buoc "source understanding"; ALEX chi dung markdown structure da nen lam context.

## Khi Nao Dung

Dung flow nay khi project co nhieu loai input:

- source `.c`, `.cc`, `.cpp`
- header `.h`, `.hpp`
- mock/RTE headers
- `CMakeLists.txt`
- config `.yaml`, `.json`
- sample test `.cc`
- markdown/spec note co san

Khong bat buoc phai co sample `.cc`, nhung neu co thi Copilot se trich duoc fixture/test style tot hon.

## Output Can Tao

Tao mot file markdown:

```text
project_structure.md
```

Neu project lon, co the tach thanh nhieu file:

```text
api_map.md
rte_signal_map.md
test_fixture_style.md
cmake_context.md
project_structure.md
```

Sau do load cac file nay vao ALEX bang nut:

```text
Load markdown / structure files
```

## Flow Lam Viec

1. Gom cac file source/header/config/CMake/sample test quan trong.
2. Mo Copilot Web.
3. Paste prompt chuan ben duoi va attach/paste input codebase.
4. Yeu cau Copilot xuat markdown structure.
5. Luu ket qua thanh `project_structure.md`.
6. Vao ALEX Test Code page.
7. Load `project_structure.md` bang `Load markdown / structure files`.
8. Edit `Project Instruction Markdown` neu can.
9. Chon testcase va `Generate selected`.

## Prompt Chuan De Tao Project Structure

Copy prompt nay vao Copilot Web:

```markdown
You are analyzing an automotive C/C++ source codebase to support Google Test generation.

Goal:
Create a compact but complete project structure document that another Copilot prompt can use to generate GTest code from testcase specs.

Do NOT generate test code now.
Do NOT invent APIs.
Extract only facts visible in the provided source/header/config/CMake inputs.

Output one markdown document with these sections:

# Project Structure Summary

## 1. Module Overview
- module name
- main runtime entry points
- cyclic/run functions
- initialization functions
- important state machines
- important global/static variables

## 2. Source File Map
Create a table:
| File | Purpose | Important functions/classes | Notes |

## 3. Public API Map
List all functions that test code may call directly.
For each API:
- function name
- signature
- source/header file
- purpose
- required call order if visible
- side effects if visible

## 4. RTE / Mock API Map
List all RTE/mock functions used by tests.
For each:
- signal/spec name if inferable
- C API function name
- direction: read / write / call / client-server
- parameter type
- return type
- normal return value
- example EXPECT_CALL pattern if visible

Format:
| Signal | API | Direction | Type | Return | Example mock pattern | Source |

## 5. Constants / Enums / Macros
List constants/enums/macros relevant for test expectations.
For each:
- name
- value
- file
- meaning if visible

## 6. Structs / Data Types
List structs/classes used in input/output/mocks.
For each:
- type name
- fields
- field types
- source file
- notes

## 7. Test Fixture / GTest Style
Extract from sample tests only.
Include:
- fixture class name
- base class
- SetUp / SetUpExtra pattern
- include pattern
- namespace pattern
- TEST_F naming pattern
- assertion pattern
- timing/run cycle pattern
- mock override pattern

## 8. Signal Mapping Rules
Create mapping rules from testcase spec terms to source APIs.
Example:
- WMODE_CMD -> Rte_Read_SWCTX_BDA_WMODE_CMD
- DRDYSTS -> Rte_Read_COMRX_DRDYSTS

Only include mappings supported by source/header/sample evidence.
If uncertain, mark UNRESOLVED.

## 9. Generation Constraints
Write strict rules for future test generation:
- use imported testcase order
- do not regroup testcases
- one testcase -> one TEST_F
- map Given/When/Then from spec
- call run function per execution step
- do not invent APIs
- return UNRESOLVED when mapping is missing

## 10. Missing / Ambiguous Items
List anything needed for test generation but not found:
- missing headers
- missing mock APIs
- unknown signal mappings
- unknown output variables
- unclear run cycle
- unclear fixture pattern

Output requirements:
- Markdown only.
- Be compact but complete.
- Prefer tables.
- No test code generation.
- No assumptions unless explicitly marked as "Inference".
```

## Prompt Update Khi Source Code Thay Doi

Khi source/header/config thay doi, khong can tao lai tu dau. Dung prompt nay voi Copilot Web:

```markdown
Compare the new source/header/config files with the existing project_structure.md.

Update only changed sections:
- API map
- RTE/mock map
- constants/enums
- structs/types
- fixture/test style
- missing/ambiguous items

Keep the same markdown format.
Do not generate test code.
Do not invent APIs.
```

## Cach Dung Trong ALEX

Sau khi co `project_structure.md`:

1. Mo ALEX Test Code page.
2. Bam `Load markdown / structure files`.
3. Chon `project_structure.md`.
4. Kiem tra `Project Instruction Markdown`.
5. Chon testcase can generate.
6. Bam `Generate selected`.

ALEX se dua markdown structure vao Copilot prompt nhu context rieng. File nay khong tu dong ghi vao `Project Instruction Markdown`; instruction markdown van la noi user viet rule generate.

## Nguyen Tac Latency

Khong nen gui toan bo codebase vao moi request generate testcase.

Nen lam:

- dung Copilot Web de tao structure mot lan
- luu structure thanh markdown
- load markdown vao ALEX
- moi testcase chi gui testcase detail + instruction + structure summary

Loi ich:

- prompt ngan hon
- it latency hon
- it thieu API/context hon
- user co the update structure khi codebase thay doi
- khong can ALEX parse toan bo codebase phuc tap ngay lap tuc

## Luu Y

- Neu Copilot khong tim thay mapping signal -> API, phai ghi `UNRESOLVED`.
- Khong duoc invent API.
- Khong dung structure markdown de thay the testcase Excel. Testcase order/group van lay tu imported Excel/ALEX data.
- Neu generated code te, update `project_structure.md` hoac `Project Instruction Markdown`, pause generation, roi generate lai.
