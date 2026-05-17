# Test scenario candidates

| ID | Event | Description | Review |
| --- | --- | --- | --- |
| TC_PM_001 | evaluate_SHUTOFF_DECISION | Verify logic for SHUTOFF_DECISION: ((OK_SHUTOFF AND NOT NOK_SHUTOFF) OR (FORCE_SHUTOFF AND CND_FORCE_ALLOWED)) | yes |
| TC_PM_002 | evaluate_OK_SHUTOFF | Verify logic for OK_SHUTOFF: ((CND_REQ_GROUP AND CND_SAFE_GROUP) OR CND_NORMAL_ROUTE OR CND_BACKUP_ROUTE OR (CND_BACKUP_ | yes |
| TC_PM_003 | evaluate_CND_REQ_GROUP | Verify logic for CND_REQ_GROUP: ((REQ_MAIN_OK (*1) AND REQ_STABLE (*4)) OR (REQ_SRC_A_VALID (*2) OR REQ_SRC_B_VALID (*3) | yes |
| TC_PM_004 | evaluate_CND_SAFE_GROUP | Verify logic for CND_SAFE_GROUP: ((VEHICLE_STOPPED (*1) AND DRIVER_SAFE (*2) AND NOT SAFETY_LOCKED (*5)) OR (PROCESS_IDL | yes |

### TC_PM_001
- **Operation:** `{'given': [{'note': '((OK_SHUTOFF AND NOT NOK_SHUTOFF) OR (FORCE_SHUTOFF AND CND_FORCE_ALLOWED))'}], 'when': [{'description': 'Evaluate control judgment'}]}`
- **Expectation:** `[{'description': 'Outcome matches control definition', 'review_note': 'Refine'}]`

### TC_PM_002
- **Operation:** `{'given': [{'note': '((CND_REQ_GROUP AND CND_SAFE_GROUP) OR CND_NORMAL_ROUTE OR CND_BACKUP_ROUTE OR (CND_BACKUP_TIMER_OK AND POWER=OFF) OR CND_OUTPUT_READY)'}], 'when': [{'description': 'Evaluate control judgment'}]}`
- **Expectation:** `[{'description': 'Outcome matches control definition', 'review_note': 'Refine'}]`

### TC_PM_003
- **Operation:** `{'given': [{'note': '((REQ_MAIN_OK (*1) AND REQ_STABLE (*4)) OR (REQ_SRC_A_VALID (*2) OR REQ_SRC_B_VALID (*3)))'}], 'when': [{'description': 'Evaluate control judgment'}]}`
- **Expectation:** `[{'description': 'Outcome matches control definition', 'review_note': 'Refine'}]`

### TC_PM_004
- **Operation:** `{'given': [{'note': '((VEHICLE_STOPPED (*1) AND DRIVER_SAFE (*2) AND NOT SAFETY_LOCKED (*5)) OR (PROCESS_IDLE (*3) OR PROCESS_PREPARED (*4)))'}], 'when': [{'description': 'Evaluate control judgment'}]}`
- **Expectation:** `[{'description': 'Outcome matches control definition', 'review_note': 'Refine'}]`
