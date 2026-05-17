# Test scenario candidates

| ID | Event | Description | Review |
| --- | --- | --- | --- |
| TC_PM_001 | Shutdown request detected | Positive path for transition TR_001 (TR_PM_001 -> ADM1_ACC) | yes |
| TC_PM_002 | ACC request detected | Positive path for transition TR_002 (TR_PM_002 -> ADM1_OFF) | yes |
| TC_PM_003 | guard_false_signal | Negate primary guard signal Mode_cmd | yes |
| TC_PM_004 | Battery abnormal | Positive path for transition TR_003 (TR_PM_003 -> ADM1_ACC) | yes |
| TC_PM_005 | guard_false_signal | Negate primary guard signal Battery_OK | yes |
| TC_PM_006 | Shutdown request active | Positive path for transition TR_004 (TC_PM_001 -> Power Mode Control) | yes |
| TC_PM_007 | Shutdown timing not reached | Positive path for transition TR_005 (TC_PM_002 -> Power Mode Control) | yes |
| TC_PM_008 | Shutdown request active | Positive path for transition TR_001 (TC_PM_001 -> Power Mode Control) | yes |
| TC_PM_009 | Shutdown request active | Positive path for transition TR_002 (TC_PM_002 -> Power Mode Control) | yes |
| TC_PM_010 | Timing boundary | Positive path for transition TR_003 (TC_PM_003 -> Power Mode Control) | yes |
| TC_PM_011 | Mandatory condition false | Positive path for transition TR_004 (TC_PM_004 -> Power Mode Control) | yes |

### TC_PM_001
- **Operation:** `{'given': [{'note': 'Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)', 'parse_status': 'unparsed'}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with ADM1_ACC', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_002
- **Operation:** `{'given': [{'signal': 'Mode_cmd', 'value': '2', 'operator': '=='}, {'signal': 'Battery_OK', 'value': '1', 'operator': '=='}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with ADM1_OFF', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_003
- **Operation:** `{'given': [{'signal': 'Mode_cmd', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_004
- **Operation:** `{'given': [{'signal': 'Battery_OK', 'value': '0', 'operator': '=='}, {'timing': 'T_trans exceeded'}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with ADM1_ACC', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_005
- **Operation:** `{'given': [{'signal': 'Battery_OK', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_006
- **Operation:** `{'given': [{'note': 'Verify shutoff when all mandatory conditions are true'}, {'note': 'Condition_C is true'}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with Power Mode Control', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_007
- **Operation:** `{'given': [{'note': 'Verify system does not shut off before timing threshold'}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with Power Mode Control', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_008
- **Operation:** `{'given': [{'note': 'Verify shutoff when all mandatory conditions are satisfied'}, {'note': 'Condition_C branch is true'}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with Power Mode Control', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_009
- **Operation:** `{'given': [{'note': 'Verify shutoff when'}, {'note': 'branch Condition_D is true'}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with Power Mode Control', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_010
- **Operation:** `{'given': [{'note': 'Verify no shutoff before shutdown timer threshold'}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with Power Mode Control', 'review_note': 'Refine to concrete interface values'}]`

### TC_PM_011
- **Operation:** `{'given': [{'note': 'Verify no shutoff when vehicle speed is not zero'}], 'when': [{'description': 'Satisfy all guards including timing as interpreted'}]}`
- **Expectation:** `[{'description': 'Reach state or output consistent with Power Mode Control', 'review_note': 'Refine to concrete interface values'}]`
