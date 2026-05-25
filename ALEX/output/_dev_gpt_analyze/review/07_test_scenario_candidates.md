# Test scenario candidates

| ID | Event | Description | Review |
| --- | --- | --- | --- |
| TC_PM_001 | Accessory request | Positive path for transition TR_OFF_ACC (OFF -> ACCESSORY) | yes |
| TC_PM_002 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_003 | guard_false_signal | Negate primary guard signal PWR_REQ_VALID | yes |
| TC_PM_004 | Run request | Positive path for transition TR_ACC_RUN (ACCESSORY -> RUN) | yes |
| TC_PM_005 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_006 | guard_false_signal | Negate primary guard signal PWR_REQ_VALID | yes |
| TC_PM_007 | Shutoff request | Positive path for transition TR_RUN_SHUT (RUN -> SHUT_OFF) | yes |
| TC_PM_008 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_009 | guard_false_signal | Negate primary guard signal SYS_SHUTOFF | yes |
| TC_PM_010 | Shutdown complete | Positive path for transition TR_SHUT_OFF (SHUT_OFF -> OFF) | yes |
| TC_PM_011 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_012 | Transition failed | Positive path for transition TR_FAIL_OFF (ANY -> OFF) | yes |
| TC_PM_013 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_014 | Accessory request | Positive path for transition TR_OFF_ACC (OFF -> ACCESSORY) | yes |
| TC_PM_015 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_016 | guard_false_signal | Negate primary guard signal PWR_REQ_VALID | yes |
| TC_PM_017 | Run request | Positive path for transition TR_ACC_RUN (ACCESSORY -> RUN) | yes |
| TC_PM_018 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_019 | guard_false_signal | Negate primary guard signal PWR_REQ_VALID | yes |
| TC_PM_020 | Shutoff request | Positive path for transition TR_RUN_SHUT (RUN -> SHUT_OFF) | yes |
| TC_PM_021 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_022 | guard_false_signal | Negate primary guard signal SYS_SHUTOFF | yes |
| TC_PM_023 | Shutdown complete | Positive path for transition TR_SHUT_OFF (SHUT_OFF -> OFF) | yes |
| TC_PM_024 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_025 | Transition failed | Positive path for transition TR_FAIL_OFF (ANY -> OFF) | yes |
| TC_PM_026 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_027 | evaluate_SYS_SHUTOFF_default | Verify SYS_SHUTOFF=1 — path default | yes |
| TC_PM_028 | evaluate_SYS_SHUTOFF_default_guard_false | Verify SYS_SHUTOFF=1 — path default guard false | yes |
| TC_PM_029 | evaluate_NOK_SHUTOFF_branch_1 | Verify NOK_SHUTOFF=1 — path branch 1 | yes |
| TC_PM_030 | evaluate_NOK_SHUTOFF_branch_2 | Verify NOK_SHUTOFF=1 — path branch 2 | yes |
| TC_PM_031 | evaluate_NOK_SHUTOFF_branch_3 | Verify NOK_SHUTOFF=1 — path branch 3 | yes |
| TC_PM_032 | evaluate_NOK_SHUTOFF_branch_4 | Verify NOK_SHUTOFF=1 — path branch 4 | yes |
| TC_PM_033 | evaluate_NOK_SHUTOFF_branch_1_guard_false | Verify NOK_SHUTOFF=1 — path branch 1 guard false | yes |
| TC_PM_034 | evaluate_NOK_SHUTOFF_branch_2_guard_false | Verify NOK_SHUTOFF=1 — path branch 2 guard false | yes |
| TC_PM_035 | evaluate_NOK_SHUTOFF_branch_3_guard_false | Verify NOK_SHUTOFF=1 — path branch 3 guard false | yes |
| TC_PM_036 | evaluate_NOK_SHUTOFF_branch_4_guard_false | Verify NOK_SHUTOFF=1 — path branch 4 guard false | yes |
| TC_PM_037 | evaluate_SYS_SHUTOFF_default | Verify SYS_SHUTOFF=1 — path default | yes |
| TC_PM_038 | evaluate_SYS_SHUTOFF_default_guard_false | Verify SYS_SHUTOFF=1 — path default guard false | yes |
| TC_PM_039 | evaluate_NOK_SHUTOFF_branch_1 | Verify NOK_SHUTOFF=1 — path branch 1 | yes |
| TC_PM_040 | evaluate_NOK_SHUTOFF_branch_2 | Verify NOK_SHUTOFF=1 — path branch 2 | yes |
| TC_PM_041 | evaluate_NOK_SHUTOFF_branch_3 | Verify NOK_SHUTOFF=1 — path branch 3 | yes |
| TC_PM_042 | evaluate_NOK_SHUTOFF_branch_4 | Verify NOK_SHUTOFF=1 — path branch 4 | yes |
| TC_PM_043 | evaluate_NOK_SHUTOFF_branch_1_guard_false | Verify NOK_SHUTOFF=1 — path branch 1 guard false | yes |
| TC_PM_044 | evaluate_NOK_SHUTOFF_branch_2_guard_false | Verify NOK_SHUTOFF=1 — path branch 2 guard false | yes |
| TC_PM_045 | evaluate_NOK_SHUTOFF_branch_3_guard_false | Verify NOK_SHUTOFF=1 — path branch 3 guard false | yes |
| TC_PM_046 | evaluate_NOK_SHUTOFF_branch_4_guard_false | Verify NOK_SHUTOFF=1 — path branch 4 guard false | yes |

