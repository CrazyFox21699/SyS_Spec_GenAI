# Test scenario candidates

| ID | Event | Description | Review |
| --- | --- | --- | --- |
| TC_PM_001 | OK_SHUTOFF | Positive path for transition SM_P_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_002 | guard_false_signal | Negate primary guard signal OK_SHUTOFF | yes |
| TC_PM_003 | NOK_SHUTOFF | Positive path for transition SM_P_002 (NORMAL -> NORMAL) | yes |
| TC_PM_004 | guard_false_signal | Negate primary guard signal NOK_SHUTOFF | yes |
| TC_PM_005 | RESET_SHUTOFF | Positive path for transition SM_P_003 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_006 | guard_false_signal | Negate primary guard signal RESET_SHUTOFF | yes |
| TC_PM_007 | OK_SHUTOFF | Positive path for transition SM_D_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_008 | guard_false_signal | Negate primary guard signal OK_SHUTOFF | yes |
| TC_PM_009 | NOK_SHUTOFF | Positive path for transition SM_D_002 (NORMAL -> NORMAL) | yes |
| TC_PM_010 | guard_false_signal | Negate primary guard signal NOK_SHUTOFF | yes |
| TC_PM_011 | RESET_SHUTOFF | Positive path for transition SM_D_003 (NORMAL -> NORMAL) | yes |
| TC_PM_012 | guard_false_signal | Negate primary guard signal RESET_SHUTOFF | yes |
| TC_PM_013 | OK_SHUTOFF | Positive path for transition SM_D_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_014 | guard_false_signal | Negate primary guard signal OK_SHUTOFF | yes |
| TC_PM_015 | NOK_SHUTOFF | Positive path for transition SM_D_002 (NORMAL -> NORMAL) | yes |
| TC_PM_016 | guard_false_signal | Negate primary guard signal NOK_SHUTOFF | yes |
| TC_PM_017 | RESET_SHUTOFF | Positive path for transition SM_D_003 (NORMAL -> NORMAL) | yes |
| TC_PM_018 | guard_false_signal | Negate primary guard signal RESET_SHUTOFF | yes |
| TC_PM_019 | evaluate_SHUTOFF_DECISION | Verify logic for SHUTOFF_DECISION: (OK_SHUTOFF AND NOT NOK_SHUTOFF AND FORCE_SHUTOFF AND CND_FORCE_ALLOWED) | yes |
| TC_PM_020 | evaluate_OK_SHUTOFF | Verify logic for OK_SHUTOFF: (CND_REQ_GROUP OR CND_SAFE_GROUP OR CND_NORMAL_ROUTE OR CND_BACKUP_ROUTE OR (CND_BACKUP_TIM | yes |
| TC_PM_021 | evaluate_CND_REQ_GROUP | Verify logic for CND_REQ_GROUP: (REQ_MAIN_OK (*1) AND REQ_STABLE (*4) AND (REQ_SRC_A_VALID (*2) OR REQ_SRC_B_VALID (*3)) | yes |
| TC_PM_022 | evaluate_CND_SAFE_GROUP | Verify logic for CND_SAFE_GROUP: (VEHICLE_STOPPED (*1) AND DRIVER_SAFE (*2) AND NOT SAFETY_LOCKED (*5) AND (PROCESS_IDLE | yes |
| TC_PM_023 | negative_not_branch | Verify behavior when NOT NOK_SHUTOFF (negative guard for SHUTOFF_DECISION) | yes |
| TC_PM_024 | negative_not_branch | Verify behavior when NOT SAFETY_LOCKED (*5) (negative guard for CND_SAFE_GROUP) | yes |

### TC_PM_001
- **Operation:** `{'given': [{'signal': 'OK_SHUTOFF', 'value': 'TRUE', 'operator': '=='}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with SHUT_OFF', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_002
- **Operation:** `{'given': [{'signal': 'OK_SHUTOFF', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_003
- **Operation:** `{'given': [{'signal': 'NOK_SHUTOFF', 'value': 'TRUE', 'operator': '=='}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with NORMAL', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_004
- **Operation:** `{'given': [{'signal': 'NOK_SHUTOFF', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_005
- **Operation:** `{'given': [{'signal': 'RESET_SHUTOFF', 'value': 'TRUE', 'operator': '=='}, {'signal': 'SHUTOFF_DECISION', 'value': 'FALSE', 'operator': '=='}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with SHUT_OFF', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_006
- **Operation:** `{'given': [{'signal': 'RESET_SHUTOFF', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_007
- **Operation:** `{'given': [{'signal': 'OK_SHUTOFF', 'value': 'TRUE', 'operator': '=='}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with SHUT_OFF', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_008
- **Operation:** `{'given': [{'signal': 'OK_SHUTOFF', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_009
- **Operation:** `{'given': [{'signal': 'NOK_SHUTOFF', 'value': 'TRUE', 'operator': '=='}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with NORMAL', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_010
- **Operation:** `{'given': [{'signal': 'NOK_SHUTOFF', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_011
- **Operation:** `{'given': [{'signal': 'RESET_SHUTOFF', 'value': 'TRUE', 'operator': '=='}, {'signal': 'SHUTOFF_DECISION', 'value': 'FALSE', 'operator': '=='}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with NORMAL', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_012
- **Operation:** `{'given': [{'signal': 'RESET_SHUTOFF', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_013
- **Operation:** `{'given': [{'signal': 'OK_SHUTOFF', 'value': 'TRUE', 'operator': '=='}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with SHUT_OFF', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_014
- **Operation:** `{'given': [{'signal': 'OK_SHUTOFF', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_015
- **Operation:** `{'given': [{'signal': 'NOK_SHUTOFF', 'value': 'TRUE', 'operator': '=='}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with NORMAL', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_016
- **Operation:** `{'given': [{'signal': 'NOK_SHUTOFF', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_017
- **Operation:** `{'given': [{'signal': 'RESET_SHUTOFF', 'value': 'TRUE', 'operator': '=='}, {'signal': 'SHUTOFF_DECISION', 'value': 'FALSE', 'operator': '=='}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with NORMAL', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_018
- **Operation:** `{'given': [{'signal': 'RESET_SHUTOFF', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_019
- **Operation:** `{'given': [{'note': '(OK_SHUTOFF AND NOT NOK_SHUTOFF AND FORCE_SHUTOFF AND CND_FORCE_ALLOWED)'}], 'when': [{'description': 'Evaluate control judgment'}]}`
- **Expectation:** `[{'description': 'Outcome matches control definition', 'review_note': 'Refine'}]`

### TC_PM_020
- **Operation:** `{'given': [{'note': '(CND_REQ_GROUP OR CND_SAFE_GROUP OR CND_NORMAL_ROUTE OR CND_BACKUP_ROUTE OR (CND_BACKUP_TIMER_OK AND POWER=OFF) OR CND_OUTPUT_READY)'}], 'when': [{'description': 'Evaluate control judgment'}]}`
- **Expectation:** `[{'description': 'Outcome matches control definition', 'review_note': 'Refine'}]`

### TC_PM_021
- **Operation:** `{'given': [{'note': '(REQ_MAIN_OK (*1) AND REQ_STABLE (*4) AND (REQ_SRC_A_VALID (*2) OR REQ_SRC_B_VALID (*3)))'}], 'when': [{'description': 'Evaluate control judgment'}]}`
- **Expectation:** `[{'description': 'Outcome matches control definition', 'review_note': 'Refine'}]`

### TC_PM_022
- **Operation:** `{'given': [{'note': '(VEHICLE_STOPPED (*1) AND DRIVER_SAFE (*2) AND NOT SAFETY_LOCKED (*5) AND (PROCESS_IDLE (*3) OR PROCESS_PREPARED (*4)))'}], 'when': [{'description': 'Evaluate control judgment'}]}`
- **Expectation:** `[{'description': 'Outcome matches control definition', 'review_note': 'Refine'}]`

### TC_PM_023
- **Operation:** `{'given': [{'note': 'NOT NOK_SHUTOFF active / guard false'}], 'when': [{'description': 'Evaluate while NOT condition holds'}]}`
- **Expectation:** `[{'description': 'Must not satisfy SHUTOFF_DECISION permission', 'review_note': 'Refine'}]`

### TC_PM_024
- **Operation:** `{'given': [{'note': 'NOT SAFETY_LOCKED (*5) active / guard false'}], 'when': [{'description': 'Evaluate while NOT condition holds'}]}`
- **Expectation:** `[{'description': 'Must not satisfy CND_SAFE_GROUP permission', 'review_note': 'Refine'}]`
