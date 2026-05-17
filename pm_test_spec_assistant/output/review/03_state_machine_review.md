# State machine review (candidates)

Source files: /Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_Behavior_Logic_Sample.xlsx, /Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_Condition_Tree_Diagram.png, /Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_StateFlow_Timing_Sample.pdf, /Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_State_Machine_Diagram.png, /Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_System_Spec_Sample.docx, /Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_TestSpec_Reference_Sample.xlsx, /Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_Timing_Chart.png, /Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/pm_controller_sample.cpp, /Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/power_mode_gtest_sample.cpp

- **TR_PM_001** — None (mode: None)
- **ADM1_ACC** — None (mode: None)
- **TR_PM_002** — None (mode: None)
- **ADM1_OFF** — None (mode: None)
- **TR_PM_003** — None (mode: None)
- **TC_PM_001** — None (mode: None)
- **Power Mode Control** — None (mode: None)
- **TC_PM_002** — None (mode: None)
- **TC_PM_003** — None (mode: None)
- **TC_PM_004** — None (mode: None)

## Transitions (raw extraction)
- `TR_001` TR_PM_001 → ADM1_ACC — cond: `Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)`
- `TR_002` TR_PM_002 → ADM1_OFF — cond: `Mode_cmd = 2 AND Battery_OK = 1`
- `TR_003` TR_PM_003 → ADM1_ACC — cond: `Battery_OK = 0 OR T_trans exceeded`
- `TR_004` TC_PM_001 → Power Mode Control — cond: `Verify shutoff when all mandatory conditions are true and Condition_C is true`
- `TR_005` TC_PM_002 → Power Mode Control — cond: `Verify system does not shut off before timing threshold`
- `TR_001` TC_PM_001 → Power Mode Control — cond: `Verify shutoff when all mandatory conditions are satisfied and Condition_C branch is true`
- `TR_002` TC_PM_002 → Power Mode Control — cond: `Verify shutoff when OR branch Condition_D is true`
- `TR_003` TC_PM_003 → Power Mode Control — cond: `Verify no shutoff before shutdown timer threshold`
- `TR_004` TC_PM_004 → Power Mode Control — cond: `Verify no shutoff when vehicle speed is not zero`
