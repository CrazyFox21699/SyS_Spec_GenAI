# State machine review (candidates)

Source files: /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/GPT_GenLogic.xlsx, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/input/GPT_GenLogic.xlsx

Semantic graph: 9 states, 5 edges (5 explicit, 0 rule-inferred)

- **OFF** — None (mode: None)
- **ACCESSORY** — None (mode: None)
- **RUN** — None (mode: None)
- **SHUT_OFF** — None (mode: None)
- **ANY** — None (mode: None)
- **DIAG_FLAG** —  (mode: None)
- **FALLBACK_OFF** —  (mode: None)
- **PWR_STATE** —  (mode: None)
- **RELAY_MAIN** —  (mode: None)

## Transitions (raw extraction)
- `TR_OFF_ACC` OFF → ACCESSORY — cond: `PWR_REQ_VALID AND IGN_STS=1 AND NOT NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram: OFF→ACCESSORY`
- `TR_ACC_RUN` ACCESSORY → RUN — cond: `PWR_REQ_VALID AND GEAR_POS=P AND BATT_OK=1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1 | Diagram: ACCESSORY`
- `TR_RUN_SHUT` RUN → SHUT_OFF — cond: `SYS_SHUTOFF AND NOT NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P; VEH_SPD=0 | Diagram: RUN→SHUT`
- `TR_SHUT_OFF` SHUT_OFF → OFF — cond: `RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF`
- `TR_FAIL_OFF` ANY → OFF — cond: `T_FAIL_TIMEOUT elapsed OR DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout or diagnostic | Diagram: Any→OFF f`
- `TR_OFF_ACC` OFF → ACCESSORY — cond: `PWR_REQ_VALID AND IGN_STS=1 AND NOT NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram: OFF→ACCESSORY`
- `TR_ACC_RUN` ACCESSORY → RUN — cond: `PWR_REQ_VALID AND GEAR_POS=P AND BATT_OK=1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1 | Diagram: ACCESSORY`
- `TR_RUN_SHUT` RUN → SHUT_OFF — cond: `SYS_SHUTOFF AND NOT NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P; VEH_SPD=0 | Diagram: RUN→SHUT`
- `TR_SHUT_OFF` SHUT_OFF → OFF — cond: `RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF`
- `TR_FAIL_OFF` ANY → OFF — cond: `T_FAIL_TIMEOUT elapsed OR DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout or diagnostic | Diagram: Any→OFF f`

## Semantic edges
- OFF → ACCESSORY | event=Accessory request | type=explicit_transition | evidence=GPT_GenLogic.xlsx / excel_transition_table / row 64
- ACCESSORY → RUN | event=Run request | type=explicit_transition | evidence=GPT_GenLogic.xlsx / excel_transition_table / row 65
- RUN → SHUT_OFF | event=Shutoff request | type=explicit_transition | evidence=GPT_GenLogic.xlsx / excel_transition_table / row 66
- SHUT_OFF → OFF | event=Shutdown complete | type=explicit_transition | evidence=GPT_GenLogic.xlsx / excel_transition_table / row 67
- ANY → OFF | event=Transition failed | type=explicit_transition | evidence=GPT_GenLogic.xlsx / excel_transition_table / row 68