### TC_PM_001
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}], 'when': []}`
- **Expectation:** `[{'signal': 'IGN_STS', 'value': '1', 'operator': '=='}, {'description': 'System state = ACCESSORY'}, {'signal': 'PWR_STATE', 'value': '1; RELAY_MAIN=ON'}]`

### TC_PM_002
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_003
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_004
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}, {'signal': 'GEAR_POS', 'value': 'P', 'operator': '=='}], 'when': []}`
- **Expectation:** `[{'description': 'System state = RUN'}, {'signal': 'PWR_STATE', 'value': '2; RELAY_MAIN=ON'}]`

### TC_PM_005
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}, {'signal': 'GEAR_POS', 'value': 'P', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_006
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_007
- **Operation:** `{'given': [{'signal': 'SYS_SHUTOFF', 'value': '1', 'operator': '=='}], 'when': []}`
- **Expectation:** `[{'description': 'System state = SHUT_OFF'}, {'signal': 'PWR_STATE', 'value': '3; RELAY_MAIN=OFF'}]`

### TC_PM_008
- **Operation:** `{'given': [{'signal': 'SYS_SHUTOFF', 'value': '1', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_009
- **Operation:** `{'given': [{'signal': 'SYS_SHUTOFF', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_010
- **Operation:** `{'given': [{'note': 'RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF', 'parse_status': 'unparsed'}], 'when': []}`
- **Expectation:** `[{'description': 'System state = OFF'}, {'signal': 'PWR_STATE', 'value': '0; WAKE_REQ=0'}]`

### TC_PM_011
- **Operation:** `{'given': [{'note': 'RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF', 'parse_status': 'unparsed'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_012
- **Operation:** `{'given': [{'timing': 'T_FAIL_TIMEOUT elapsed'}, {'timing': 'DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout'}], 'when': [{'timing': 'T_FAIL_TIMEOUT elapsed'}, {'timing': 'DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout'}]}`
- **Expectation:** `[{'description': 'System state = OFF'}, {'signal': 'PWR_STATE', 'value': '0; DIAG_FLAG=1'}]`

### TC_PM_013
- **Operation:** `{'given': [{'timing': 'T_FAIL_TIMEOUT elapsed'}, {'timing': 'DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_014
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}], 'when': []}`
- **Expectation:** `[{'signal': 'IGN_STS', 'value': '1', 'operator': '=='}, {'description': 'System state = ACCESSORY'}, {'signal': 'PWR_STATE', 'value': '1; RELAY_MAIN=ON'}]`

### TC_PM_015
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_016
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_017
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}, {'signal': 'GEAR_POS', 'value': 'P', 'operator': '=='}], 'when': []}`
- **Expectation:** `[{'description': 'System state = RUN'}, {'signal': 'PWR_STATE', 'value': '2; RELAY_MAIN=ON'}]`

### TC_PM_018
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}, {'signal': 'GEAR_POS', 'value': 'P', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_019
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_020
- **Operation:** `{'given': [{'signal': 'SYS_SHUTOFF', 'value': '1', 'operator': '=='}], 'when': []}`
- **Expectation:** `[{'description': 'System state = SHUT_OFF'}, {'signal': 'PWR_STATE', 'value': '3; RELAY_MAIN=OFF'}]`

### TC_PM_021
- **Operation:** `{'given': [{'signal': 'SYS_SHUTOFF', 'value': '1', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_022
- **Operation:** `{'given': [{'signal': 'SYS_SHUTOFF', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_023
- **Operation:** `{'given': [{'note': 'RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF', 'parse_status': 'unparsed'}], 'when': []}`
- **Expectation:** `[{'description': 'System state = OFF'}, {'signal': 'PWR_STATE', 'value': '0; WAKE_REQ=0'}]`

### TC_PM_024
- **Operation:** `{'given': [{'note': 'RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF', 'parse_status': 'unparsed'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_025
- **Operation:** `{'given': [{'timing': 'T_FAIL_TIMEOUT elapsed'}, {'timing': 'DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout'}], 'when': [{'timing': 'T_FAIL_TIMEOUT elapsed'}, {'timing': 'DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout'}]}`
- **Expectation:** `[{'description': 'System state = OFF'}, {'signal': 'PWR_STATE', 'value': '0; DIAG_FLAG=1'}]`

### TC_PM_026
- **Operation:** `{'given': [{'timing': 'T_FAIL_TIMEOUT elapsed'}, {'timing': 'DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_027
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '==', 'negated': False}, {'signal': 'VEHICLE_SAFE', 'value': '1', 'operator': '==', 'negated': False}, {'signal': 'NORMAL_ROUTE', 'value': '1', 'operator': '==', 'negated': False}, {'signal': 'BACKUP_ROUTE', 'value': '1', 'operator': '==', 'negated': False}], 'when': [{'description': 'Evaluate control judgment'}]}`
- **Expectation:** `[{'signal': 'SYS_SHUTOFF', 'value': '1', 'operator': '=='}]`

### TC_PM_028
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '0', 'operator': '!=', 'negated': True}, {'signal': 'VEHICLE_SAFE', 'value': '1', 'operator': '==', 'negated': False}, {'signal': 'NORMAL_ROUTE', 'value': '1', 'operator': '==', 'negated': False}, {'signal': 'BACKUP_ROUTE', 'value': '1', 'operator': '==', 'negated': False}], 'when': [{'description': 'Evaluate control judgment'}]}`
- **Expectation:** `[{'signal': 'SYS_SHUTOFF', 'value': '1', 'operator': '=='}]`

### TC_PM_029
- **Operation:** `{'given': [{'signal': 'ENGINE_RUNNING', 'value': '1', 'operator': '==', 'negated': False}], 'when': [{'description': 'Evaluate control judgment'}]}`
- **Expectation:** `[{'signal': 'NOK_SHUTOFF', 'value': '1', 'operator': '=='}]`

### TC_PM_030
- **Operation:** `{'given': [{'signal': 'GEAR_NOT_PARK', 'value': '1', 'operator': '==', 'negated': False}], 'when': [{'description': 'Evaluate control judgment'}]}`
- **Expectation:** `[{'signal': 'NOK_SHUTOFF', 'value': '1', 'operator': '=='}]`
