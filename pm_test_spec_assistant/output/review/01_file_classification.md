# File classification

| File | Role | Confidence | User confirm? | Reasons |
| --- | --- | --- | --- | --- |
| `/Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_Behavior_Logic_Sample.xlsx` | behavior_logic | high | no | Behavior keyword match: state<br>Behavior keyword match: transition<br>Behavior keyword match: condition<br>Behavior keyword match: event<br>Behavior keyword match: output<br>Behavior keyword match: next state |
| `/Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_Condition_Tree_Diagram.png` | diagram | high | no | Image extension |
| `/Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_StateFlow_Timing_Sample.pdf` | behavior_logic | medium | no | PDF may be diagram or spec<br>State-like pattern: ADM\d+_[A-Z0-9_]+ |
| `/Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_State_Machine_Diagram.png` | diagram | high | no | Image extension |
| `/Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_System_Spec_Sample.docx` | system_spec | high | no | Signal/interface keyword in Word: signal<br>Signal/interface keyword in Word: interface<br>Signal/interface keyword in Word: sender<br>Signal/interface keyword in Word: receiver<br>Signal/interface keyword in Word: initial<br>Signal/interface keyword in Word: fail-safe |
| `/Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_TestSpec_Reference_Sample.xlsx` | behavior_logic | high | no | Behavior keyword match: state<br>Behavior keyword match: transition<br>Behavior keyword match: condition<br>Behavior keyword match: event<br>Behavior keyword match: next state<br>State-like pattern: ADM\d+_[A-Z0-9_]+ |
| `/Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/PM_Timing_Chart.png` | diagram | high | no | Image extension |
| `/Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/pm_controller_sample.cpp` | behavior_logic | low | yes | Source code extension<br>State-like pattern: ADM\d+_[A-Z0-9_]+<br>Conflicting signals between roles |
| `/Users/tranthaonguyen/TruongHuy/TMC/pm_sample_inputs/input/power_mode_gtest_sample.cpp` | code_reference | high | no | Source code extension<br>Contains GoogleTest-style macros<br>State-like pattern: ADM\d+_[A-Z0-9_]+ |

## Notes
- Roles are heuristic in v0.1; confirm especially for `unknown` or low confidence.
