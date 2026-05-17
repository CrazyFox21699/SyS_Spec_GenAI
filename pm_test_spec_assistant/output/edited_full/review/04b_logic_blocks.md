# Logic blocks (tables + paragraph formulas)

## `SHUTOFF_DECISION` (TC2_T1_01)
- Type: two_column_control | parse: ok

**Expression:**
```
(OK_SHUTOFF AND NOT NOK_SHUTOFF AND FORCE_SHUTOFF AND CND_FORCE_ALLOWED)
```
- Source: edited_Shutoff_Condition_Spec.docx table_1

## `OK_SHUTOFF` (TC2_T2_01)
- Type: two_column_control | parse: partial

**Expression:**
```
(CND_REQ_GROUP OR CND_SAFE_GROUP OR CND_NORMAL_ROUTE OR CND_BACKUP_ROUTE OR (CND_BACKUP_TIMER_OK AND POWER=OFF) OR CND_OUTPUT_READY)
```
- Source: edited_Shutoff_Condition_Spec.docx table_2

## `CND_REQ_GROUP` (TC2_T3_01)
- Type: two_column_control | parse: ok

**Expression:**
```
(REQ_MAIN_OK (*1) AND REQ_STABLE (*4) AND (REQ_SRC_A_VALID (*2) OR REQ_SRC_B_VALID (*3)))
```
- Source: edited_Shutoff_Condition_Spec.docx table_3

## `CND_SAFE_GROUP` (TC2_T4_01)
- Type: two_column_control | parse: ok

**Expression:**
```
(VEHICLE_STOPPED (*1) AND DRIVER_SAFE (*2) AND NOT SAFETY_LOCKED (*5) AND (PROCESS_IDLE (*3) OR PROCESS_PREPARED (*4)))
```
- Source: edited_Shutoff_Condition_Spec.docx table_4
