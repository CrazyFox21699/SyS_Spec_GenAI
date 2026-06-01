\===== ALEX\_CODE\_CONFIG\_BUNDLE\_START =====

## 1. code\_rules.md

### Fixture rule

* Use `TEST_F(<FixtureClass>, <TestName>)`
* Fixture must inherit from `RteDefaultAction`
* Override `SetUpExtra()` to initialize:
  * NV memory
  * initial power state
  * relay monitor defaults
* Timing constants must be defined as class `const` members (e.g., `T1`, `T2`, `T7`)

***

### Test naming rule

* Pattern:
  `<BehaviorTrigger>`
* Use concise English camel-case without spaces  
  Example:
  * `ByApok2OkWithinT7`
  * `ByPowerModeCmdRunAndAutoMode`

***

### testcase\_id traceability rule

* Do NOT embed testcase ID into function name
* Trace via structured comments above test:
  * include GIVEN/WHEN/THEN block
  * match Excel wording closely
* Preserve Japanese comments if present

***

### input setup rule

* All inputs must be mocked via `EXPECT_CALL(rte, Rte_Read_XXX(...))`
* Always use:
  * `NotNull()` pointer matcher
  * `WillRepeatedly(DoAll(SetArgPointee<0>(value), Return(RTE_E_OK)))`
* For signals:
  * Must set 3 layers if applicable:
    * `_COMP`
    * `_SIGINFO`
    * raw signal
* Sequence must follow Given → igsw\_Main\_Run() → next Given

***

### output assertion rule

* Use `EXPECT_THAT(variable, Eq(expected))`
* Bit extraction:
  ```
  EXPECT_THAT((VAR & (1U << bit)) >> bit, Eq(expected))
  ```
* Direct variable usage allowed for globals:
  * `V_PMODE_STS`
  * `ACCD`
  * `IGD`

***

### timing/wait rule

* Use loop-based execution:
  ```
  for (int t = 0; t < Txx; ++t) {
      igsw_Main_Run();
  }
  ```
* Single-cycle trigger:
  ```
  igsw_Main_Run();
  ```
* Boundary injection:
  ```
  if (t == (T7 - 1)) { ... }
  ```

***

### mock/stub rule

* Use `gmock` macros:
  * `EXPECT_CALL`
  * `SetArgPointee`
  * `SetArrayArgument`
* Default: `WillRepeatedly(...)`
* Single-cycle event: `WillOnce(...)`
* DID write:
  * explicit call: `igsw_Sid2e_Write(...)`

***

### forbidden patterns

* ❌ Direct assignment to RTE signals
* ❌ Introducing helper wrapper APIs
* ❌ Using sleep/delay APIs
* ❌ Skipping COMP/SIGINFO layer
* ❌ Using ASSERT\_\* instead of EXPECT\_\*

***

### preferred patterns

* ✅ Use `EXPECT_CALL(...).WillRepeatedly(...)` for stable inputs
* ✅ Use loop-based time simulation
* ✅ Use explicit state transition comments
* ✅ Use bit extraction inline
* ✅ Separate Given/When/Then clearly

***

### what not to invent

* Do NOT invent:
  * setter functions (no SetXxx)
  * getter functions (no GetXxx)
  * utility helpers (WaitMs, RunFor, etc.)
* Only use:
  * `Rte_Read_*`
  * `igsw_Main_Run`
  * `igsw_Sid2e_Write`

***

## 2. signal\_mapping.yaml

WMODE\_CMD:
setter: EXPECT\_CALL(rte, Rte\_Read\_SWCTX\_BDA\_WMODE\_CMD(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({value}), Return(RTE\_E\_OK)))

SDS\_PWRMD\_CMD:
setter: EXPECT\_CALL(rte, Rte\_Read\_COMRX\_SDS\_PWRMD\_CMD(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({value}), Return(RTE\_E\_OK)))

DRDYSTS:
setter:
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_COMP\_DRDYSTS(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(RTE\_COMRX\_COMP\_TRUE), Return(RTE\_E\_OK)))
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_SIGINFO\_DRDYSTS(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(1U), Return(RTE\_E\_OK)))
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_DRDYSTS(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({value}), Return(RTE\_E\_OK)))

SP1:
setter:
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_COMP\_SP1(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(RTE\_COMRX\_COMP\_TRUE), Return(RTE\_E\_OK)))
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_SIGINFO\_SP1(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(1U), Return(RTE\_E\_OK)))
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_SP1(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({value}), Return(RTE\_E\_OK)))

