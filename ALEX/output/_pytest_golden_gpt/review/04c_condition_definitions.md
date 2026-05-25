# Condition definitions

| Condition | Definition | Source |
| --- | --- | --- |
| `SYS_SHUTOFF` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 23 |
| `PWR_REQ_VALID` | Refer to lower condition group | GPT_GenLogic.xlsx  row 24 |
| `VEHICLE_SAFE` | Refer to lower condition group | GPT_GenLogic.xlsx  row 25 |
| `SYS_SHUTOFF` | Composite condition group (OR) | GPT_GenLogic.xlsx  row 26 |
| `NORMAL_ROUTE` | Normal route condition | GPT_GenLogic.xlsx  row 27 |
| `SYS_SHUTOFF` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 28 |
| `BACKUP_ROUTE` | Backup path valid | GPT_GenLogic.xlsx  row 29 |
| `T_SHUT_CONFIRM elapsed` | Timer condition | GPT_GenLogic.xlsx  row 30 |
| `NOT NOK_SHUTOFF` | Negative blocking condition | GPT_GenLogic.xlsx  row 31 |
| `NOK_SHUTOFF` | Composite condition group (OR) | GPT_GenLogic.xlsx  row 32 |
| `ENGINE_RUNNING` | Engine/process still running | GPT_GenLogic.xlsx  row 33 |
| `GEAR_NOT_PARK` | Gear position is not P | GPT_GenLogic.xlsx  row 34 |
| `NOK_SHUTOFF` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 35 |
| `DOOR_UNLOCKED` | Door lock not satisfied | GPT_GenLogic.xlsx  row 36 |
| `VEH_SPD > 0` | Vehicle speed is non-zero | GPT_GenLogic.xlsx  row 37 |
| `DIAG_BLOCKED` | Diagnostic prohibits transition | GPT_GenLogic.xlsx  row 38 |
| `PWR_REQ_VALID` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 43 |
| `PWR_REQ = 1` | Power request command is active | GPT_GenLogic.xlsx  row 44 |
| `T_REQ_STABLE elapsed` | Request remains active for stable time | GPT_GenLogic.xlsx  row 45 |
| `VEHICLE_SAFE` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 46 |
| `IGN_STS = 0` | Ignition is OFF | GPT_GenLogic.xlsx  row 47 |
| `GEAR_POS = P` | Transmission is Park | GPT_GenLogic.xlsx  row 48 |
| `VEH_SPD = 0` | Vehicle speed is zero | GPT_GenLogic.xlsx  row 49 |
| `NORMAL_ROUTE` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 50 |
| `BATT_OK = 1` | Battery condition normal | GPT_GenLogic.xlsx  row 51 |
| `RELAY_MAIN feedback = OFF` | Main relay is confirmed off | GPT_GenLogic.xlsx  row 52 |
| `BACKUP_ROUTE` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 53 |
| `DOOR_LOCK = 1` | Door is locked | GPT_GenLogic.xlsx  row 54 |
| `WAKE_REQ = 0` | Wake request inactive | GPT_GenLogic.xlsx  row 55 |
| `ENG_STS = RUN` | Running state prohibits shutoff | GPT_GenLogic.xlsx  row 56 |
| `GEAR_POS <> P` | Gear is not Park | GPT_GenLogic.xlsx  row 57 |
| `DOOR_LOCK = 0` | Door is unlocked | GPT_GenLogic.xlsx  row 58 |
| `DIAG_FLAG = 1 for T_DIAG_FILTER` | Diagnostic is set for filter time | GPT_GenLogic.xlsx  row 59 |
| `Constant` | Description | GPT_GenLogic.xlsx  row 9 |
| `T_REQ_STABLE` | Request stable confirmation time | GPT_GenLogic.xlsx  row 10 |
| `T_ACC_CONFIRM` | ACC transition confirmation time | GPT_GenLogic.xlsx  row 11 |
| `T_RUN_CONFIRM` | RUN transition confirmation time | GPT_GenLogic.xlsx  row 12 |
| `T_SHUT_CONFIRM` | Shutoff confirmation time | GPT_GenLogic.xlsx  row 13 |
| `T_FAIL_TIMEOUT` | Transition failure timeout | GPT_GenLogic.xlsx  row 14 |
| `T_WAKE_HOLD` | Wake request hold time | GPT_GenLogic.xlsx  row 15 |
| `T_DIAG_FILTER` | Diagnostic filter time | GPT_GenLogic.xlsx  row 16 |
| `Condition Group` | Condition | GPT_GenLogic.xlsx  row 42 |
| `PWR_REQ_VALID` | AND | GPT_GenLogic.xlsx  row 43 |
| `PWR_REQ_VALID` | PWR_REQ = 1 | GPT_GenLogic.xlsx  row 44 |
| `PWR_REQ_VALID` | T_REQ_STABLE elapsed | GPT_GenLogic.xlsx  row 45 |
| `VEHICLE_SAFE` | AND | GPT_GenLogic.xlsx  row 46 |
| `VEHICLE_SAFE` | IGN_STS = 0 | GPT_GenLogic.xlsx  row 47 |
| `VEHICLE_SAFE` | GEAR_POS = P | GPT_GenLogic.xlsx  row 48 |
| `VEHICLE_SAFE` | VEH_SPD = 0 | GPT_GenLogic.xlsx  row 49 |
| `NORMAL_ROUTE` | AND | GPT_GenLogic.xlsx  row 50 |
| `NORMAL_ROUTE` | BATT_OK = 1 | GPT_GenLogic.xlsx  row 51 |
| `NORMAL_ROUTE` | RELAY_MAIN feedback = OFF | GPT_GenLogic.xlsx  row 52 |
| `BACKUP_ROUTE` | AND | GPT_GenLogic.xlsx  row 53 |
| `BACKUP_ROUTE` | DOOR_LOCK = 1 | GPT_GenLogic.xlsx  row 54 |
| `BACKUP_ROUTE` | WAKE_REQ = 0 | GPT_GenLogic.xlsx  row 55 |
| `ENGINE_RUNNING` | ENG_STS = RUN | GPT_GenLogic.xlsx  row 56 |
| `GEAR_NOT_PARK` | GEAR_POS <> P | GPT_GenLogic.xlsx  row 57 |
| `DOOR_UNLOCKED` | DOOR_LOCK = 0 | GPT_GenLogic.xlsx  row 58 |
| `DIAG_BLOCKED` | DIAG_FLAG = 1 for T_DIAG_FILTER | GPT_GenLogic.xlsx  row 59 |
| `8. State Transition Interpretation and Expected Output` | 8. State Transition Interpretation and Expected Output | GPT_GenLogic.xlsx  row 62 |
| `Transition ID` | From State | GPT_GenLogic.xlsx  row 63 |
| `TR_OFF_ACC` | OFF | GPT_GenLogic.xlsx  row 64 |
| `TR_ACC_RUN` | ACCESSORY | GPT_GenLogic.xlsx  row 65 |
| `TR_RUN_SHUT` | RUN | GPT_GenLogic.xlsx  row 66 |
| `TR_SHUT_OFF` | SHUT_OFF | GPT_GenLogic.xlsx  row 67 |
| `TR_FAIL_OFF` | ANY | GPT_GenLogic.xlsx  row 68 |
| `9. Alias / Mixed Naming` | 9. Alias / Mixed Naming | GPT_GenLogic.xlsx  row 70 |
| `Alias Name` | Actual Condition | GPT_GenLogic.xlsx  row 71 |
| `request_valid_condition` | PWR_REQ_VALID | GPT_GenLogic.xlsx  row 72 |
| `safe_condition_ok` | VEHICLE_SAFE | GPT_GenLogic.xlsx  row 73 |
| `normal_route_ok` | NORMAL_ROUTE | GPT_GenLogic.xlsx  row 74 |
| `backup_route_ok` | BACKUP_ROUTE | GPT_GenLogic.xlsx  row 75 |
| `ng_shutoff_condition` | NOK_SHUTOFF | GPT_GenLogic.xlsx  row 76 |
| `10. Expected Tool Extraction / Review Focus` |  | GPT_GenLogic.xlsx  row 79 |
| `Item` | Expected Tool Behavior | GPT_GenLogic.xlsx  row 80 |
| `Two-column logic` | Build AST from Control/Condition table, indentation, AND/OR/NOT | GPT_GenLogic.xlsx  row 81 |
| `Timing constants` | Extract numeric values and units from Constants table | GPT_GenLogic.xlsx  row 82 |
| `State transitions` | Link transition table to diagram states | GPT_GenLogic.xlsx  row 83 |
| `Alias mapping` | Resolve alias only when mapping table selected | GPT_GenLogic.xlsx  row 84 |
| `Negative logic` | Preserve NOT NOK_SHUTOFF and do not flatten | GPT_GenLogic.xlsx  row 85 |
| `Condition_E` | Request input remains active for T_CONFIRM | Sample_Power_Control_Specification.docx table_3 row 2 |
| `Condition_A` | Vehicle condition is stationary | Sample_Power_Control_Specification.docx table_3 row 3 |
| `Condition_B` | Internal processing state is IDLE | Sample_Power_Control_Specification.docx table_3 row 4 |
| `Condition_C` | Communication status is NORMAL | Sample_Power_Control_Specification.docx table_3 row 5 |
| `Condition_D` | Backup request status is ACTIVE | Sample_Power_Control_Specification.docx table_3 row 6 |
| `SYS_SHUTOFF` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 23 |
| `PWR_REQ_VALID` | Refer to lower condition group | GPT_GenLogic.xlsx  row 24 |
| `VEHICLE_SAFE` | Refer to lower condition group | GPT_GenLogic.xlsx  row 25 |
| `SYS_SHUTOFF` | Composite condition group (OR) | GPT_GenLogic.xlsx  row 26 |
| `NORMAL_ROUTE` | Normal route condition | GPT_GenLogic.xlsx  row 27 |
| `SYS_SHUTOFF` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 28 |
| `BACKUP_ROUTE` | Backup path valid | GPT_GenLogic.xlsx  row 29 |
| `T_SHUT_CONFIRM elapsed` | Timer condition | GPT_GenLogic.xlsx  row 30 |
| `NOT NOK_SHUTOFF` | Negative blocking condition | GPT_GenLogic.xlsx  row 31 |
| `NOK_SHUTOFF` | Composite condition group (OR) | GPT_GenLogic.xlsx  row 32 |
| `ENGINE_RUNNING` | Engine/process still running | GPT_GenLogic.xlsx  row 33 |
| `GEAR_NOT_PARK` | Gear position is not P | GPT_GenLogic.xlsx  row 34 |
| `NOK_SHUTOFF` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 35 |
| `DOOR_UNLOCKED` | Door lock not satisfied | GPT_GenLogic.xlsx  row 36 |
| `VEH_SPD > 0` | Vehicle speed is non-zero | GPT_GenLogic.xlsx  row 37 |
| `DIAG_BLOCKED` | Diagnostic prohibits transition | GPT_GenLogic.xlsx  row 38 |
| `PWR_REQ_VALID` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 43 |
| `PWR_REQ = 1` | Power request command is active | GPT_GenLogic.xlsx  row 44 |
| `T_REQ_STABLE elapsed` | Request remains active for stable time | GPT_GenLogic.xlsx  row 45 |
| `VEHICLE_SAFE` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 46 |
| `IGN_STS = 0` | Ignition is OFF | GPT_GenLogic.xlsx  row 47 |
| `GEAR_POS = P` | Transmission is Park | GPT_GenLogic.xlsx  row 48 |
| `VEH_SPD = 0` | Vehicle speed is zero | GPT_GenLogic.xlsx  row 49 |
| `NORMAL_ROUTE` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 50 |
| `BATT_OK = 1` | Battery condition normal | GPT_GenLogic.xlsx  row 51 |
| `RELAY_MAIN feedback = OFF` | Main relay is confirmed off | GPT_GenLogic.xlsx  row 52 |
| `BACKUP_ROUTE` | Composite condition group (AND) | GPT_GenLogic.xlsx  row 53 |
| `DOOR_LOCK = 1` | Door is locked | GPT_GenLogic.xlsx  row 54 |
| `WAKE_REQ = 0` | Wake request inactive | GPT_GenLogic.xlsx  row 55 |
| `ENG_STS = RUN` | Running state prohibits shutoff | GPT_GenLogic.xlsx  row 56 |
| `GEAR_POS <> P` | Gear is not Park | GPT_GenLogic.xlsx  row 57 |
| `DOOR_LOCK = 0` | Door is unlocked | GPT_GenLogic.xlsx  row 58 |
| `DIAG_FLAG = 1 for T_DIAG_FILTER` | Diagnostic is set for filter time | GPT_GenLogic.xlsx  row 59 |
| `Constant` | Description | GPT_GenLogic.xlsx  row 9 |
| `T_REQ_STABLE` | Request stable confirmation time | GPT_GenLogic.xlsx  row 10 |
| `T_ACC_CONFIRM` | ACC transition confirmation time | GPT_GenLogic.xlsx  row 11 |
| `T_RUN_CONFIRM` | RUN transition confirmation time | GPT_GenLogic.xlsx  row 12 |
| `T_SHUT_CONFIRM` | Shutoff confirmation time | GPT_GenLogic.xlsx  row 13 |
| `T_FAIL_TIMEOUT` | Transition failure timeout | GPT_GenLogic.xlsx  row 14 |
| `T_WAKE_HOLD` | Wake request hold time | GPT_GenLogic.xlsx  row 15 |
| `T_DIAG_FILTER` | Diagnostic filter time | GPT_GenLogic.xlsx  row 16 |
| `Condition Group` | Condition | GPT_GenLogic.xlsx  row 42 |
| `PWR_REQ_VALID` | AND | GPT_GenLogic.xlsx  row 43 |
| `PWR_REQ_VALID` | PWR_REQ = 1 | GPT_GenLogic.xlsx  row 44 |
| `PWR_REQ_VALID` | T_REQ_STABLE elapsed | GPT_GenLogic.xlsx  row 45 |
| `VEHICLE_SAFE` | AND | GPT_GenLogic.xlsx  row 46 |
| `VEHICLE_SAFE` | IGN_STS = 0 | GPT_GenLogic.xlsx  row 47 |
| `VEHICLE_SAFE` | GEAR_POS = P | GPT_GenLogic.xlsx  row 48 |
| `VEHICLE_SAFE` | VEH_SPD = 0 | GPT_GenLogic.xlsx  row 49 |
| `NORMAL_ROUTE` | AND | GPT_GenLogic.xlsx  row 50 |
| `NORMAL_ROUTE` | BATT_OK = 1 | GPT_GenLogic.xlsx  row 51 |
| `NORMAL_ROUTE` | RELAY_MAIN feedback = OFF | GPT_GenLogic.xlsx  row 52 |
| `BACKUP_ROUTE` | AND | GPT_GenLogic.xlsx  row 53 |
| `BACKUP_ROUTE` | DOOR_LOCK = 1 | GPT_GenLogic.xlsx  row 54 |
| `BACKUP_ROUTE` | WAKE_REQ = 0 | GPT_GenLogic.xlsx  row 55 |
| `ENGINE_RUNNING` | ENG_STS = RUN | GPT_GenLogic.xlsx  row 56 |
| `GEAR_NOT_PARK` | GEAR_POS <> P | GPT_GenLogic.xlsx  row 57 |
| `DOOR_UNLOCKED` | DOOR_LOCK = 0 | GPT_GenLogic.xlsx  row 58 |
| `DIAG_BLOCKED` | DIAG_FLAG = 1 for T_DIAG_FILTER | GPT_GenLogic.xlsx  row 59 |
| `8. State Transition Interpretation and Expected Output` | 8. State Transition Interpretation and Expected Output | GPT_GenLogic.xlsx  row 62 |
| `Transition ID` | From State | GPT_GenLogic.xlsx  row 63 |
| `TR_OFF_ACC` | OFF | GPT_GenLogic.xlsx  row 64 |
| `TR_ACC_RUN` | ACCESSORY | GPT_GenLogic.xlsx  row 65 |
| `TR_RUN_SHUT` | RUN | GPT_GenLogic.xlsx  row 66 |
| `TR_SHUT_OFF` | SHUT_OFF | GPT_GenLogic.xlsx  row 67 |
| `TR_FAIL_OFF` | ANY | GPT_GenLogic.xlsx  row 68 |
| `9. Alias / Mixed Naming` | 9. Alias / Mixed Naming | GPT_GenLogic.xlsx  row 70 |
| `Alias Name` | Actual Condition | GPT_GenLogic.xlsx  row 71 |
| `request_valid_condition` | PWR_REQ_VALID | GPT_GenLogic.xlsx  row 72 |
| `safe_condition_ok` | VEHICLE_SAFE | GPT_GenLogic.xlsx  row 73 |
| `normal_route_ok` | NORMAL_ROUTE | GPT_GenLogic.xlsx  row 74 |
| `backup_route_ok` | BACKUP_ROUTE | GPT_GenLogic.xlsx  row 75 |
| `ng_shutoff_condition` | NOK_SHUTOFF | GPT_GenLogic.xlsx  row 76 |
| `10. Expected Tool Extraction / Review Focus` |  | GPT_GenLogic.xlsx  row 79 |
| `Item` | Expected Tool Behavior | GPT_GenLogic.xlsx  row 80 |
| `Two-column logic` | Build AST from Control/Condition table, indentation, AND/OR/NOT | GPT_GenLogic.xlsx  row 81 |
| `Timing constants` | Extract numeric values and units from Constants table | GPT_GenLogic.xlsx  row 82 |
| `State transitions` | Link transition table to diagram states | GPT_GenLogic.xlsx  row 83 |
| `Alias mapping` | Resolve alias only when mapping table selected | GPT_GenLogic.xlsx  row 84 |
| `Negative logic` | Preserve NOT NOK_SHUTOFF and do not flatten | GPT_GenLogic.xlsx  row 85 |
| `Condition_E` | Shutdown command is requested for required duration | PM_Behavior_Logic_Sample.xlsx  row 2 |
| `Condition_A` | Ignition switch is OFF | PM_Behavior_Logic_Sample.xlsx  row 3 |
| `Condition_B` | Vehicle is stopped | PM_Behavior_Logic_Sample.xlsx  row 4 |
| `Condition_C` | Battery status is normal | PM_Behavior_Logic_Sample.xlsx  row 5 |
| `Condition_D` | Door is locked | PM_Behavior_Logic_Sample.xlsx  row 6 |
| `Condition_E` | Request input remains active for T_CONFIRM | Sample_Power_Control_Specification.docx table_3 row 2 |
| `Condition_A` | Vehicle condition is stationary | Sample_Power_Control_Specification.docx table_3 row 3 |
| `Condition_B` | Internal processing state is IDLE | Sample_Power_Control_Specification.docx table_3 row 4 |
| `Condition_C` | Communication status is NORMAL | Sample_Power_Control_Specification.docx table_3 row 5 |
| `Condition_D` | Backup request status is ACTIVE | Sample_Power_Control_Specification.docx table_3 row 6 |
| `T_REQ_STABLE` | Request stable confirmation time | 120 [ms]  5 | Shutoff_Condition_Spec_v2.docx table_6 row 2 |
| `T_BACKUP_TIMER` | Backup route confirmation time | 300 [ms] | Shutoff_Condition_Spec_v2.docx table_6 row 3 |
| `T_HW_WAKEUP` | Hardware standby wakeup time | 450 [ms] | Shutoff_Condition_Spec_v2.docx table_6 row 4 |
| `T_CANCEL` | Operator cancel filter time | 700 [ms]  20 | Shutoff_Condition_Spec_v2.docx table_6 row 5 |
| `T_SENSOR_CONFIRM` | Sensor invalid confirmation time | 232 [ms] | Shutoff_Condition_Spec_v2.docx table_6 row 6 |
| `T_COMM_TIMEOUT` | Communication lost timeout | 123 [ms]  3 | Shutoff_Condition_Spec_v2.docx table_6 row 7 |
| `T_FORCE_WAIT` | Force request waiting time | 50 [ms] | Shutoff_Condition_Spec_v2.docx table_6 row 8 |
| `CND_REQ_GROUP` | Composite condition group (members defined below) | Shutoff_Condition_Spec_v2.docx  row  |
| `REQ_MAIN_OK` | req.main == TRUE | Shutoff_Condition_Spec_v2.docx  row  |
| `REQ_SRC_A_VALID` | source == SRC_A && req.auth == PASS | Shutoff_Condition_Spec_v2.docx  row  |
| `REQ_SRC_B_VALID` | req.source == SRC_B && req.level >= MIN_LEVEL | Shutoff_Condition_Spec_v2.docx  row  |
| `REQ_STABLE` | remains active until timer >= T_REQ_STABLE | Shutoff_Condition_Spec_v2.docx  row  |
| `CND_SAFE_GROUP` | Composite condition group (members defined below) | Shutoff_Condition_Spec_v2.docx  row  |
| `VEHICLE_STOPPED` | 100 to 200km/h | Shutoff_Condition_Spec_v2.docx  row  |
| `DRIVER_SAFE` | 3 to 5 | Shutoff_Condition_Spec_v2.docx  row  |
| `PROCESS_IDLE` | YES | Shutoff_Condition_Spec_v2.docx  row  |
| `PROCESS_PREPARED` | PREPARED. | Shutoff_Condition_Spec_v2.docx  row  |
| `SAFETY_LOCKED` | YES | Shutoff_Condition_Spec_v2.docx  row  |
| `T_REQ_STABLE` | Request stable confirmation time | 120 [ms]  5 | edited_Shutoff_Condition_Spec.docx table_6 row 2 |
| `T_BACKUP_TIMER` | Backup route confirmation time | 300 [ms] | edited_Shutoff_Condition_Spec.docx table_6 row 3 |
| `T_HW_WAKEUP` | Hardware standby wakeup time | 450 [ms] | edited_Shutoff_Condition_Spec.docx table_6 row 4 |
| `T_CANCEL` | Operator cancel filter time | 700 [ms]  20 | edited_Shutoff_Condition_Spec.docx table_6 row 5 |
| `T_SENSOR_CONFIRM` | Sensor invalid confirmation time | 232 [ms] | edited_Shutoff_Condition_Spec.docx table_6 row 6 |
| `T_COMM_TIMEOUT` | Communication lost timeout | 123 [ms]  3 | edited_Shutoff_Condition_Spec.docx table_6 row 7 |
| `T_FORCE_WAIT` | Force request waiting time | 50 [ms] | edited_Shutoff_Condition_Spec.docx table_6 row 8 |
| `CND_REQ_GROUP` | Composite condition group (members defined below) | edited_Shutoff_Condition_Spec.docx  row  |
| `REQ_MAIN_OK` | req.main == TRUE | edited_Shutoff_Condition_Spec.docx  row  |
| `REQ_SRC_A_VALID` | source == SRC_A && req.auth == PASS | edited_Shutoff_Condition_Spec.docx  row  |
| `REQ_SRC_B_VALID` | req.source == SRC_B && req.level >= MIN_LEVEL | edited_Shutoff_Condition_Spec.docx  row  |
| `REQ_STABLE` | remains active until timer >= T_REQ_STABLE | edited_Shutoff_Condition_Spec.docx  row  |
| `CND_SAFE_GROUP` | Composite condition group (members defined below) | edited_Shutoff_Condition_Spec.docx  row  |
| `VEHICLE_STOPPED` | 100 to 200km/h | edited_Shutoff_Condition_Spec.docx  row  |
| `DRIVER_SAFE` | 3 to 5 | edited_Shutoff_Condition_Spec.docx  row  |
| `PROCESS_IDLE` | YES | edited_Shutoff_Condition_Spec.docx  row  |
| `PROCESS_PREPARED` | PREPARED. | edited_Shutoff_Condition_Spec.docx  row  |
| `SAFETY_LOCKED` | YES | edited_Shutoff_Condition_Spec.docx  row  |
| `Mode_cmd` | Customer command for power mode transition; Initial=0; FailSafe=0 | PM_Behavior_Logic_Sample.xlsx  row 2 |
| `IGN_SW` | Condition A source; Initial=0; FailSafe=0 | PM_Behavior_Logic_Sample.xlsx  row 5 |
| `VehicleSpeed` | Condition B source; Initial=0; FailSafe=0 | PM_Behavior_Logic_Sample.xlsx  row 7 |
| `Battery_OK` | Condition C source; Initial=1; FailSafe=0 | PM_Behavior_Logic_Sample.xlsx  row 8 |
| `DoorLock_STS` | Condition D source; Initial=0; FailSafe=0 | PM_Behavior_Logic_Sample.xlsx  row 9 |
| `Mode_STS` | Expected output; Initial=1; FailSafe=0 | PM_Behavior_Logic_Sample.xlsx  row 10 |
| `ACC_Relay` | Expected hardware output; Initial=0; FailSafe=0 | PM_Behavior_Logic_Sample.xlsx  row 11 |
| `TR_PM_001` | FailSafe=If timeout, force ADM1_OFF | PM_Behavior_Logic_Sample.xlsx  row 2 |
| `TR_PM_002` | FailSafe=If Battery_OK=0 stay ADM1_OFF | PM_Behavior_Logic_Sample.xlsx  row 3 |
| `TR_PM_003` | FailSafe=Immediate fallback | PM_Behavior_Logic_Sample.xlsx  row 4 |
| `SAMPLE` | SAMPLE | PM_StateFlow_Timing_Sample.pdf None row None |
| `PDF` | PDF | PM_StateFlow_Timing_Sample.pdf None row None |
| `Power` | Power | PM_StateFlow_Timing_Sample.pdf None row None |
| `Mode` | Mode | PM_StateFlow_Timing_Sample.pdf None row None |
| `State` | State | PM_StateFlow_Timing_Sample.pdf None row None |
| `Flow` | Flow | PM_StateFlow_Timing_Sample.pdf None row None |
| `Condition` | Condition | PM_StateFlow_Timing_Sample.pdf None row None |
| `Tree` | Tree | PM_StateFlow_Timing_Sample.pdf None row None |
| `Timing` | Timing | PM_StateFlow_Timing_Sample.pdf None row None |
| `Chart` | Chart | PM_StateFlow_Timing_Sample.pdf None row None |
| `This` | This | PM_StateFlow_Timing_Sample.pdf None row None |
| `Test` | Test | PM_StateFlow_Timing_Sample.pdf None row None |
| `Spec` | Spec | PM_StateFlow_Timing_Sample.pdf None row None |
| `Assistant` | Assistant | PM_StateFlow_Timing_Sample.pdf None row None |
| `Diagram` | Diagram | PM_StateFlow_Timing_Sample.pdf None row None |
| `Item` | Item | PM_StateFlow_Timing_Sample.pdf None row None |
| `Example` | Example | PM_StateFlow_Timing_Sample.pdf None row None |
| `Content` | Content | PM_StateFlow_Timing_Sample.pdf None row None |
| `Expected` | Expected | PM_StateFlow_Timing_Sample.pdf None row None |
| `Tool` | Tool | PM_StateFlow_Timing_Sample.pdf None row None |
| `Behavior` | Behavior | PM_StateFlow_Timing_Sample.pdf None row None |
| `ADM1_ACC` | ADM1_ACC | PM_StateFlow_Timing_Sample.pdf None row None |
| `TRANS_SHUTDOWN` | TRANS_SHUTDOWN | PM_StateFlow_Timing_Sample.pdf None row None |
| `ADM1_OFF` | ADM1_OFF | PM_StateFlow_Timing_Sample.pdf None row None |
| `Extract` | Extract | PM_StateFlow_Timing_Sample.pdf None row None |
| `Condition_E` | Condition_E | PM_StateFlow_Timing_Sample.pdf None row None |
| `AND` | AND | PM_StateFlow_Timing_Sample.pdf None row None |
| `Condition_A` | Condition_A | PM_StateFlow_Timing_Sample.pdf None row None |
| `Condition_B` | Condition_B | PM_StateFlow_Timing_Sample.pdf None row None |
| `Condition_C` | Condition_C | PM_StateFlow_Timing_Sample.pdf None row None |
| `Condition_D` | Condition_D | PM_StateFlow_Timing_Sample.pdf None row None |
| `Build` | Build | PM_StateFlow_Timing_Sample.pdf None row None |
| `AST` | AST | PM_StateFlow_Timing_Sample.pdf None row None |
| `Normalize` | Normalize | PM_StateFlow_Timing_Sample.pdf None row None |
| `Failure` | Failure | PM_StateFlow_Timing_Sample.pdf None row None |
| `T_trans` | T_trans | PM_StateFlow_Timing_Sample.pdf None row None |
| `Generate` | Generate | PM_StateFlow_Timing_Sample.pdf None row None |
| `Embedded` | Embedded | PM_StateFlow_Timing_Sample.pdf None row None |
| `System` | System | PM_StateFlow_Timing_Sample.pdf None row None |
| `T_shutdown` | T_shutdown | PM_StateFlow_Timing_Sample.pdf None row None |
| `Figure` | Figure | PM_StateFlow_Timing_Sample.pdf None row None |
| `Review` | Review | PM_StateFlow_Timing_Sample.pdf None row None |
| `Machine` | Machine | PM_StateFlow_Timing_Sample.pdf None row None |
