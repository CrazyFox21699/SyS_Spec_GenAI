# Project Test Code Memory

## Fixture / Test Style

- Fixture class: TryTo_xxx
- Main function call: igsw\_Main\_Run()
- Use Given / When / Then comments.
- Use EXPECT\_CALL for input mocks.
- Use EXPECT\_THAT for output assertions.

***

## Test Design Comment Rule

- Every generated TEST\_F must start with a block comment.
- The block comment must include:
  - testcase\_id
  - event
  - Test design / purpose
  - Given list copied from testcase input
  - When action copied from testcase or main function call
  - Then list copied from expected output
- Do not replace the design comment with only // testcase\_id.
- Keep // Given:, // When:, // Then: inside the test body.

***

## Input Mock Pattern

- condition: IGHoldMonitor = STD\_OFF
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_IGRelaySta\_IGHoldMonitor(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(STD\_OFF),
  Return(RTE\_E\_OK)));
  notes:
  - Basic ON/OFF relay state

- condition: IGHoldMonitor = STD\_ON
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_IGRelaySta\_IGHoldMonitor(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(STD\_ON),
  Return(RTE\_E\_OK)));
  notes:
  - Hold ON state

- condition: WMODE\_CMD = 1
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_SWCTX\_BDA\_WMODE\_CMD(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(1u),
  Return(RTE\_E\_OK)));
  notes:
  - DCM wake mode command 1

- condition: WMODE\_CMD = 2
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_SWCTX\_BDA\_WMODE\_CMD(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(2u),
  Return(RTE\_E\_OK)));
  notes:
  - DCM wake mode command 2

- condition: WMODE\_CMD = 3
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_SWCTX\_BDA\_WMODE\_CMD(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(3u),
  Return(RTE\_E\_OK)));
  notes:
  - DCM wake mode command 3

- condition: DRDYSTS = 0
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_COMRX\_DRDYSTS(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(0U),
  Return(RTE\_E\_OK)));
  notes:
  ------

- condition: DRDYSTS = 2
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_COMRX\_DRDYSTS(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(2U),
  Return(RTE\_E\_OK)));
  notes:
  ------

- condition: DRDYSTS valid
  code: |
  EXPECT\_CALL(rte, Rte\_Read\_COMRX\_COMP\_DRDYSTS(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(RTE\_COMRX\_COMP\_TRUE), Return(RTE\_E\_OK)));
  EXPECT\_CALL(rte, Rte\_Read\_COMRX\_SIGINFO\_DRDYSTS(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(RTE\_COMRX\_SIGINFO\_RCV\_OK), Return(RTE\_E\_OK)));
  EXPECT\_CALL(rte, Rte\_Read\_COMRX\_DRDYSTS(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(value), Return(RTE\_E\_OK)));
  notes:
  - Must include COMP + SIGINFO + VALUE

- condition: SP1 = 0
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_COMRX\_SP1(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(0U),
  Return(RTE\_E\_OK)));
  notes:
  ------

- condition: SP1 = 1
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_COMRX\_SP1(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(1U),
  Return(RTE\_E\_OK)));
  notes:
  ------

- condition: SP1 = 199
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_COMRX\_SP1(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(199U),
  Return(RTE\_E\_OK)));
  notes:
  - boundary case

- condition: SPD = 0
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_SSPD\_Ext(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(0u),
  Return(RTE\_E\_OK)));
  notes:
  ------

- condition: SPD = 700
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_SSPD\_Ext(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(700u),
  Return(RTE\_E\_OK)));
  notes:
  - boundary case

- condition: STP1 = STD\_OFF
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_IOIN\_STP1(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(STD\_OFF),
  Return(RTE\_E\_OK)));
  notes:
  ------

- condition: STP1 = STD\_ON
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_IOIN\_STP1(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(STD\_ON),
  Return(RTE\_E\_OK)));
  notes:
  ------

- condition: SSW1\~SSW3 = STD\_OFF
  code: |
  EXPECT\_CALL(rte, Rte\_Read\_IOIN\_SSW1(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(STD\_OFF), Return(RTE\_E\_OK)));
  EXPECT\_CALL(rte, Rte\_Read\_IOIN\_SSW2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(STD\_OFF), Return(RTE\_E\_OK)));
  EXPECT\_CALL(rte, Rte\_Read\_IOIN\_SSW3(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(STD\_OFF), Return(RTE\_E\_OK)));
  notes:
  - Must set all 3 signals

