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
