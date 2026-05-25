# Traceability review

## TC_PM_001
- Signals: ['PWR_REQ_VALID', 'IGN_STS']
- Conditions: ['PWR_REQ_VALID AND IGN_STS=1 AND NOT NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram: OFF→ACCESSORY']
- States: {'from': 'OFF', 'to': 'ACCESSORY'}
- Outputs: ['PWR_STATE=1; RELAY_MAIN=ON']
- Confidence: medium | review: True

## TC_PM_004
- Signals: ['PWR_REQ_VALID', 'GEAR_POS']
- Conditions: ['PWR_REQ_VALID AND GEAR_POS=P AND BATT_OK=1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1 | Diagram: ACCESSORY→RUN']
- States: {'from': 'ACCESSORY', 'to': 'RUN'}
- Outputs: ['PWR_STATE=2; RELAY_MAIN=ON']
- Confidence: medium | review: True

## TC_PM_007
- Signals: ['SYS_SHUTOFF']
- Conditions: ['SYS_SHUTOFF AND NOT NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P; VEH_SPD=0 | Diagram: RUN→SHUT_OFF']
- States: {'from': 'RUN', 'to': 'SHUT_OFF'}
- Outputs: ['PWR_STATE=3; RELAY_MAIN=OFF']
- Confidence: medium | review: True

## TC_PM_010
- Signals: []
- Conditions: ['RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF']
- States: {'from': 'SHUT_OFF', 'to': 'OFF'}
- Outputs: ['PWR_STATE=0; WAKE_REQ=0']
- Confidence: medium | review: True

## TC_PM_012
- Signals: []
- Conditions: ['T_FAIL_TIMEOUT elapsed OR DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout or diagnostic | Diagram: Any→OFF fallback']
- States: {'from': 'ANY', 'to': 'OFF'}
- Outputs: ['PWR_STATE=0; DIAG_FLAG=1']
- Confidence: medium | review: True

## TC_PM_014
- Signals: ['PWR_REQ_VALID', 'IGN_STS']
- Conditions: ['PWR_REQ_VALID AND IGN_STS=1 AND NOT NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram: OFF→ACCESSORY']
- States: {'from': 'OFF', 'to': 'ACCESSORY'}
- Outputs: ['PWR_STATE=1; RELAY_MAIN=ON']
- Confidence: medium | review: True

## TC_PM_017
- Signals: ['PWR_REQ_VALID', 'GEAR_POS']
- Conditions: ['PWR_REQ_VALID AND GEAR_POS=P AND BATT_OK=1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1 | Diagram: ACCESSORY→RUN']
- States: {'from': 'ACCESSORY', 'to': 'RUN'}
- Outputs: ['PWR_STATE=2; RELAY_MAIN=ON']
- Confidence: medium | review: True

## TC_PM_020
- Signals: ['SYS_SHUTOFF']
- Conditions: ['SYS_SHUTOFF AND NOT NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P; VEH_SPD=0 | Diagram: RUN→SHUT_OFF']
- States: {'from': 'RUN', 'to': 'SHUT_OFF'}
- Outputs: ['PWR_STATE=3; RELAY_MAIN=OFF']
- Confidence: medium | review: True

## TC_PM_023
- Signals: []
- Conditions: ['RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF']
- States: {'from': 'SHUT_OFF', 'to': 'OFF'}
- Outputs: ['PWR_STATE=0; WAKE_REQ=0']
- Confidence: medium | review: True

## TC_PM_025
- Signals: []
- Conditions: ['T_FAIL_TIMEOUT elapsed OR DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout or diagnostic | Diagram: Any→OFF fallback']
- States: {'from': 'ANY', 'to': 'OFF'}
- Outputs: ['PWR_STATE=0; DIAG_FLAG=1']
- Confidence: medium | review: True

## TC_PM_027
- Signals: ['PWR_REQ_VALID', 'VEHICLE_SAFE', 'NORMAL_ROUTE', 'BACKUP_ROUTE']
- Conditions: ['(PWR_REQ_VALID AND VEHICLE_SAFE AND (NORMAL_ROUTE OR (BACKUP_ROUTE AND T_SHUT_CONFIRM elapsed)) AND NOT NOK_SHUTOFF)']
- States: {}
- Outputs: ['SYS_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_028
- Signals: ['PWR_REQ_VALID', 'VEHICLE_SAFE', 'NORMAL_ROUTE', 'BACKUP_ROUTE']
- Conditions: ['(PWR_REQ_VALID AND VEHICLE_SAFE AND (NORMAL_ROUTE OR (BACKUP_ROUTE AND T_SHUT_CONFIRM elapsed)) AND NOT NOK_SHUTOFF)']
- States: {}
- Outputs: ['SYS_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_029
- Signals: ['ENGINE_RUNNING']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_030
- Signals: ['GEAR_NOT_PARK']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_031
- Signals: ['DOOR_UNLOCKED', 'VEH_SPD']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_032
- Signals: ['DIAG_BLOCKED']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_033
- Signals: ['ENGINE_RUNNING']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_034
- Signals: ['GEAR_NOT_PARK']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_035
- Signals: ['DOOR_UNLOCKED', 'VEH_SPD']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_036
- Signals: ['DIAG_BLOCKED']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_037
- Signals: ['PWR_REQ_VALID', 'VEHICLE_SAFE', 'NORMAL_ROUTE', 'BACKUP_ROUTE']
- Conditions: ['(PWR_REQ_VALID AND VEHICLE_SAFE AND (NORMAL_ROUTE OR (BACKUP_ROUTE AND T_SHUT_CONFIRM elapsed)) AND NOT NOK_SHUTOFF)']
- States: {}
- Outputs: ['SYS_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_038
- Signals: ['PWR_REQ_VALID', 'VEHICLE_SAFE', 'NORMAL_ROUTE', 'BACKUP_ROUTE']
- Conditions: ['(PWR_REQ_VALID AND VEHICLE_SAFE AND (NORMAL_ROUTE OR (BACKUP_ROUTE AND T_SHUT_CONFIRM elapsed)) AND NOT NOK_SHUTOFF)']
- States: {}
- Outputs: ['SYS_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_039
- Signals: ['ENGINE_RUNNING']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_040
- Signals: ['GEAR_NOT_PARK']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_041
- Signals: ['DOOR_UNLOCKED', 'VEH_SPD']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_042
- Signals: ['DIAG_BLOCKED']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_043
- Signals: ['ENGINE_RUNNING']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_044
- Signals: ['GEAR_NOT_PARK']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_045
- Signals: ['DOOR_UNLOCKED', 'VEH_SPD']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_046
- Signals: ['DIAG_BLOCKED']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True