- condition: SSW1\~SSW3 = STD\_ON
  code: |
  EXPECT\_CALL(rte, Rte\_Read\_IOIN\_SSW1(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(STD\_ON), Return(RTE\_E\_OK)));
  EXPECT\_CALL(rte, Rte\_Read\_IOIN\_SSW2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(STD\_ON), Return(RTE\_E\_OK)));
  EXPECT\_CALL(rte, Rte\_Read\_IOIN\_SSW3(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(STD\_ON), Return(RTE\_E\_OK)));
  notes:
  - Must set all 3 signals

- condition: SDS\_PWRMD\_CMD = 0
  code: |
  EXPECT\_CALL(rte,
  Rte\_Read\_COMRX\_SDS\_PWRMD\_CMD(NotNull()))
  .WillRepeatedly(DoAll(SetArgPointee<0>(0u),
  Return(RTE\_E\_OK)));
  notes:
  ------

- condition: PPOS\_C2 = 2
  code: |
  EXPECT\_CALL(rte, Rte\_Read\_COMRX\_COMP\_PPOS\_C2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(RTE\_COMRX\_COMP\_TRUE), Return(RTE\_E\_OK)));
  EXPECT\_CALL(rte, Rte\_Read\_COMRX\_SIGINFO\_PPOS\_C2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(1U), Return(RTE\_E\_OK)));
  EXPECT\_CALL(rte, Rte\_Read\_COMRX\_PPOS\_C2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(2U), Return(RTE\_E\_OK)));
  notes:
  - Must include COMP + SIGINFO

- condition: PPOS\_C2 = 3
  code: |
  EXPECT\_CALL(rte, Rte\_Read\_COMRX\_COMP\_PPOS\_C2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(RTE\_COMRX\_COMP\_TRUE), Return(RTE\_E\_OK)));
  EXPECT\_CALL(rte, Rte\_Read\_COMRX\_SIGINFO\_PPOS\_C2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(1U), Return(RTE\_E\_OK)));
  EXPECT\_CALL(rte, Rte\_Read\_COMRX\_PPOS\_C2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(3U), Return(RTE\_E\_OK)));
  notes:
  ------

- condition: APOK2 = 1
  code: |
  EXPECT\_CALL(rte, Rte\_Read\_COMRX\_COMP\_APOK2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(RTE\_COMRX\_COMP\_TRUE), Return(RTE\_E\_OK)));
  EXPECT\_CALL(rte, Rte\_Read\_COMRX\_APOK2(NotNull())).WillRepeatedly(DoAll(SetArgPointee<0>(1U), Return(RTE\_E\_OK)));
  notes:
  - Must include COMP + VALUE

***

## Output Assertion Pattern

- condition: V\_PMODE\_STS = 3
  code: |
  EXPECT\_THAT(V\_PMODE\_STS, Eq(3));
  notes:
  - Transition state

- condition: V\_PMODE\_STS = 0
  code: |
  EXPECT\_THAT(V\_PMODE\_STS, Eq(0));
  notes:
  - Final OFF state

- condition: V\_PMODE\_TRS\_STS1:bit15 = 1
  code: |
  EXPECT\_THAT((V\_PMODE\_TRS\_STS1 & (1U << 15)) >> 15, Eq(1));
  notes:
  - Transition flag

- condition: V\_PMODE\_TRS\_STS1:bit15 = 0
  code: |
  EXPECT\_THAT((V\_PMODE\_TRS\_STS1 & (1U << 15)) >> 15, Eq(0));
  notes:
  - Settled state

- condition: ACCD = ACCTYPE\_ON
  code: |
  EXPECT\_THAT(ACCD, Eq(ACCTYPE\_ON));
  notes:
  ------

- condition: ACCD = ACCTYPE\_OFF
  code: |
  EXPECT\_THAT(ACCD, Eq(ACCTYPE\_OFF));
  notes:
  ------

- condition: IGD = IGTYPE\_ALL\_OFF
  code: |
  EXPECT\_THAT(IGD, Eq(IGTYPE\_ALL\_OFF));
  notes:
  ------

