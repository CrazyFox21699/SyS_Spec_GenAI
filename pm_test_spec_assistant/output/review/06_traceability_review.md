# Traceability review

## TC_PM_001
- Signals: ['Mode_cmd', 'IGN_SW', 'VehicleSpeed']
- Conditions: ['Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)']
- States: {'from': 'TR_PM_001', 'to': 'ADM1_ACC'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_002
- Signals: ['Mode_cmd', 'Battery_OK']
- Conditions: ['Mode_cmd = 2 AND Battery_OK = 1']
- States: {'from': 'TR_PM_002', 'to': 'ADM1_OFF'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_004
- Signals: ['Battery_OK']
- Conditions: ['Battery_OK = 0 OR T_trans exceeded']
- States: {'from': 'TR_PM_003', 'to': 'ADM1_ACC'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_006
- Signals: ['Mode_cmd', 'IGN_SW', 'VehicleSpeed']
- Conditions: ['Verify shutoff when all mandatory conditions are true and Condition_C is true']
- States: {'from': 'TC_PM_001', 'to': 'Power Mode Control'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_007
- Signals: ['Mode_cmd', 'IGN_SW', 'VehicleSpeed']
- Conditions: ['Verify system does not shut off before timing threshold']
- States: {'from': 'TC_PM_002', 'to': 'Power Mode Control'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_008
- Signals: ['Mode_cmd', 'IGN_SW', 'VehicleSpeed']
- Conditions: ['Verify shutoff when all mandatory conditions are satisfied and Condition_C branch is true']
- States: {'from': 'TC_PM_001', 'to': 'Power Mode Control'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_009
- Signals: ['Mode_cmd', 'IGN_SW', 'VehicleSpeed']
- Conditions: ['Verify shutoff when OR branch Condition_D is true']
- States: {'from': 'TC_PM_002', 'to': 'Power Mode Control'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_010
- Signals: ['Mode_cmd', 'IGN_SW', 'VehicleSpeed']
- Conditions: ['Verify no shutoff before shutdown timer threshold']
- States: {'from': 'TC_PM_003', 'to': 'Power Mode Control'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_011
- Signals: ['Mode_cmd', 'IGN_SW', 'VehicleSpeed']
- Conditions: ['Verify no shutoff when vehicle speed is not zero']
- States: {'from': 'TC_PM_004', 'to': 'Power Mode Control'}
- Outputs: []
- Confidence: medium | review: True
