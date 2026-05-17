# Condition definitions

| Condition | Definition | Source |
| --- | --- | --- |
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
| `VEHICLE_STOPPED` | Vehicle motion state is zero. | edited_Shutoff_Condition_Spec.docx  row  |
| `DRIVER_SAFE` | Operator override is not active. | edited_Shutoff_Condition_Spec.docx  row  |
| `PROCESS_IDLE` | Processing state is IDLE. | edited_Shutoff_Condition_Spec.docx  row  |
| `PROCESS_PREPARED` | Processing state is PREPARED. | edited_Shutoff_Condition_Spec.docx  row  |
| `SAFETY_LOCKED` | Safety interlock is active. The condition line is written as NOT SAFETY_LOCKED.  | edited_Shutoff_Condition_Spec.docx  row  |