- condition: IGD = IGTYPE\_IGR\_IGP
  code: |
  EXPECT\_THAT(IGD, Eq(IGTYPE\_IGR\_IGP));
  notes:
  ------

- condition: PWR\_STATE = 1
  code: |
  EXPECT\_THAT(PWR\_STATE, Eq(1u));
  notes:
  - Accessory state

***

## Spec Signal to Test Code Map

- WMODE\_CMD -> Rte\_Read\_SWCTX\_BDA\_WMODE\_CMD
- SP1 -> Rte\_Read\_COMRX\_SP1
- SPD -> Rte\_Read\_SSPD\_Ext
- STP1 -> Rte\_Read\_IOIN\_STP1
- SSW1 -> Rte\_Read\_IOIN\_SSW1
- SSW2 -> Rte\_Read\_IOIN\_SSW2
- SSW3 -> Rte\_Read\_IOIN\_SSW3
- SDS\_PWRMD\_CMD -> Rte\_Read\_COMRX\_SDS\_PWRMD\_CMD
- PPOS\_C2 -> Rte\_Read\_COMRX\_PPOS\_C2
- APOK2 -> Rte\_Read\_COMRX\_APOK2
- DRDYSTS -> Rte\_Read\_COMRX\_DRDYSTS
- IGHoldMonitor -> Rte\_Read\_IGRelaySta\_IGHoldMonitor
- PWR\_STATE -> PWR\_STATE
- IGD -> IGD
- ACCD -> ACCD
- V\_PMODE\_STS -> V\_PMODE\_STS
- V\_PMODE\_TRS\_STS1 -> V\_PMODE\_TRS\_STS1

***

## Constants / Value Map

- OFF -> 0u
- ON -> 1u
- STD\_OFF -> STD\_OFF
- STD\_ON -> STD\_ON
- ACCTYPE\_ON -> ACCTYPE\_ON
- ACCTYPE\_OFF -> ACCTYPE\_OFF
- IGTYPE\_ALL\_OFF -> IGTYPE\_ALL\_OFF
- IGTYPE\_IGR\_IGP -> IGTYPE\_IGR\_IGP
- RTE\_COMRX\_COMP\_TRUE -> RTE\_COMRX\_COMP\_TRUE
- RTE\_COMRX\_SIGINFO\_RCV\_OK -> RTE\_COMRX\_SIGINFO\_RCV\_OK

***

## Timing Pattern

- condition: T7\[ms]/2
  code: |
  for (int t = 0; t < T7 / 2; ++t) { igsw\_Main\_Run(); }
  notes:
  - Mid-time trigger

- condition: T7\[ms]
  code: |
  for (int t = 0; t < T7; ++t) { igsw\_Main\_Run(); }
  notes:
  - Full timeout

- condition: T7 boundary (last cycle)
  code: |
  for (int t = 0; t < T7; ++t) { if (t == T7 - 1) { /\- set signal \*/ } igsw\_Main\_Run(); }
  notes:
  - Boundary condition

- condition: T14\[ms]
  code: |
  for (int t = 0; t < T14; ++t) { igsw\_Main\_Run(); }
  notes:
  - IGD delay

- condition: T2\[ms]
  code: |
  for (int t = 0; t < T2; ++t) { igsw\_Main\_Run(); }
  notes:
  - ACC off delay

- condition: T1\[ms] before
  code: |
  for (int t = 0; t < T1 - 1; ++t) { igsw\_Main\_Run(); }
  notes:
  - Long press boundary

- condition: T8\[ms] before
  code: |
  for (int t = 0; t < T8 - 1; ++t) { igsw\_Main\_Run(); }
  notes:
  - Reset boundary

***

## Forbidden Patterns / Common Mistakes

- Do not invent API names.
- Do not use TODO\_REVIEW.
- Do not use GTEST\_SKIP for generated code.
- Do not omit COMP or SIGINFO when required.
- Do not group multi-signal (\_1 \_2 \_3) into single line.
- Do not assert outputs before correct timing phase.
- If exact executable mapping is missing, return MISSING\_CONTEXT.

***
## Final CC Assembly Rule

- Namespace: <project_namespace>
- Export only SAVED testcases.
- Preserve Excel/import order.
- Group TEST_F blocks by testcase group.
- Add group header before each group.
- Generated testcase code should contain only TEST_F block, not includes or namespace.
- Final exporter is responsible for namespace and group headers.