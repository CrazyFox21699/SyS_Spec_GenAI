# Traceability review

## TC_PM_001
- Signals: []
- Conditions: ['((OK_SHUTOFF AND NOT NOK_SHUTOFF) OR (FORCE_SHUTOFF AND CND_FORCE_ALLOWED))']
- States: {}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_002
- Signals: []
- Conditions: ['((CND_REQ_GROUP AND CND_SAFE_GROUP) OR CND_NORMAL_ROUTE OR CND_BACKUP_ROUTE OR (CND_BACKUP_TIMER_OK AND POWER=OFF) OR CND_OUTPUT_READY)']
- States: {}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_003
- Signals: []
- Conditions: ['((REQ_MAIN_OK (*1) AND REQ_STABLE (*4)) OR (REQ_SRC_A_VALID (*2) OR REQ_SRC_B_VALID (*3)))']
- States: {}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_004
- Signals: []
- Conditions: ['((VEHICLE_STOPPED (*1) AND DRIVER_SAFE (*2) AND NOT SAFETY_LOCKED (*5)) OR (PROCESS_IDLE (*3) OR PROCESS_PREPARED (*4)))']
- States: {}
- Outputs: []
- Confidence: medium | review: True
