# Traceability review

## TC_PM_001
- Signals: ['OK_SHUTOFF']
- Conditions: ['OK_SHUTOFF = TRUE']
- States: {'from': 'NORMAL', 'to': 'SHUT_OFF'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_003
- Signals: ['NOK_SHUTOFF']
- Conditions: ['NOK_SHUTOFF = TRUE']
- States: {'from': 'NORMAL', 'to': 'NORMAL'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_005
- Signals: ['RESET_SHUTOFF', 'SHUTOFF_DECISION']
- Conditions: ['RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE']
- States: {'from': 'NORMAL', 'to': 'SHUT_OFF'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_007
- Signals: ['OK_SHUTOFF']
- Conditions: ['OK_SHUTOFF = TRUE']
- States: {'from': 'NORMAL', 'to': 'SHUT_OFF'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_009
- Signals: ['NOK_SHUTOFF']
- Conditions: ['NOK_SHUTOFF = TRUE']
- States: {'from': 'NORMAL', 'to': 'NORMAL'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_011
- Signals: ['RESET_SHUTOFF', 'SHUTOFF_DECISION']
- Conditions: ['RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE']
- States: {'from': 'NORMAL', 'to': 'NORMAL'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_013
- Signals: ['OK_SHUTOFF']
- Conditions: ['OK_SHUTOFF = TRUE']
- States: {'from': 'NORMAL', 'to': 'SHUT_OFF'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_015
- Signals: ['NOK_SHUTOFF']
- Conditions: ['NOK_SHUTOFF = TRUE']
- States: {'from': 'NORMAL', 'to': 'NORMAL'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_017
- Signals: ['RESET_SHUTOFF', 'SHUTOFF_DECISION']
- Conditions: ['RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE']
- States: {'from': 'NORMAL', 'to': 'NORMAL'}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_019
- Signals: []
- Conditions: ['(OK_SHUTOFF AND NOT NOK_SHUTOFF AND FORCE_SHUTOFF AND CND_FORCE_ALLOWED)']
- States: {}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_020
- Signals: []
- Conditions: ['(CND_REQ_GROUP OR CND_SAFE_GROUP OR CND_NORMAL_ROUTE OR CND_BACKUP_ROUTE OR (CND_BACKUP_TIMER_OK AND POWER=OFF) OR CND_OUTPUT_READY)']
- States: {}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_021
- Signals: []
- Conditions: ['(REQ_MAIN_OK (*1) AND REQ_STABLE (*4) AND (REQ_SRC_A_VALID (*2) OR REQ_SRC_B_VALID (*3)))']
- States: {}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_022
- Signals: []
- Conditions: ['(VEHICLE_STOPPED (*1) AND DRIVER_SAFE (*2) AND NOT SAFETY_LOCKED (*5) AND (PROCESS_IDLE (*3) OR PROCESS_PREPARED (*4)))']
- States: {}
- Outputs: []
- Confidence: medium | review: True

## TC_PM_023
- Signals: []
- Conditions: ['NOT NOK_SHUTOFF']
- States: {}
- Outputs: []
- Confidence: low | review: True

## TC_PM_024
- Signals: []
- Conditions: ['NOT SAFETY_LOCKED (*5)']
- States: {}
- Outputs: []
- Confidence: low | review: True
