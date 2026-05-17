# Test scenario candidates

| ID | Event | Description | Review |
| --- | --- | --- | --- |
| TC_PM_001 | Accessory request | Positive path for transition TR_OFF_ACC (OFF -> ACCESSORY) | yes |
| TC_PM_002 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_003 | guard_false_signal | Negate primary guard signal IGN_STS | yes |
| TC_PM_004 | Run request | Positive path for transition TR_ACC_RUN (ACCESSORY -> RUN) | yes |
| TC_PM_005 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_006 | guard_false_signal | Negate primary guard signal GEAR_POS | yes |
| TC_PM_007 | Shutoff request | Positive path for transition TR_RUN_SHUT (RUN -> SHUT_OFF) | yes |
| TC_PM_008 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_009 | Shutdown complete | Positive path for transition TR_SHUT_OFF (SHUT_OFF -> OFF) | yes |
| TC_PM_010 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_011 | Transition failed | Positive path for transition TR_FAIL_OFF (ANY -> OFF) | yes |
| TC_PM_012 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_013 | state_transition | Positive path for transition SM_001 (MODE_STS SHALL NOT BECOME 0 DUE TO TR_PM_001 -> MODE_STS SHALL NOT BECOME 0 DUE TO  | yes |
| TC_PM_014 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_015 | state_transition | Positive path for transition SM_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_016 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_017 | SHUT_OFF_PERMISSION | Positive path for transition SM_P_001 (None -> None) | yes |
| TC_PM_018 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_019 | guard_false_signal | Negate primary guard signal SHUT_OFF_PERMISSION | yes |
| TC_PM_020 | RESET_CONDITION | Positive path for transition SM_P_002 (None -> None) | yes |
| TC_PM_021 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_022 | guard_false_signal | Negate primary guard signal RESET_CONDITION | yes |
| TC_PM_023 | logic_table_transition | Positive path for transition SM_LB_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_024 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_025 | guard_false_signal | Negate primary guard signal Condition_A / Vehicle condition | yes |
| TC_PM_026 | diagram_transition | Positive path for transition SM_D_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_027 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_028 | OK_SHUTOFF | Positive path for transition SM_P_001 (None -> None) | yes |
| TC_PM_029 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_030 | guard_false_signal | Negate primary guard signal OK_SHUTOFF | yes |
| TC_PM_031 | NOK_SHUTOFF | Positive path for transition SM_P_002 (None -> None) | yes |
| TC_PM_032 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_033 | guard_false_signal | Negate primary guard signal NOK_SHUTOFF | yes |
| TC_PM_034 | RESET_SHUTOFF | Positive path for transition SM_P_003 (None -> None) | yes |
| TC_PM_035 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_036 | guard_false_signal | Negate primary guard signal RESET_SHUTOFF | yes |
| TC_PM_037 | OK_SHUTOFF | Positive path for transition SM_D_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_038 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_039 | guard_false_signal | Negate primary guard signal OK_SHUTOFF | yes |
| TC_PM_040 | NOK_SHUTOFF | Positive path for transition SM_D_002 (NORMAL -> NORMAL) | yes |
| TC_PM_041 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_042 | guard_false_signal | Negate primary guard signal NOK_SHUTOFF | yes |
| TC_PM_043 | RESET_SHUTOFF | Positive path for transition SM_D_003 (NORMAL -> NORMAL) | yes |
| TC_PM_044 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_045 | guard_false_signal | Negate primary guard signal RESET_SHUTOFF | yes |
| TC_PM_046 | OK_SHUTOFF | Positive path for transition SM_P_001 (None -> None) | yes |
| TC_PM_047 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_048 | guard_false_signal | Negate primary guard signal OK_SHUTOFF | yes |
| TC_PM_049 | NOK_SHUTOFF | Positive path for transition SM_P_002 (None -> None) | yes |
| TC_PM_050 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_051 | guard_false_signal | Negate primary guard signal NOK_SHUTOFF | yes |
| TC_PM_052 | RESET_SHUTOFF | Positive path for transition SM_P_003 (None -> None) | yes |
| TC_PM_053 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_054 | guard_false_signal | Negate primary guard signal RESET_SHUTOFF | yes |
| TC_PM_055 | OK_SHUTOFF | Positive path for transition SM_D_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_056 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_057 | guard_false_signal | Negate primary guard signal OK_SHUTOFF | yes |
| TC_PM_058 | NOK_SHUTOFF | Positive path for transition SM_D_002 (NORMAL -> NORMAL) | yes |
| TC_PM_059 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_060 | guard_false_signal | Negate primary guard signal NOK_SHUTOFF | yes |
| TC_PM_061 | RESET_SHUTOFF | Positive path for transition SM_D_003 (NORMAL -> NORMAL) | yes |
| TC_PM_062 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_063 | guard_false_signal | Negate primary guard signal RESET_SHUTOFF | yes |
| TC_PM_064 | evaluate_NOK_SHUTOFF_branch_1 | Verify NOK_SHUTOFF=1 — path branch 1 | yes |
| TC_PM_065 | evaluate_NOK_SHUTOFF_branch_2 | Verify NOK_SHUTOFF=1 — path branch 2 | yes |
| TC_PM_066 | evaluate_NOK_SHUTOFF_branch_3 | Verify NOK_SHUTOFF=1 — path branch 3 | yes |
| TC_PM_067 | evaluate_NOK_SHUTOFF_branch_4 | Verify NOK_SHUTOFF=1 — path branch 4 | yes |
| TC_PM_068 | evaluate_Battery abnormal_branch_1 | Verify Battery abnormal=1 — path branch 1 | yes |
| TC_PM_069 | evaluate_Battery abnormal_branch_2 | Verify Battery abnormal=1 — path branch 2 | yes |
| TC_PM_070 | evaluate_RESET_branch_1 | Verify RESET=1 — path branch 1 | yes |
| TC_PM_071 | evaluate_RESET_branch_2 | Verify RESET=1 — path branch 2 | yes |
| TC_PM_072 | evaluate_RESET_branch_3 | Verify RESET=1 — path branch 3 | yes |
| TC_PM_073 | evaluate_RESET_CONDITION_branch_1 | Verify RESET_CONDITION=1 — path branch 1 | yes |
| TC_PM_074 | evaluate_RESET_CONDITION_branch_2 | Verify RESET_CONDITION=1 — path branch 2 | yes |
| TC_PM_075 | evaluate_RESET_CONDITION_branch_3 | Verify RESET_CONDITION=1 — path branch 3 | yes |
| TC_PM_076 | evaluate_SHUTOFF_DECISION_branch_1_footnote_when | Verify SHUTOFF_DECISION=1 — path branch 1 footnote when | yes |
| TC_PM_077 | evaluate_SHUTOFF_DECISION_branch_1_footnote_otherwise | Verify SHUTOFF_DECISION=1 — path branch 1 footnote otherwise | yes |
| TC_PM_078 | evaluate_SHUTOFF_DECISION_branch_2_footnote_when | Verify SHUTOFF_DECISION=1 — path branch 2 footnote when | yes |
| TC_PM_079 | evaluate_SHUTOFF_DECISION_branch_2_footnote_otherwise | Verify SHUTOFF_DECISION=1 — path branch 2 footnote otherwise | yes |
| TC_PM_080 | evaluate_SHUTOFF_DECISION_branch_1_guard_false | Verify SHUTOFF_DECISION=1 — path branch 1 guard false | yes |
| TC_PM_081 | evaluate_SHUTOFF_DECISION_branch_2_guard_false | Verify SHUTOFF_DECISION=1 — path branch 2 guard false | yes |
| TC_PM_082 | evaluate_OK_SHUTOFF_default | Verify OK_SHUTOFF=1 — path default | yes |
| TC_PM_083 | evaluate_OK_SHUTOFF_default_guard_false | Verify OK_SHUTOFF=1 — path default guard false | yes |
| TC_PM_084 | evaluate_CND_REQ_GROUP_default_footnote_when | Verify CND_REQ_GROUP=1 — path default footnote when | yes |
| TC_PM_085 | evaluate_CND_REQ_GROUP_default_footnote_otherwise | Verify CND_REQ_GROUP=1 — path default footnote otherwise | yes |
| TC_PM_086 | evaluate_CND_REQ_GROUP_default_guard_false | Verify CND_REQ_GROUP=1 — path default guard false | yes |
| TC_PM_087 | evaluate_CND_SAFE_GROUP_default_footnote_when | Verify CND_SAFE_GROUP=1 — path default footnote when | yes |
| TC_PM_088 | evaluate_CND_SAFE_GROUP_default_footnote_otherwise | Verify CND_SAFE_GROUP=1 — path default footnote otherwise | yes |
| TC_PM_089 | evaluate_CND_SAFE_GROUP_default_guard_false | Verify CND_SAFE_GROUP=1 — path default guard false | yes |
| TC_PM_090 | evaluate_SHUTOFF_DECISION_branch_1_footnote_when | Verify SHUTOFF_DECISION=1 — path branch 1 footnote when | yes |
| TC_PM_091 | evaluate_SHUTOFF_DECISION_branch_1_footnote_otherwise | Verify SHUTOFF_DECISION=1 — path branch 1 footnote otherwise | yes |
| TC_PM_092 | evaluate_SHUTOFF_DECISION_branch_2_footnote_when | Verify SHUTOFF_DECISION=1 — path branch 2 footnote when | yes |
| TC_PM_093 | evaluate_SHUTOFF_DECISION_branch_2_footnote_otherwise | Verify SHUTOFF_DECISION=1 — path branch 2 footnote otherwise | yes |
| TC_PM_094 | evaluate_SHUTOFF_DECISION_branch_1_guard_false | Verify SHUTOFF_DECISION=1 — path branch 1 guard false | yes |
| TC_PM_095 | evaluate_SHUTOFF_DECISION_branch_2_guard_false | Verify SHUTOFF_DECISION=1 — path branch 2 guard false | yes |
| TC_PM_096 | evaluate_OK_SHUTOFF_default | Verify OK_SHUTOFF=1 — path default | yes |
| TC_PM_097 | evaluate_OK_SHUTOFF_default_guard_false | Verify OK_SHUTOFF=1 — path default guard false | yes |
| TC_PM_098 | evaluate_CND_REQ_GROUP_default_footnote_when | Verify CND_REQ_GROUP=1 — path default footnote when | yes |
| TC_PM_099 | evaluate_CND_REQ_GROUP_default_footnote_otherwise | Verify CND_REQ_GROUP=1 — path default footnote otherwise | yes |
| TC_PM_100 | evaluate_CND_REQ_GROUP_default_guard_false | Verify CND_REQ_GROUP=1 — path default guard false | yes |
| TC_PM_101 | evaluate_CND_SAFE_GROUP_default_footnote_when | Verify CND_SAFE_GROUP=1 — path default footnote when | yes |
| TC_PM_102 | evaluate_CND_SAFE_GROUP_default_footnote_otherwise | Verify CND_SAFE_GROUP=1 — path default footnote otherwise | yes |
| TC_PM_103 | evaluate_CND_SAFE_GROUP_default_guard_false | Verify CND_SAFE_GROUP=1 — path default guard false | yes |
| TC_001 | Evaluate permission | Spec reference TC_001: E=true, A=true, B=true, C=true, D=false | yes |
| TC_002 | Evaluate permission | Spec reference TC_002: E=true, A=true, B=true, C=false, D=true | yes |
| TC_003 | Evaluate permission | Spec reference TC_003: E=true, A=true, B=true, C=false, D=false | yes |
| TC_004 | Evaluate permission | Spec reference TC_004: E=false, A=true, B=true, C=true, D=false | yes |
| TC_PM_108 | negative_not_branch | Verify behavior when NOT NOK_SHUTOFF (negative guard for SHUTOFF_DECISION) | yes |
| TC_PM_109 | negative_not_branch | Verify behavior when NOT SAFETY_LOCKED (negative guard for CND_SAFE_GROUP) | yes |
| TC_PM_110 | negative_not_branch | Verify behavior when NOT NOK_SHUTOFF (negative guard for SHUTOFF_DECISION) | yes |
| TC_PM_111 | negative_not_branch | Verify behavior when NOT SAFETY_LOCKED (negative guard for CND_SAFE_GROUP) | yes |

### TC_PM_001
- **Operation:** `{'given': [{'note': 'PWR_REQ_VALID'}, {'timing': 'NOT NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram: OFF→ACCESSORY'}], 'when': [{'timing': 'NOT NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram: OFF→ACCESSORY'}]}`
- **Expectation:** `[{'signal': 'IGN_STS', 'value': '1', 'operator': '=='}, {'description': 'System state = ACCESSORY'}, {'signal': 'PWR_STATE', 'value': '1; RELAY_MAIN=ON'}]`

### TC_PM_002
- **Operation:** `{'given': [{'note': 'PWR_REQ_VALID'}, {'timing': 'NOT NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram: OFF→ACCESSORY'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_003
- **Operation:** `{'given': [{'signal': 'IGN_STS', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_004
- **Operation:** `{'given': [{'note': 'PWR_REQ_VALID'}, {'signal': 'GEAR_POS', 'value': 'P', 'operator': '=='}, {'timing': 'BATT_OK=1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1 | Diagram: ACCESSORY→RUN'}], 'when': [{'timing': 'BATT_OK=1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1 | Diagram: ACCESSORY→RUN'}]}`
- **Expectation:** `[{'description': 'System state = RUN'}, {'signal': 'PWR_STATE', 'value': '2; RELAY_MAIN=ON'}]`

### TC_PM_005
- **Operation:** `{'given': [{'note': 'PWR_REQ_VALID'}, {'signal': 'GEAR_POS', 'value': 'P', 'operator': '=='}, {'timing': 'BATT_OK=1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1 | Diagram: ACCESSORY→RUN'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_006
- **Operation:** `{'given': [{'signal': 'GEAR_POS', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_007
- **Operation:** `{'given': [{'note': 'SYS_SHUTOFF'}, {'timing': 'NOT NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P; VEH_SPD=0 | Diagram: RUN→SHUT_OFF'}], 'when': [{'timing': 'NOT NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P; VEH_SPD=0 | Diagram: RUN→SHUT_OFF'}]}`
- **Expectation:** `[{'description': 'System state = SHUT_OFF'}, {'signal': 'PWR_STATE', 'value': '3; RELAY_MAIN=OFF'}]`

### TC_PM_008
- **Operation:** `{'given': [{'note': 'SYS_SHUTOFF'}, {'timing': 'NOT NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P; VEH_SPD=0 | Diagram: RUN→SHUT_OFF'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_009
- **Operation:** `{'given': [{'timing': 'RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF'}], 'when': [{'timing': 'RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF'}]}`
- **Expectation:** `[{'description': 'System state = OFF'}, {'signal': 'PWR_STATE', 'value': '0; WAKE_REQ=0'}]`

### TC_PM_010
- **Operation:** `{'given': [{'timing': 'RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_011
- **Operation:** `{'given': [{'timing': 'T_FAIL_TIMEOUT elapsed'}, {'timing': 'DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout'}, {'note': 'diagnostic | Diagram: Any→OFF fallback'}], 'when': [{'timing': 'T_FAIL_TIMEOUT elapsed'}, {'timing': 'DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout'}]}`
- **Expectation:** `[{'description': 'System state = OFF'}, {'signal': 'PWR_STATE', 'value': '0; DIAG_FLAG=1'}]`

### TC_PM_012
- **Operation:** `{'given': [{'timing': 'T_FAIL_TIMEOUT elapsed'}, {'timing': 'DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout'}, {'note': 'diagnostic | Diagram: Any→OFF fallback'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_013
- **Operation:** `{'given': [{'timing': 'TC_PM_003 | Power Mode Control | Condition B false | Verify shutoff is not triggered when vehicle is not stopped | Given Mode_cmd=1, IGN_SW=0, VehicleSpeed>0, Battery_OK=1; When T_shutdown>=100ms | Mode_STS shall not become 0 due to TR_PM_001 | Negative path'}], 'when': [{'timing': 'TC_PM_003 | Power Mode Control | Condition B false | Verify shutoff is not triggered when vehicle is not stopped | Given Mode_cmd=1, IGN_SW=0, VehicleSpeed>0, Battery_OK=1; When T_shutdown>=100ms | Mode_STS shall not become 0 due to TR_PM_001 | Negative path'}]}`
- **Expectation:** `[{'description': 'System state = MODE_STS SHALL NOT BECOME 0 DUE TO TR_PM_001'}]`

### TC_PM_014
- **Operation:** `{'given': [{'timing': 'TC_PM_003 | Power Mode Control | Condition B false | Verify shutoff is not triggered when vehicle is not stopped | Given Mode_cmd=1, IGN_SW=0, VehicleSpeed>0, Battery_OK=1; When T_shutdown>=100ms | Mode_STS shall not become 0 due to TR_PM_001 | Negative path'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_015
- **Operation:** `{'given': [{'timing': 'Previous State = NORMAL; Next State = SHUT_OFF'}], 'when': [{'timing': 'Previous State = NORMAL; Next State = SHUT_OFF'}]}`
- **Expectation:** `[{'description': 'System state = SHUT_OFF'}, {'description': 'OFF_REQUEST'}]`

### TC_PM_016
- **Operation:** `{'given': [{'timing': 'Previous State = NORMAL; Next State = SHUT_OFF'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_017
- **Operation:** `{'given': [{'note': 'Condition_C OR Condition_D'}], 'when': []}`
- **Expectation:** `[{'signal': 'SHUT_OFF_PERMISSION', 'value': 'Condition_E', 'operator': '=='}]`

### TC_PM_018
- **Operation:** `{'given': [{'note': 'Condition_C OR Condition_D'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_019
- **Operation:** `{'given': [{'signal': 'SHUT_OFF_PERMISSION', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_020
- **Operation:** `{'given': [{'signal': 'RESET_CONDITION', 'value': 'Condition_R1', 'operator': '=='}], 'when': []}`
- **Expectation:** `[]`

### TC_PM_021
- **Operation:** `{'given': [{'signal': 'RESET_CONDITION', 'value': 'Condition_R1', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_022
- **Operation:** `{'given': [{'signal': 'RESET_CONDITION', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_023
- **Operation:** `{'given': [{'note': 'Condition_E / Request input active for T_CONFIRM'}, {'signal': 'Condition_A / Vehicle condition', 'value': 'stationary', 'operator': '=='}, {'signal': 'Condition_B / Processing state', 'value': 'IDLE', 'operator': '=='}, {'timing': 'Condition_C / Communication status = NORMAL OR Condition_D / Backup request status = ACTIVE'}], 'when': [{'timing': 'Condition_C / Communication status = NORMAL OR Condition_D / Backup request status = ACTIVE'}]}`
- **Expectation:** `[{'description': 'System state = SHUT_OFF'}]`

### TC_PM_024
- **Operation:** `{'given': [{'note': 'Condition_E / Request input active for T_CONFIRM'}, {'signal': 'Condition_A / Vehicle condition', 'value': 'stationary', 'operator': '=='}, {'signal': 'Condition_B / Processing state', 'value': 'IDLE', 'operator': '=='}, {'timing': 'Condition_C / Communication status = NORMAL OR Condition_D / Backup request status = ACTIVE'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_025
- **Operation:** `{'given': [{'signal': 'Condition_A / Vehicle condition', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_026
- **Operation:** `{'given': [{'note': 'NORMAL → SHUT_OFF'}], 'when': []}`
- **Expectation:** `[{'description': 'System state = SHUT_OFF'}]`

### TC_PM_027
- **Operation:** `{'given': [{'note': 'NORMAL → SHUT_OFF'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_028
- **Operation:** `{'given': [{'signal': 'OK_SHUTOFF', 'value': 'TRUE', 'operator': '=='}], 'when': []}`
- **Expectation:** `[]`

### TC_PM_029
- **Operation:** `{'given': [{'signal': 'OK_SHUTOFF', 'value': 'TRUE', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_030
- **Operation:** `{'given': [{'signal': 'OK_SHUTOFF', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`
