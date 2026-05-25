# State machine review (candidates)

Source files: /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/GPT_GenLogic.xlsx, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/PM_Condition_Tree_Diagram.png, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/Sample_Power_Control_Specification.docx, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/input/GPT_GenLogic.xlsx, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/input/PM_Behavior_Logic_Sample.xlsx, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/input/PM_Condition_Tree_Diagram.png, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/input/PM_StateFlow_Timing_Sample.pdf, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/input/PM_State_Machine_Diagram.png, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/input/PM_System_Spec_Sample.docx, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/input/PM_Timing_Chart.png, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/input/Sample_Power_Control_Specification.docx, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/input/Shutoff_Condition_Spec_v2.docx, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/input/edited_Shutoff_Condition_Spec.docx, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/input/pm_controller_sample.cpp, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/input/power_mode_gtest_sample.cpp, /Users/tranthaonguyen/TruongHuy/TMC_Cursor/pm_sample_inputs/output/PM_TestSpec_Reference_Sample.xlsx

Semantic graph: 32 states, 16 edges (9 explicit, 3 rule-inferred)

- **OFF** — None (mode: None)
- **ACCESSORY** — None (mode: None)
- **RUN** — None (mode: None)
- **SHUT_OFF** — None (mode: None)
- **ANY** — None (mode: None)
- **NORMAL** — None (mode: None)
- **MODE_STS SHALL NOT BECOME 0 DUE TO TR_PM_001** — None (mode: None)
- **TC_PM_001** — None (mode: None)
- **Power Mode Control** — None (mode: None)
- **TC_PM_002** — None (mode: None)
- **TC_PM_003** — None (mode: None)
- **TC_PM_004** — None (mode: None)
- **ACC_RELAY** —  (mode: None)
- **ADM1_OFF_ADM1_ACC** —  (mode: None)
- **CONDITION_D** —  (mode: None)
- **DIAG_FLAG** —  (mode: None)
- **FAIL_SAFE** —  (mode: None)
- **FALLBACK** —  (mode: None)
- **FALLBACK_OFF** —  (mode: None)
- **MODE_CMD** —  (mode: None)
- **MODE_STS** —  (mode: None)
- **MODE_STS_SHALL_NOT_BECOME_0_DUE_TO_TR_PM_001** —  (mode: None)
- **NOK_SHUTOFF** —  (mode: None)
- **OK_SHUTOFF** —  (mode: None)
- **PAND_CONDITION_E_LEAF_DEFINITIONS** —  (mode: None)
- **POWER_MODE_CONTROL** —  (mode: None)
- **PWR_STATE** —  (mode: None)
- **RELAY_MAIN** —  (mode: None)
- **RESET_CONDITION** —  (mode: None)
- **RESET_SHUTOFF** —  (mode: None)
- **SAMPLE_POWER_MODE_STATE_MACHINE** —  (mode: None)
- **SAMPLE_TIMING_CHART_SHUTDOWN_REQUEST** —  (mode: None)
- **SHUT_OFF_PERMISSION** —  (mode: None)
- **T_TRANS_EXCEEDED** —  (mode: None)