SPD:
setter: EXPECT\_CALL(rte, Rte\_Read\_SSPD\_Ext(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({value}), Return(RTE\_E\_OK)))

PPOS\_C2:
setter:
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_COMP\_PPOS\_C2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(RTE\_COMRX\_COMP\_TRUE), Return(RTE\_E\_OK)))
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_SIGINFO\_PPOS\_C2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(1U), Return(RTE\_E\_OK)))
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_PPOS\_C2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({value}), Return(RTE\_E\_OK)))

APOK2:
setter:
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_COMP\_APOK2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(RTE\_COMRX\_COMP\_TRUE), Return(RTE\_E\_OK)))
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_APOK2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({value}), Return(RTE\_E\_OK)))

RI\_APRJ:
setter:
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_COMP\_RI\_APRJ(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(RTE\_COMRX\_COMP\_TRUE), Return(RTE\_E\_OK)))
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_SIGINFO\_RI\_APRJ(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({siginfo}), Return(RTE\_E\_OK)))
\- EXPECT\_CALL(rte, Rte\_Read\_COMRX\_RI\_APRJ(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({value}), Return(RTE\_E\_OK)))

SSW:
setter:
\- EXPECT\_CALL(rte, Rte\_Read\_IOIN\_SSW1(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({value}), Return(RTE\_E\_OK)))
\- EXPECT\_CALL(rte, Rte\_Read\_IOIN\_SSW2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({value}), Return(RTE\_E\_OK)))
\- EXPECT\_CALL(rte, Rte\_Read\_IOIN\_SSW3(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>({value}), Return(RTE\_E\_OK)))

V\_PMODE\_STS:
getter: direct\_variable
assertion: EXPECT\_THAT(V\_PMODE\_STS, Eq({expected}))

V\_PMODE\_TRS\_STS1\_BIT15:
getter: direct\_variable\_bit
assertion: EXPECT\_THAT((V\_PMODE\_TRS\_STS1 & (1U << 15)) >> 15, Eq({expected}))

ACCD:
getter: direct\_variable
assertion: EXPECT\_THAT(ACCD, Eq({expected}))

IGD:
getter: direct\_variable
assertion: EXPECT\_THAT(IGD, Eq({expected}))

T\_WAIT:
code: |
for (int t = 0; t < {time}; ++t) {
igsw\_Main\_Run();
}

MAIN\_STEP:
code: igsw\_Main\_Run()

***

## 3. gtest\_template.md

```cpp
TEST_F({fixture}, {test_name})
{
    // ===== GIVEN =====
    {given_code}

    // Initial step
    igsw_Main_Run();

    // ===== WHEN =====
    {when_code}

    // Timing progression
    {timing_code}

    // ===== THEN =====
    {assertion_code}
}
```

***

## 4. api\_catalog.yaml

fixture:

* RteDefaultAction
* SetUpExtra()

core:

* igsw\_Main\_Run()
* igsw\_Sid2e\_Write(reqType, did, resultPtr)

setters:

* Rte\_Read\_\*

getters:

* direct variables:
  * V\_PMODE\_STS
  * V\_PMODE\_TRS\_STS1
  * ACCD
  * IGD

assertions:

* EXPECT\_THAT(expr, Eq(value))

timing:

* for-loop with igsw\_Main\_Run()

mocks:

* EXPECT\_CALL
* WillRepeatedly
* WillOnce
* DoAll
* SetArgPointee
* SetArrayArgument

utilities:

* NotNull()
* Return()

***

## 5. ai\_review\_pack.md

### AI Batch Review Prompt

You are reviewing generated GTest code.

Validate against:

* Testcase intent (Excel)
* code\_rules.md
* signal\_mapping.yaml
* api\_catalog.yaml

***

### Check for:

1. Missing GIVEN setup
2. Missing EXPECT\_CALL for inputs
3. Missing COMP/SIGINFO layer
4. Missing assertions
5. Incorrect timing loops
6. Incorrect bit extraction
7. Unknown APIs
8. Direct variable overwrites
9. Missing igsw\_Main\_Run() steps
10. Duplicate test names
11. Wrong signal mapping
12. Wrong state transition order

***

### Required Output Format

\[SUMMARY]

\[QUALITY\_FINDINGS]

\[PATCH\_PLAN]

\[PATCHES]

\[UNRESOLVED\_ITEMS]

***

\===== ALEX\_CODE\_CONFIG\_BUNDLE\_END =====
