# Logic blocks (tables + paragraph formulas)

## `SYS_SHUTOFF` (TC2_XL_Test_Pow_SEC_03_01)
- Type: two_column_control | parse: ok

**Expression:**
```
(PWR_REQ_VALID AND VEHICLE_SAFE AND (NORMAL_ROUTE OR (BACKUP_ROUTE AND T_SHUT_CONFIRM elapsed)) AND NOT NOK_SHUTOFF)
```
- Source: GPT_GenLogic.xlsx 

## `NOK_SHUTOFF` (TC2_XL_Test_Pow_SEC_03_02)
- Type: two_column_control | parse: ok

**Expression:**
```
(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)
```
- Source: GPT_GenLogic.xlsx 

## `Shutdown request detected` (TC2_XL_02_State_01_01)
- Type: two_column_control | parse: ok

**Expression:**
```
Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)
```
- Source: PM_Behavior_Logic_Sample.xlsx 

## `ACC request detected` (TC2_XL_02_State_01_02)
- Type: two_column_control | parse: ok

**Expression:**
```
Mode_cmd = 2 AND Battery_OK = 1
```
- Source: PM_Behavior_Logic_Sample.xlsx 

## `Battery abnormal` (TC2_XL_02_State_01_03)
- Type: two_column_control | parse: ok

**Expression:**
```
Battery_OK = 0 OR T_trans exceeded
```
- Source: PM_Behavior_Logic_Sample.xlsx 

## `SHUT_OFF` (WD2_001)
- Type: permission | parse: partial

**Expression:**
```
Condition_E / System request is active for confirmation time AND Condition_A / Vehicle condition is safe for shutoff AND Condition_A / Processing state is ready AND (Condition_C / Communication status is valid OR Condition_D / External fallback request is detected)
```
- Source: Sample_Power_Control_Specification.docx table_2

## `NORMAL → SHUT_OFF` (WD4_001)
- Type: transition | parse: partial

**Expression:**
```
Condition_E / Request input active for T_CONFIRM AND Condition_A / Vehicle condition = stationary AND Condition_B / Processing state = IDLE AND (Condition_C / Communication status = NORMAL OR Condition_D / Backup request status = ACTIVE)
```
- Source: Sample_Power_Control_Specification.docx table_4

## `RESET` (WD6_001)
- Type: reset | parse: partial

**Expression:**
```
(Condition_R1 / System request becomes inactive OR Condition_R1 / Vehicle condition becomes unsafe OR Condition_R3 / Communication invalid timeout is detected)
```
- Source: Sample_Power_Control_Specification.docx table_6

## `SHUT_OFF_PERMISSION` (FORMULA_001)
- Type: permission | parse: partial
- **Canonical paragraph formula**

**Expression:**
```
Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)
```
- Source: Sample_Power_Control_Specification.docx paragraph_formula

## `RESET_CONDITION` (FORMULA_002)
- Type: reset | parse: partial
- **Canonical paragraph formula**

**Expression:**
```
Condition_R1 OR Condition_R2 OR Condition_R3
```
- Source: Sample_Power_Control_Specification.docx paragraph_formula

## `SHUTOFF_DECISION` (TC2_T1_01)
- Type: two_column_control | parse: ok

**Expression:**
```
(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)
```
- Source: Shutoff_Condition_Spec_v2.docx table_1

## `OK_SHUTOFF` (TC2_T2_01)
- Type: two_column_control | parse: ok

**Expression:**
```
(CND_REQ_GROUP = 1 AND CND_SAFE_GROUP = 1 AND (CND_NORMAL_ROUTE = 1 OR CND_BACKUP_ROUTE = 1) AND (CND_BACKUP_TIMER_OK = 2 AND POWER = OFF) AND CND_OUTPUT_READY = 2)
```
- Source: Shutoff_Condition_Spec_v2.docx table_2

## `CND_REQ_GROUP` (TC2_T3_01)
- Type: two_column_control | parse: ok

**Expression:**
```
(REQ_MAIN_OK (*1) AND REQ_SRC_A_VALID (*2) AND REQ_SRC_B_VALID (*3) AND REQ_STABLE (*4))
```
- Source: Shutoff_Condition_Spec_v2.docx table_3

## `CND_SAFE_GROUP` (TC2_T4_01)
- Type: two_column_control | parse: ok

**Expression:**
```
(VEHICLE_STOPPED = 2(*1) AND DRIVER_SAFE (*2) AND PROCESS_IDLE (*3) AND PROCESS_PREPARED (*4) AND NOT SAFETY_LOCKED (*5))
```
- Source: Shutoff_Condition_Spec_v2.docx table_4

## `SHUTOFF_DECISION` (TC2_T1_01)
- Type: two_column_control | parse: ok

**Expression:**
```
(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)
```
- Source: edited_Shutoff_Condition_Spec.docx table_1

## `OK_SHUTOFF` (TC2_T2_01)
- Type: two_column_control | parse: ok

**Expression:**
```
(CND_REQ_GROUP = 1 AND CND_SAFE_GROUP = 1 AND (CND_NORMAL_ROUTE = 1 OR CND_BACKUP_ROUTE = 1) AND (CND_BACKUP_TIMER_OK = 2 AND POWER = OFF) AND CND_OUTPUT_READY = 2)
```
- Source: edited_Shutoff_Condition_Spec.docx table_2

## `CND_REQ_GROUP` (TC2_T3_01)
- Type: two_column_control | parse: ok

**Expression:**
```
(REQ_MAIN_OK (*1) AND REQ_SRC_A_VALID (*2) AND REQ_SRC_B_VALID (*3) AND REQ_STABLE (*4))
```
- Source: edited_Shutoff_Condition_Spec.docx table_3

## `CND_SAFE_GROUP` (TC2_T4_01)
- Type: two_column_control | parse: ok

**Expression:**
```
(VEHICLE_STOPPED = 2(*1) AND DRIVER_SAFE (*2) AND PROCESS_IDLE (*3) AND PROCESS_PREPARED (*4) AND NOT SAFETY_LOCKED (*5))
```
- Source: edited_Shutoff_Condition_Spec.docx table_4
