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
- Signals: ['Mode_cmd', 'IGN_SW', 'VehicleSpeed']
- Conditions: ['RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF']
- States: {'from': 'SHUT_OFF', 'to': 'OFF'}
- Outputs: ['PWR_STATE=0; WAKE_REQ=0']
- Confidence: medium | review: True

## TC_PM_012
- Signals: ['Mode_cmd', 'IGN_SW', 'VehicleSpeed']
- Conditions: ['T_FAIL_TIMEOUT elapsed OR DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout or diagnostic | Diagram: Any→OFF fallback']
- States: {'from': 'ANY', 'to': 'OFF'}
- Outputs: ['PWR_STATE=0; DIAG_FLAG=1']
- Confidence: medium | review: True

## TC_PM_014
- Signals: ['Mode_cmd', 'IGN_SW', 'VehicleSpeed']
- Conditions: ['TC_PM_003 | Power Mode Control | Condition B false | Verify shutoff is not triggered when vehicle is not stopped | Given Mode_cmd=1, IGN_SW=0, VehicleSpeed>0, Battery_OK=1; When T_shutdown>=100ms | Mode_STS shall not become 0 due to TR_PM_001 | Negative path']
- States: {'from': 'MODE_STS SHALL NOT BECOME 0 DUE TO TR_PM_001', 'to': 'MODE_STS SHALL NOT BECOME 0 DUE TO TR_PM_001'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_016
- Signals: ['Mode_cmd', 'IGN_SW', 'VehicleSpeed']
- Conditions: ['Previous State = NORMAL; Next State = SHUT_OFF']
- States: {'from': 'NORMAL', 'to': 'SHUT_OFF'}
- Outputs: ['OFF_REQUEST']
- Confidence: medium | review: True

## TC_PM_018
- Signals: ['SHUT_OFF_PERMISSION']
- Conditions: ['SHUT_OFF_PERMISSION = Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)']
- States: {'from': None, 'to': None}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_021
- Signals: ['RESET_CONDITION']
- Conditions: ['RESET_CONDITION = Condition_R1 OR Condition_R2 OR Condition_R3']
- States: {'from': None, 'to': None}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_024
- Signals: ['Condition_A / Vehicle condition', 'Condition_B / Processing state', 'Condition_C / Communication status', 'Condition_D / Backup request status']
- Conditions: ['Condition_E / Request input active for T_CONFIRM AND Condition_A / Vehicle condition = stationary AND Condition_B / Processing state = IDLE AND (Condition_C / Communication status = NORMAL OR Condition_D / Backup request status = ACTIVE)']
- States: {'from': 'NORMAL', 'to': 'SHUT_OFF'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_027
- Signals: ['Mode_cmd', 'IGN_SW', 'VehicleSpeed']
- Conditions: ['NORMAL → SHUT_OFF']
- States: {'from': 'NORMAL', 'to': 'SHUT_OFF'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_029
- Signals: ['OK_SHUTOFF']
- Conditions: ['OK_SHUTOFF = TRUE']
- States: {'from': None, 'to': None}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_032
- Signals: ['NOK_SHUTOFF']
- Conditions: ['NOK_SHUTOFF = TRUE']
- States: {'from': None, 'to': None}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_035
- Signals: ['RESET_SHUTOFF', 'SHUTOFF_DECISION']
- Conditions: ['RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE']
- States: {'from': None, 'to': None}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_038
- Signals: ['OK_SHUTOFF']
- Conditions: ['OK_SHUTOFF = TRUE']
- States: {'from': 'NORMAL', 'to': 'SHUT_OFF'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_041
- Signals: ['NOK_SHUTOFF']
- Conditions: ['NOK_SHUTOFF = TRUE']
- States: {'from': 'NORMAL', 'to': 'NORMAL'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_044
- Signals: ['RESET_SHUTOFF', 'SHUTOFF_DECISION']
- Conditions: ['RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE']
- States: {'from': 'NORMAL', 'to': 'NORMAL'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_047
- Signals: ['OK_SHUTOFF']
- Conditions: ['OK_SHUTOFF = TRUE']
- States: {'from': None, 'to': None}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_050
- Signals: ['NOK_SHUTOFF']
- Conditions: ['NOK_SHUTOFF = TRUE']
- States: {'from': None, 'to': None}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_053
- Signals: ['RESET_SHUTOFF', 'SHUTOFF_DECISION']
- Conditions: ['RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE']
- States: {'from': None, 'to': None}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_056
- Signals: ['OK_SHUTOFF']
- Conditions: ['OK_SHUTOFF = TRUE']
- States: {'from': 'NORMAL', 'to': 'SHUT_OFF'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_059
- Signals: ['NOK_SHUTOFF']
- Conditions: ['NOK_SHUTOFF = TRUE']
- States: {'from': 'NORMAL', 'to': 'NORMAL'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_062
- Signals: ['RESET_SHUTOFF', 'SHUTOFF_DECISION']
- Conditions: ['RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE']
- States: {'from': 'NORMAL', 'to': 'NORMAL'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_065
- Signals: ['PWR_REQ_VALID', 'VEHICLE_SAFE', 'NORMAL_ROUTE', 'BACKUP_ROUTE']
- Conditions: ['(PWR_REQ_VALID AND VEHICLE_SAFE AND (NORMAL_ROUTE OR (BACKUP_ROUTE AND T_SHUT_CONFIRM elapsed)) AND NOT NOK_SHUTOFF)']
- States: {}
- Outputs: ['SYS_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_066
- Signals: ['PWR_REQ_VALID', 'VEHICLE_SAFE', 'NORMAL_ROUTE', 'BACKUP_ROUTE']
- Conditions: ['(PWR_REQ_VALID AND VEHICLE_SAFE AND (NORMAL_ROUTE OR (BACKUP_ROUTE AND T_SHUT_CONFIRM elapsed)) AND NOT NOK_SHUTOFF)']
- States: {}
- Outputs: ['SYS_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_067
- Signals: ['ENGINE_RUNNING']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_068
- Signals: ['GEAR_NOT_PARK']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_069
- Signals: ['DOOR_UNLOCKED', 'VEH_SPD']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_070
- Signals: ['DIAG_BLOCKED']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_071
- Signals: ['ENGINE_RUNNING']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_072
- Signals: ['GEAR_NOT_PARK']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_073
- Signals: ['DOOR_UNLOCKED', 'VEH_SPD']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_074
- Signals: ['DIAG_BLOCKED']
- Conditions: ['(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)']
- States: {}
- Outputs: ['NOK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_075
- Signals: ['Mode_cmd', 'Battery_OK']
- Conditions: ['Mode_cmd = 2 AND Battery_OK = 1']
- States: {}
- Outputs: ['ACC request detected']
- Confidence: medium | review: True

## TC_PM_076
- Signals: ['Mode_cmd', 'Battery_OK']
- Conditions: ['Mode_cmd = 2 AND Battery_OK = 1']
- States: {}
- Outputs: ['ACC request detected']
- Confidence: medium | review: True

## TC_PM_077
- Signals: ['Battery_OK']
- Conditions: ['Battery_OK = 0 OR T_trans exceeded']
- States: {}
- Outputs: ['Battery abnormal']
- Confidence: medium | review: True

## TC_PM_078
- Signals: []
- Conditions: ['Battery_OK = 0 OR T_trans exceeded']
- States: {}
- Outputs: ['Battery abnormal']
- Confidence: medium | review: True

## TC_PM_079
- Signals: ['Battery_OK']
- Conditions: ['Battery_OK = 0 OR T_trans exceeded']
- States: {}
- Outputs: ['Battery abnormal']
- Confidence: medium | review: True

## TC_PM_080
- Signals: ['Condition_A / Vehicle condition', 'Condition_B / Processing state', 'Condition_C / Communication status', 'Condition_D / Backup request status']
- Conditions: ['Condition_E / Request input active for T_CONFIRM AND Condition_A / Vehicle condition = stationary AND Condition_B / Processing state = IDLE AND (Condition_C / Communication status = NORMAL OR Condition_D / Backup request status = ACTIVE)']
- States: {}
- Outputs: ['NORMAL → SHUT_OFF']
- Confidence: medium | review: True

## TC_PM_081
- Signals: ['Condition_A / Vehicle condition', 'Condition_B / Processing state', 'Condition_C / Communication status', 'Condition_D / Backup request status']
- Conditions: ['Condition_E / Request input active for T_CONFIRM AND Condition_A / Vehicle condition = stationary AND Condition_B / Processing state = IDLE AND (Condition_C / Communication status = NORMAL OR Condition_D / Backup request status = ACTIVE)']
- States: {}
- Outputs: ['NORMAL → SHUT_OFF']
- Confidence: medium | review: True

## TC_PM_082
- Signals: []
- Conditions: ['(Condition_R1 / System request becomes inactive OR Condition_R1 / Vehicle condition becomes unsafe OR Condition_R3 / Communication invalid timeout is detected)']
- States: {}
- Outputs: ['RESET']
- Confidence: medium | review: True

## TC_PM_083
- Signals: []
- Conditions: ['(Condition_R1 / System request becomes inactive OR Condition_R1 / Vehicle condition becomes unsafe OR Condition_R3 / Communication invalid timeout is detected)']
- States: {}
- Outputs: ['RESET']
- Confidence: medium | review: True

## TC_PM_084
- Signals: []
- Conditions: ['(Condition_R1 / System request becomes inactive OR Condition_R1 / Vehicle condition becomes unsafe OR Condition_R3 / Communication invalid timeout is detected)']
- States: {}
- Outputs: ['RESET']
- Confidence: medium | review: True

## TC_PM_085
- Signals: []
- Conditions: ['Condition_R1 OR Condition_R2 OR Condition_R3']
- States: {}
- Outputs: ['RESET_CONDITION']
- Confidence: medium | review: True

## TC_PM_086
- Signals: []
- Conditions: ['Condition_R1 OR Condition_R2 OR Condition_R3']
- States: {}
- Outputs: ['RESET_CONDITION']
- Confidence: medium | review: True

## TC_PM_087
- Signals: []
- Conditions: ['Condition_R1 OR Condition_R2 OR Condition_R3']
- States: {}
- Outputs: ['RESET_CONDITION']
- Confidence: medium | review: True

## TC_PM_088
- Signals: ['OK_SHUTOFF']
- Conditions: ['(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_089
- Signals: ['OK_SHUTOFF']
- Conditions: ['(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_090
- Signals: []
- Conditions: ['(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_091
- Signals: []
- Conditions: ['(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_092
- Signals: ['FORCE_SHUTOFF']
- Conditions: ['(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_093
- Signals: ['FORCE_SHUTOFF']
- Conditions: ['(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_094
- Signals: ['CND_FORCE_ALLOWED']
- Conditions: ['(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_095
- Signals: ['CND_FORCE_ALLOWED']
- Conditions: ['(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_096
- Signals: ['OK_SHUTOFF']
- Conditions: ['(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_097
- Signals: ['NOK_SHUTOFF']
- Conditions: ['(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_098
- Signals: ['FORCE_SHUTOFF']
- Conditions: ['(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_099
- Signals: ['CND_FORCE_ALLOWED']
- Conditions: ['(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_100
- Signals: ['CND_REQ_GROUP', 'CND_SAFE_GROUP', 'CND_NORMAL_ROUTE', 'CND_BACKUP_ROUTE', 'CND_BACKUP_TIMER_OK', 'POWER']
- Conditions: ['(CND_REQ_GROUP = 1 AND CND_SAFE_GROUP = 1 AND (CND_NORMAL_ROUTE = 1 OR CND_BACKUP_ROUTE = 1) AND (CND_BACKUP_TIMER_OK = 2 AND POWER = OFF) AND CND_OUTPUT_READY = 2)']
- States: {}
- Outputs: ['OK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_101
- Signals: ['CND_REQ_GROUP', 'CND_SAFE_GROUP', 'CND_NORMAL_ROUTE', 'CND_BACKUP_ROUTE', 'CND_BACKUP_TIMER_OK', 'POWER']
- Conditions: ['(CND_REQ_GROUP = 1 AND CND_SAFE_GROUP = 1 AND (CND_NORMAL_ROUTE = 1 OR CND_BACKUP_ROUTE = 1) AND (CND_BACKUP_TIMER_OK = 2 AND POWER = OFF) AND CND_OUTPUT_READY = 2)']
- States: {}
- Outputs: ['OK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_102
- Signals: []
- Conditions: ['(REQ_MAIN_OK (*1) AND REQ_SRC_A_VALID (*2) AND REQ_SRC_B_VALID (*3) AND REQ_STABLE (*4))']
- States: {}
- Outputs: ['CND_REQ_GROUP']
- Confidence: medium | review: True

## TC_PM_103
- Signals: []
- Conditions: ['(REQ_MAIN_OK (*1) AND REQ_SRC_A_VALID (*2) AND REQ_SRC_B_VALID (*3) AND REQ_STABLE (*4))']
- States: {}
- Outputs: ['CND_REQ_GROUP']
- Confidence: medium | review: True

## TC_PM_104
- Signals: ['REQ_MAIN_OK']
- Conditions: ['(REQ_MAIN_OK (*1) AND REQ_SRC_A_VALID (*2) AND REQ_SRC_B_VALID (*3) AND REQ_STABLE (*4))']
- States: {}
- Outputs: ['CND_REQ_GROUP']
- Confidence: medium | review: True

## TC_PM_105
- Signals: ['VEHICLE_STOPPED']
- Conditions: ['(VEHICLE_STOPPED = 2(*1) AND DRIVER_SAFE (*2) AND PROCESS_IDLE (*3) AND PROCESS_PREPARED (*4) AND NOT SAFETY_LOCKED (*5))']
- States: {}
- Outputs: ['CND_SAFE_GROUP']
- Confidence: medium | review: True

## TC_PM_106
- Signals: ['VEHICLE_STOPPED']
- Conditions: ['(VEHICLE_STOPPED = 2(*1) AND DRIVER_SAFE (*2) AND PROCESS_IDLE (*3) AND PROCESS_PREPARED (*4) AND NOT SAFETY_LOCKED (*5))']
- States: {}
- Outputs: ['CND_SAFE_GROUP']
- Confidence: medium | review: True

## TC_PM_107
- Signals: ['VEHICLE_STOPPED']
- Conditions: ['(VEHICLE_STOPPED = 2(*1) AND DRIVER_SAFE (*2) AND PROCESS_IDLE (*3) AND PROCESS_PREPARED (*4) AND NOT SAFETY_LOCKED (*5))']
- States: {}
- Outputs: ['CND_SAFE_GROUP']
- Confidence: medium | review: True

## TC_PM_108
- Signals: ['HUY']
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_109
- Signals: ['HUY']
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_110
- Signals: ['OK_SHUTOFF']
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_111
- Signals: ['OK_SHUTOFF']
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_112
- Signals: []
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_113
- Signals: []
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_114
- Signals: ['FORCE_SHUTOFF']
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_115
- Signals: ['FORCE_SHUTOFF']
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_116
- Signals: ['CND_FORCE_ALLOWED']
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_117
- Signals: ['CND_FORCE_ALLOWED']
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_118
- Signals: ['HUY']
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_119
- Signals: ['OK_SHUTOFF']
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_120
- Signals: ['NOK_SHUTOFF']
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_121
- Signals: ['FORCE_SHUTOFF']
- Conditions: ['(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)']
- States: {}
- Outputs: ['SHUTOFF_DECISION']
- Confidence: medium | review: True

## TC_PM_122
- Signals: ['CND_REQ_GROUP', 'CND_SAFE_GROUP', 'CND_NORMAL_ROUTE', 'CND_BACKUP_ROUTE', 'CND_BACKUP_TIMER_OK', 'POWER']
- Conditions: ['(CND_REQ_GROUP = 1 AND CND_SAFE_GROUP = 1 AND (CND_NORMAL_ROUTE = 1 OR CND_BACKUP_ROUTE = 1) AND (CND_BACKUP_TIMER_OK = 2 AND POWER = OFF) AND CND_OUTPUT_READY = 2)']
- States: {}
- Outputs: ['OK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_123
- Signals: ['CND_REQ_GROUP', 'CND_SAFE_GROUP', 'CND_NORMAL_ROUTE', 'CND_BACKUP_ROUTE', 'CND_BACKUP_TIMER_OK', 'POWER']
- Conditions: ['(CND_REQ_GROUP = 1 AND CND_SAFE_GROUP = 1 AND (CND_NORMAL_ROUTE = 1 OR CND_BACKUP_ROUTE = 1) AND (CND_BACKUP_TIMER_OK = 2 AND POWER = OFF) AND CND_OUTPUT_READY = 2)']
- States: {}
- Outputs: ['OK_SHUTOFF']
- Confidence: medium | review: True

## TC_PM_124
- Signals: []
- Conditions: ['(REQ_MAIN_OK (*1) AND REQ_SRC_A_VALID (*2) AND REQ_SRC_B_VALID (*3) AND REQ_STABLE (*4))']
- States: {}
- Outputs: ['CND_REQ_GROUP']
- Confidence: medium | review: True

## TC_PM_125
- Signals: []
- Conditions: ['(REQ_MAIN_OK (*1) AND REQ_SRC_A_VALID (*2) AND REQ_SRC_B_VALID (*3) AND REQ_STABLE (*4))']
- States: {}
- Outputs: ['CND_REQ_GROUP']
- Confidence: medium | review: True

## TC_PM_126
- Signals: ['REQ_MAIN_OK']
- Conditions: ['(REQ_MAIN_OK (*1) AND REQ_SRC_A_VALID (*2) AND REQ_SRC_B_VALID (*3) AND REQ_STABLE (*4))']
- States: {}
- Outputs: ['CND_REQ_GROUP']
- Confidence: medium | review: True

## TC_PM_127
- Signals: ['VEHICLE_STOPPED']
- Conditions: ['(VEHICLE_STOPPED = 2(*1) AND DRIVER_SAFE (*2) AND PROCESS_IDLE (*3) AND PROCESS_PREPARED (*4) AND NOT SAFETY_LOCKED (*5))']
- States: {}
- Outputs: ['CND_SAFE_GROUP']
- Confidence: medium | review: True

## TC_PM_128
- Signals: ['VEHICLE_STOPPED']
- Conditions: ['(VEHICLE_STOPPED = 2(*1) AND DRIVER_SAFE (*2) AND PROCESS_IDLE (*3) AND PROCESS_PREPARED (*4) AND NOT SAFETY_LOCKED (*5))']
- States: {}
- Outputs: ['CND_SAFE_GROUP']
- Confidence: medium | review: True

## TC_PM_129
- Signals: ['VEHICLE_STOPPED']
- Conditions: ['(VEHICLE_STOPPED = 2(*1) AND DRIVER_SAFE (*2) AND PROCESS_IDLE (*3) AND PROCESS_PREPARED (*4) AND NOT SAFETY_LOCKED (*5))']
- States: {}
- Outputs: ['CND_SAFE_GROUP']
- Confidence: medium | review: True

## TC_001
- Signals: []
- Conditions: ['E=true, A=true, B=true, C=true, D=false']
- States: {}
- Outputs: ['SHUT_OFF']
- Confidence: high | review: True

## TC_002
- Signals: []
- Conditions: ['E=true, A=true, B=true, C=false, D=true']
- States: {}
- Outputs: ['SHUT_OFF']
- Confidence: high | review: True

## TC_003
- Signals: []
- Conditions: ['E=true, A=true, B=true, C=false, D=false']
- States: {}
- Outputs: ['Not SHUT_OFF']
- Confidence: high | review: True

## TC_004
- Signals: []
- Conditions: ['E=false, A=true, B=true, C=true, D=false']
- States: {}
- Outputs: ['Not SHUT_OFF']
- Confidence: high | review: True

## TC_PM_134
- Signals: []
- Conditions: ['NOT NOK_SHUTOFF']
- States: {}
- Outputs: []
- Confidence: low | review: True

## TC_PM_135
- Signals: []
- Conditions: ['NOT SAFETY_LOCKED']
- States: {}
- Outputs: []
- Confidence: low | review: True

## TC_PM_136
- Signals: []
- Conditions: ['NOT NOK_SHUTOFF']
- States: {}
- Outputs: []
- Confidence: low | review: True

## TC_PM_137
- Signals: []
- Conditions: ['NOT SAFETY_LOCKED']
- States: {}
- Outputs: []
- Confidence: low | review: True