## Transitions (raw extraction)
- `TR_OFF_ACC` OFF → ACCESSORY — cond: `PWR_REQ_VALID AND IGN_STS=1 AND NOT NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram: OFF→ACCESSORY`
- `TR_ACC_RUN` ACCESSORY → RUN — cond: `PWR_REQ_VALID AND GEAR_POS=P AND BATT_OK=1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1 | Diagram: ACCESSORY`
- `TR_RUN_SHUT` RUN → SHUT_OFF — cond: `SYS_SHUTOFF AND NOT NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P; VEH_SPD=0 | Diagram: RUN→SHUT`
- `TR_SHUT_OFF` SHUT_OFF → OFF — cond: `RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF`
- `TR_FAIL_OFF` ANY → OFF — cond: `T_FAIL_TIMEOUT elapsed OR DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout or diagnostic | Diagram: Any→OFF f`
- `SM_001` NORMAL → SHUT_OFF — cond: `Previous State = NORMAL; Next State = SHUT_OFF`
- `SM_P_001` None → None — cond: `SHUT_OFF_PERMISSION = Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)`
- `SM_P_002` None → None — cond: `RESET_CONDITION = Condition_R1 OR Condition_R2 OR Condition_R3`
- `SM_LB_001` NORMAL → SHUT_OFF — cond: `Condition_E / Request input active for T_CONFIRM AND Condition_A / Vehicle condition = stationary AND Condition_B / Proc`
- `SM_D_001` NORMAL → SHUT_OFF — cond: `NORMAL → SHUT_OFF`
- `TR_OFF_ACC` OFF → ACCESSORY — cond: `PWR_REQ_VALID AND IGN_STS=1 AND NOT NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram: OFF→ACCESSORY`
- `TR_ACC_RUN` ACCESSORY → RUN — cond: `PWR_REQ_VALID AND GEAR_POS=P AND BATT_OK=1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1 | Diagram: ACCESSORY`
- `TR_RUN_SHUT` RUN → SHUT_OFF — cond: `SYS_SHUTOFF AND NOT NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P; VEH_SPD=0 | Diagram: RUN→SHUT`
- `TR_SHUT_OFF` SHUT_OFF → OFF — cond: `RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF`
- `TR_FAIL_OFF` ANY → OFF — cond: `T_FAIL_TIMEOUT elapsed OR DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout or diagnostic | Diagram: Any→OFF f`
- `SM_001` MODE_STS SHALL NOT BECOME 0 DUE TO TR_PM_001 → MODE_STS SHALL NOT BECOME 0 DUE TO TR_PM_001 — cond: `TC_PM_003 | Power Mode Control | Condition B false | Verify shutoff is not triggered when vehicle is not stopped | Given`
- `SM_001` NORMAL → SHUT_OFF — cond: `Previous State = NORMAL; Next State = SHUT_OFF`
- `SM_P_001` None → None — cond: `SHUT_OFF_PERMISSION = Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)`
- `SM_P_002` None → None — cond: `RESET_CONDITION = Condition_R1 OR Condition_R2 OR Condition_R3`
- `SM_LB_001` NORMAL → SHUT_OFF — cond: `Condition_E / Request input active for T_CONFIRM AND Condition_A / Vehicle condition = stationary AND Condition_B / Proc`
- `SM_D_001` NORMAL → SHUT_OFF — cond: `NORMAL → SHUT_OFF`
- `SM_P_001` None → None — cond: `OK_SHUTOFF = TRUE`
- `SM_P_002` None → None — cond: `NOK_SHUTOFF = TRUE`
- `SM_P_003` None → None — cond: `RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE`
- `SM_D_001` NORMAL → SHUT_OFF — cond: `OK_SHUTOFF = TRUE`
- `SM_D_002` NORMAL → NORMAL — cond: `NOK_SHUTOFF = TRUE`
- `SM_D_003` NORMAL → NORMAL — cond: `RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE`
- `SM_P_001` None → None — cond: `OK_SHUTOFF = TRUE`
- `SM_P_002` None → None — cond: `NOK_SHUTOFF = TRUE`
- `SM_P_003` None → None — cond: `RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE`
- `SM_D_001` NORMAL → SHUT_OFF — cond: `OK_SHUTOFF = TRUE`
- `SM_D_002` NORMAL → NORMAL — cond: `NOK_SHUTOFF = TRUE`
- `SM_D_003` NORMAL → NORMAL — cond: `RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE`
- `TR_001` TC_PM_001 → Power Mode Control — cond: `Verify shutoff when all mandatory conditions are satisfied and Condition_C branch is true`
- `TR_002` TC_PM_002 → Power Mode Control — cond: `Verify shutoff when OR branch Condition_D is true`
- `TR_003` TC_PM_003 → Power Mode Control — cond: `Verify no shutoff before shutdown timer threshold`
- `TR_004` TC_PM_004 → Power Mode Control — cond: `Verify no shutoff when vehicle speed is not zero`

## Semantic edges
- OFF → ACCESSORY | event=Accessory request | type=explicit_transition | evidence=GPT_GenLogic.xlsx / excel_transition_table / row 64
- ACCESSORY → RUN | event=Run request | type=explicit_transition | evidence=GPT_GenLogic.xlsx / excel_transition_table / row 65
- RUN → SHUT_OFF | event=Shutoff request | type=explicit_transition | evidence=GPT_GenLogic.xlsx / excel_transition_table / row 66
- SHUT_OFF → OFF | event=Shutdown complete | type=explicit_transition | evidence=GPT_GenLogic.xlsx / excel_transition_table / row 67
- ANY → OFF | event=Transition failed | type=explicit_transition | evidence=GPT_GenLogic.xlsx / excel_transition_table / row 68
- NORMAL → SHUT_OFF | event=state_transition | type=explicit_transition | evidence=Sample_Power_Control_Specification.docx / table_5 / row 2
- NORMAL → SHUT_OFF | event=logic_table_transition | type=explicit_transition | evidence=Sample_Power_Control_Specification.docx / table_4
- NORMAL → SHUT_OFF | event=diagram_transition | type=explicit_arrow | evidence=Sample_Power_Control_Specification.docx / diagram_narrative / paragraph 13
- MODE_STS_SHALL_NOT_BECOME_0_DUE_TO_TR_PM_001 → MODE_STS_SHALL_NOT_BECOME_0_DUE_TO_TR_PM_001 | event=state_transition | type=explicit_transition | evidence=PM_Behavior_Logic_Sample.xlsx / row 4
- NORMAL → SHUT_OFF | event=OK_SHUTOFF | type=rule_inferred | evidence=Shutoff_Condition_Spec_v2.docx / diagram_narrative / paragraph 25; edited_Shutoff_Condition_Spec.docx / diagram_narrative / paragraph 25
- NORMAL → NORMAL | event=NOK_SHUTOFF | type=rule_inferred | evidence=Shutoff_Condition_Spec_v2.docx / diagram_narrative / paragraph 26; edited_Shutoff_Condition_Spec.docx / diagram_narrative / paragraph 26
- NORMAL → NORMAL | event=RESET_SHUTOFF | type=rule_inferred | evidence=Shutoff_Condition_Spec_v2.docx / diagram_narrative / paragraph 27; edited_Shutoff_Condition_Spec.docx / diagram_narrative / paragraph 27
- TC_PM_001 → POWER_MODE_CONTROL | event=Shutdown request active | type=state_rule | evidence=PM_TestSpec_Reference_Sample.xlsx
- TC_PM_002 → POWER_MODE_CONTROL | event=Shutdown request active | type=state_rule | evidence=PM_TestSpec_Reference_Sample.xlsx
- TC_PM_003 → POWER_MODE_CONTROL | event=Timing boundary | type=state_rule | evidence=PM_TestSpec_Reference_Sample.xlsx
- TC_PM_004 → POWER_MODE_CONTROL | event=Mandatory condition false | type=state_rule | evidence=PM_TestSpec_Reference_Sample.xlsx
