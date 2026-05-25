# Test scenario candidates

| ID | Event | Description | Review |
| --- | --- | --- | --- |
| TC_PM_001 | Accessory request | Positive path for transition TR_OFF_ACC (OFF -> ACCESSORY) | yes |
| TC_PM_002 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_003 | guard_false_signal | Negate primary guard signal PWR_REQ_VALID | yes |
| TC_PM_004 | Run request | Positive path for transition TR_ACC_RUN (ACCESSORY -> RUN) | yes |
| TC_PM_005 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_006 | guard_false_signal | Negate primary guard signal PWR_REQ_VALID | yes |
| TC_PM_007 | Shutoff request | Positive path for transition TR_RUN_SHUT (RUN -> SHUT_OFF) | yes |
| TC_PM_008 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_009 | guard_false_signal | Negate primary guard signal SYS_SHUTOFF | yes |
| TC_PM_010 | Shutdown complete | Positive path for transition TR_SHUT_OFF (SHUT_OFF -> OFF) | yes |
| TC_PM_011 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_012 | Transition failed | Positive path for transition TR_FAIL_OFF (ANY -> OFF) | yes |
| TC_PM_013 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_014 | state_transition | Positive path for transition SM_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_015 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_016 | SHUT_OFF_PERMISSION | Positive path for transition SM_P_001 (None -> None) | yes |
| TC_PM_017 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_018 | guard_false_signal | Negate primary guard signal SHUT_OFF_PERMISSION | yes |
| TC_PM_019 | RESET_CONDITION | Positive path for transition SM_P_002 (None -> None) | yes |
| TC_PM_020 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_021 | guard_false_signal | Negate primary guard signal RESET_CONDITION | yes |
| TC_PM_022 | logic_table_transition | Positive path for transition SM_LB_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_023 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_024 | guard_false_signal | Negate primary guard signal Condition_A / Vehicle condition | yes |
| TC_PM_025 | diagram_transition | Positive path for transition SM_D_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_026 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_027 | Accessory request | Positive path for transition TR_OFF_ACC (OFF -> ACCESSORY) | yes |
| TC_PM_028 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_029 | guard_false_signal | Negate primary guard signal PWR_REQ_VALID | yes |
| TC_PM_030 | Run request | Positive path for transition TR_ACC_RUN (ACCESSORY -> RUN) | yes |
| TC_PM_031 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_032 | guard_false_signal | Negate primary guard signal PWR_REQ_VALID | yes |
| TC_PM_033 | Shutoff request | Positive path for transition TR_RUN_SHUT (RUN -> SHUT_OFF) | yes |
| TC_PM_034 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_035 | guard_false_signal | Negate primary guard signal SYS_SHUTOFF | yes |
| TC_PM_036 | Shutdown complete | Positive path for transition TR_SHUT_OFF (SHUT_OFF -> OFF) | yes |
| TC_PM_037 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_038 | Transition failed | Positive path for transition TR_FAIL_OFF (ANY -> OFF) | yes |
| TC_PM_039 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_040 | state_transition | Positive path for transition SM_001 (MODE_STS SHALL NOT BECOME 0 DUE TO TR_PM_001 -> MODE_STS SHALL NOT BECOME 0 DUE TO  | yes |
| TC_PM_041 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_042 | state_transition | Positive path for transition SM_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_043 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_044 | SHUT_OFF_PERMISSION | Positive path for transition SM_P_001 (None -> None) | yes |
| TC_PM_045 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_046 | guard_false_signal | Negate primary guard signal SHUT_OFF_PERMISSION | yes |
| TC_PM_047 | RESET_CONDITION | Positive path for transition SM_P_002 (None -> None) | yes |
| TC_PM_048 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_049 | guard_false_signal | Negate primary guard signal RESET_CONDITION | yes |
| TC_PM_050 | logic_table_transition | Positive path for transition SM_LB_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_051 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_052 | guard_false_signal | Negate primary guard signal Condition_A / Vehicle condition | yes |
| TC_PM_053 | diagram_transition | Positive path for transition SM_D_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_054 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_055 | OK_SHUTOFF | Positive path for transition SM_P_001 (None -> None) | yes |
| TC_PM_056 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_057 | guard_false_signal | Negate primary guard signal OK_SHUTOFF | yes |
| TC_PM_058 | NOK_SHUTOFF | Positive path for transition SM_P_002 (None -> None) | yes |
| TC_PM_059 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_060 | guard_false_signal | Negate primary guard signal NOK_SHUTOFF | yes |
| TC_PM_061 | RESET_SHUTOFF | Positive path for transition SM_P_003 (None -> None) | yes |
| TC_PM_062 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_063 | guard_false_signal | Negate primary guard signal RESET_SHUTOFF | yes |
| TC_PM_064 | OK_SHUTOFF | Positive path for transition SM_D_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_065 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_066 | guard_false_signal | Negate primary guard signal OK_SHUTOFF | yes |
| TC_PM_067 | NOK_SHUTOFF | Positive path for transition SM_D_002 (NORMAL -> NORMAL) | yes |
| TC_PM_068 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_069 | guard_false_signal | Negate primary guard signal NOK_SHUTOFF | yes |
| TC_PM_070 | RESET_SHUTOFF | Positive path for transition SM_D_003 (NORMAL -> NORMAL) | yes |
| TC_PM_071 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_072 | guard_false_signal | Negate primary guard signal RESET_SHUTOFF | yes |
| TC_PM_073 | OK_SHUTOFF | Positive path for transition SM_P_001 (None -> None) | yes |
| TC_PM_074 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_075 | guard_false_signal | Negate primary guard signal OK_SHUTOFF | yes |
| TC_PM_076 | NOK_SHUTOFF | Positive path for transition SM_P_002 (None -> None) | yes |
| TC_PM_077 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_078 | guard_false_signal | Negate primary guard signal NOK_SHUTOFF | yes |
| TC_PM_079 | RESET_SHUTOFF | Positive path for transition SM_P_003 (None -> None) | yes |
| TC_PM_080 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_081 | guard_false_signal | Negate primary guard signal RESET_SHUTOFF | yes |
| TC_PM_082 | OK_SHUTOFF | Positive path for transition SM_D_001 (NORMAL -> SHUT_OFF) | yes |
| TC_PM_083 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_084 | guard_false_signal | Negate primary guard signal OK_SHUTOFF | yes |
| TC_PM_085 | NOK_SHUTOFF | Positive path for transition SM_D_002 (NORMAL -> NORMAL) | yes |
| TC_PM_086 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_087 | guard_false_signal | Negate primary guard signal NOK_SHUTOFF | yes |
| TC_PM_088 | RESET_SHUTOFF | Positive path for transition SM_D_003 (NORMAL -> NORMAL) | yes |
| TC_PM_089 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_090 | guard_false_signal | Negate primary guard signal RESET_SHUTOFF | yes |
| TC_PM_091 | Shutdown request active | Positive path for transition TR_001 (TC_PM_001 -> Power Mode Control) | yes |
| TC_PM_092 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_093 | Shutdown request active | Positive path for transition TR_002 (TC_PM_002 -> Power Mode Control) | yes |
| TC_PM_094 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_095 | Timing boundary | Positive path for transition TR_003 (TC_PM_003 -> Power Mode Control) | yes |
| TC_PM_096 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_097 | Mandatory condition false | Positive path for transition TR_004 (TC_PM_004 -> Power Mode Control) | yes |
| TC_PM_098 | timing_boundary | Timing not yet satisfied (< None ms) while other guards true | yes |
| TC_PM_099 | evaluate_SYS_SHUTOFF_default | Verify SYS_SHUTOFF=1 — path default | yes |
| TC_PM_100 | evaluate_SYS_SHUTOFF_default_guard_false | Verify SYS_SHUTOFF=1 — path default guard false | yes |
| TC_PM_101 | evaluate_NOK_SHUTOFF_branch_1 | Verify NOK_SHUTOFF=1 — path branch 1 | yes |
| TC_PM_102 | evaluate_NOK_SHUTOFF_branch_2 | Verify NOK_SHUTOFF=1 — path branch 2 | yes |
| TC_PM_103 | evaluate_NOK_SHUTOFF_branch_3 | Verify NOK_SHUTOFF=1 — path branch 3 | yes |
| TC_PM_104 | evaluate_NOK_SHUTOFF_branch_4 | Verify NOK_SHUTOFF=1 — path branch 4 | yes |
| TC_PM_105 | evaluate_NOK_SHUTOFF_branch_1_guard_false | Verify NOK_SHUTOFF=1 — path branch 1 guard false | yes |
| TC_PM_106 | evaluate_NOK_SHUTOFF_branch_2_guard_false | Verify NOK_SHUTOFF=1 — path branch 2 guard false | yes |
| TC_PM_107 | evaluate_NOK_SHUTOFF_branch_3_guard_false | Verify NOK_SHUTOFF=1 — path branch 3 guard false | yes |
| TC_PM_108 | evaluate_NOK_SHUTOFF_branch_4_guard_false | Verify NOK_SHUTOFF=1 — path branch 4 guard false | yes |
| TC_PM_109 | evaluate_NORMAL → SHUT_OFF_default | Verify NORMAL → SHUT_OFF=1 — path default | yes |
| TC_PM_110 | evaluate_NORMAL → SHUT_OFF_default_guard_false | Verify NORMAL → SHUT_OFF=1 — path default guard false | yes |
| TC_PM_111 | evaluate_RESET_branch_1 | Verify RESET=1 — path branch 1 | yes |
| TC_PM_112 | evaluate_RESET_branch_2 | Verify RESET=1 — path branch 2 | yes |
| TC_PM_113 | evaluate_RESET_branch_3 | Verify RESET=1 — path branch 3 | yes |
| TC_PM_114 | evaluate_RESET_CONDITION_branch_1 | Verify RESET_CONDITION=1 — path branch 1 | yes |
| TC_PM_115 | evaluate_RESET_CONDITION_branch_2 | Verify RESET_CONDITION=1 — path branch 2 | yes |
| TC_PM_116 | evaluate_RESET_CONDITION_branch_3 | Verify RESET_CONDITION=1 — path branch 3 | yes |
| TC_PM_117 | evaluate_SYS_SHUTOFF_default | Verify SYS_SHUTOFF=1 — path default | yes |
| TC_PM_118 | evaluate_SYS_SHUTOFF_default_guard_false | Verify SYS_SHUTOFF=1 — path default guard false | yes |
| TC_PM_119 | evaluate_NOK_SHUTOFF_branch_1 | Verify NOK_SHUTOFF=1 — path branch 1 | yes |
| TC_PM_120 | evaluate_NOK_SHUTOFF_branch_2 | Verify NOK_SHUTOFF=1 — path branch 2 | yes |
| TC_PM_121 | evaluate_NOK_SHUTOFF_branch_3 | Verify NOK_SHUTOFF=1 — path branch 3 | yes |
| TC_PM_122 | evaluate_NOK_SHUTOFF_branch_4 | Verify NOK_SHUTOFF=1 — path branch 4 | yes |
| TC_PM_123 | evaluate_NOK_SHUTOFF_branch_1_guard_false | Verify NOK_SHUTOFF=1 — path branch 1 guard false | yes |
| TC_PM_124 | evaluate_NOK_SHUTOFF_branch_2_guard_false | Verify NOK_SHUTOFF=1 — path branch 2 guard false | yes |
| TC_PM_125 | evaluate_NOK_SHUTOFF_branch_3_guard_false | Verify NOK_SHUTOFF=1 — path branch 3 guard false | yes |
| TC_PM_126 | evaluate_NOK_SHUTOFF_branch_4_guard_false | Verify NOK_SHUTOFF=1 — path branch 4 guard false | yes |
| TC_PM_127 | evaluate_ACC request detected_default | Verify ACC request detected=1 — path default | yes |
| TC_PM_128 | evaluate_ACC request detected_default_guard_false | Verify ACC request detected=1 — path default guard false | yes |
| TC_PM_129 | evaluate_Battery abnormal_branch_1 | Verify Battery abnormal=1 — path branch 1 | yes |
| TC_PM_130 | evaluate_Battery abnormal_branch_2 | Verify Battery abnormal=1 — path branch 2 | yes |
| TC_PM_131 | evaluate_Battery abnormal_branch_1_guard_false | Verify Battery abnormal=1 — path branch 1 guard false | yes |
| TC_PM_132 | evaluate_NORMAL → SHUT_OFF_default | Verify NORMAL → SHUT_OFF=1 — path default | yes |
| TC_PM_133 | evaluate_NORMAL → SHUT_OFF_default_guard_false | Verify NORMAL → SHUT_OFF=1 — path default guard false | yes |
| TC_PM_134 | evaluate_RESET_branch_1 | Verify RESET=1 — path branch 1 | yes |
| TC_PM_135 | evaluate_RESET_branch_2 | Verify RESET=1 — path branch 2 | yes |
| TC_PM_136 | evaluate_RESET_branch_3 | Verify RESET=1 — path branch 3 | yes |
| TC_PM_137 | evaluate_RESET_CONDITION_branch_1 | Verify RESET_CONDITION=1 — path branch 1 | yes |
| TC_PM_138 | evaluate_RESET_CONDITION_branch_2 | Verify RESET_CONDITION=1 — path branch 2 | yes |
| TC_PM_139 | evaluate_RESET_CONDITION_branch_3 | Verify RESET_CONDITION=1 — path branch 3 | yes |
| TC_PM_140 | evaluate_SHUTOFF_DECISION_branch_1_footnote_when | Verify SHUTOFF_DECISION=1 — path branch 1 footnote when | yes |
| TC_PM_141 | evaluate_SHUTOFF_DECISION_branch_1_footnote_otherwise | Verify SHUTOFF_DECISION=1 — path branch 1 footnote otherwise | yes |
| TC_PM_142 | evaluate_SHUTOFF_DECISION_branch_2_footnote_when | Verify SHUTOFF_DECISION=1 — path branch 2 footnote when | yes |
| TC_PM_143 | evaluate_SHUTOFF_DECISION_branch_2_footnote_otherwise | Verify SHUTOFF_DECISION=1 — path branch 2 footnote otherwise | yes |
| TC_PM_144 | evaluate_SHUTOFF_DECISION_branch_3_footnote_when | Verify SHUTOFF_DECISION=1 — path branch 3 footnote when | yes |
| TC_PM_145 | evaluate_SHUTOFF_DECISION_branch_3_footnote_otherwise | Verify SHUTOFF_DECISION=1 — path branch 3 footnote otherwise | yes |
| TC_PM_146 | evaluate_SHUTOFF_DECISION_branch_4_footnote_when | Verify SHUTOFF_DECISION=1 — path branch 4 footnote when | yes |
| TC_PM_147 | evaluate_SHUTOFF_DECISION_branch_4_footnote_otherwise | Verify SHUTOFF_DECISION=1 — path branch 4 footnote otherwise | yes |
| TC_PM_148 | evaluate_SHUTOFF_DECISION_branch_1_guard_false | Verify SHUTOFF_DECISION=1 — path branch 1 guard false | yes |
| TC_PM_149 | evaluate_SHUTOFF_DECISION_branch_2_guard_false | Verify SHUTOFF_DECISION=1 — path branch 2 guard false | yes |
| TC_PM_150 | evaluate_SHUTOFF_DECISION_branch_3_guard_false | Verify SHUTOFF_DECISION=1 — path branch 3 guard false | yes |
| TC_PM_151 | evaluate_SHUTOFF_DECISION_branch_4_guard_false | Verify SHUTOFF_DECISION=1 — path branch 4 guard false | yes |
| TC_PM_152 | evaluate_OK_SHUTOFF_default | Verify OK_SHUTOFF=1 — path default | yes |
| TC_PM_153 | evaluate_OK_SHUTOFF_default_guard_false | Verify OK_SHUTOFF=1 — path default guard false | yes |
| TC_PM_154 | evaluate_CND_REQ_GROUP_default_footnote_when | Verify CND_REQ_GROUP=1 — path default footnote when | yes |
| TC_PM_155 | evaluate_CND_REQ_GROUP_default_footnote_otherwise | Verify CND_REQ_GROUP=1 — path default footnote otherwise | yes |
| TC_PM_156 | evaluate_CND_REQ_GROUP_default_guard_false | Verify CND_REQ_GROUP=1 — path default guard false | yes |
| TC_PM_157 | evaluate_CND_SAFE_GROUP_default_footnote_when | Verify CND_SAFE_GROUP=1 — path default footnote when | yes |
| TC_PM_158 | evaluate_CND_SAFE_GROUP_default_footnote_otherwise | Verify CND_SAFE_GROUP=1 — path default footnote otherwise | yes |
| TC_PM_159 | evaluate_CND_SAFE_GROUP_default_guard_false | Verify CND_SAFE_GROUP=1 — path default guard false | yes |
| TC_PM_160 | evaluate_SHUTOFF_DECISION_branch_1_footnote_when | Verify SHUTOFF_DECISION=1 — path branch 1 footnote when | yes |
| TC_PM_161 | evaluate_SHUTOFF_DECISION_branch_1_footnote_otherwise | Verify SHUTOFF_DECISION=1 — path branch 1 footnote otherwise | yes |
| TC_PM_162 | evaluate_SHUTOFF_DECISION_branch_2_footnote_when | Verify SHUTOFF_DECISION=1 — path branch 2 footnote when | yes |
| TC_PM_163 | evaluate_SHUTOFF_DECISION_branch_2_footnote_otherwise | Verify SHUTOFF_DECISION=1 — path branch 2 footnote otherwise | yes |
| TC_PM_164 | evaluate_SHUTOFF_DECISION_branch_3_footnote_when | Verify SHUTOFF_DECISION=1 — path branch 3 footnote when | yes |
| TC_PM_165 | evaluate_SHUTOFF_DECISION_branch_3_footnote_otherwise | Verify SHUTOFF_DECISION=1 — path branch 3 footnote otherwise | yes |
| TC_PM_166 | evaluate_SHUTOFF_DECISION_branch_4_footnote_when | Verify SHUTOFF_DECISION=1 — path branch 4 footnote when | yes |
| TC_PM_167 | evaluate_SHUTOFF_DECISION_branch_4_footnote_otherwise | Verify SHUTOFF_DECISION=1 — path branch 4 footnote otherwise | yes |
| TC_PM_168 | evaluate_SHUTOFF_DECISION_branch_5_footnote_when | Verify SHUTOFF_DECISION=1 — path branch 5 footnote when | yes |
| TC_PM_169 | evaluate_SHUTOFF_DECISION_branch_5_footnote_otherwise | Verify SHUTOFF_DECISION=1 — path branch 5 footnote otherwise | yes |
| TC_PM_170 | evaluate_SHUTOFF_DECISION_branch_1_guard_false | Verify SHUTOFF_DECISION=1 — path branch 1 guard false | yes |
| TC_PM_171 | evaluate_SHUTOFF_DECISION_branch_2_guard_false | Verify SHUTOFF_DECISION=1 — path branch 2 guard false | yes |
| TC_PM_172 | evaluate_SHUTOFF_DECISION_branch_3_guard_false | Verify SHUTOFF_DECISION=1 — path branch 3 guard false | yes |
| TC_PM_173 | evaluate_SHUTOFF_DECISION_branch_4_guard_false | Verify SHUTOFF_DECISION=1 — path branch 4 guard false | yes |
| TC_PM_174 | evaluate_OK_SHUTOFF_default | Verify OK_SHUTOFF=1 — path default | yes |
| TC_PM_175 | evaluate_OK_SHUTOFF_default_guard_false | Verify OK_SHUTOFF=1 — path default guard false | yes |
| TC_PM_176 | evaluate_CND_REQ_GROUP_default_footnote_when | Verify CND_REQ_GROUP=1 — path default footnote when | yes |
| TC_PM_177 | evaluate_CND_REQ_GROUP_default_footnote_otherwise | Verify CND_REQ_GROUP=1 — path default footnote otherwise | yes |
| TC_PM_178 | evaluate_CND_REQ_GROUP_default_guard_false | Verify CND_REQ_GROUP=1 — path default guard false | yes |
| TC_PM_179 | evaluate_CND_SAFE_GROUP_default_footnote_when | Verify CND_SAFE_GROUP=1 — path default footnote when | yes |
| TC_PM_180 | evaluate_CND_SAFE_GROUP_default_footnote_otherwise | Verify CND_SAFE_GROUP=1 — path default footnote otherwise | yes |
| TC_PM_181 | evaluate_CND_SAFE_GROUP_default_guard_false | Verify CND_SAFE_GROUP=1 — path default guard false | yes |
| TC_001 | Evaluate permission | Spec reference TC_001: E=true, A=true, B=true, C=true, D=false | yes |
| TC_002 | Evaluate permission | Spec reference TC_002: E=true, A=true, B=true, C=false, D=true | yes |
| TC_003 | Evaluate permission | Spec reference TC_003: E=true, A=true, B=true, C=false, D=false | yes |
| TC_004 | Evaluate permission | Spec reference TC_004: E=false, A=true, B=true, C=true, D=false | yes |
| TC_001 | Evaluate permission | Spec reference TC_001: E=true, A=true, B=true, C=true, D=false | yes |
| TC_002 | Evaluate permission | Spec reference TC_002: E=true, A=true, B=true, C=false, D=true | yes |
| TC_003 | Evaluate permission | Spec reference TC_003: E=true, A=true, B=true, C=false, D=false | yes |
| TC_004 | Evaluate permission | Spec reference TC_004: E=false, A=true, B=true, C=true, D=false | yes |
| TC_PM_190 | negative_not_branch | Verify behavior when NOT NOK_SHUTOFF (negative guard for SHUTOFF_DECISION) | yes |
| TC_PM_191 | negative_not_branch | Verify behavior when NOT SAFETY_LOCKED (negative guard for CND_SAFE_GROUP) | yes |
| TC_PM_192 | negative_not_branch | Verify behavior when NOT NOK_SHUTOFF (negative guard for SHUTOFF_DECISION) | yes |
| TC_PM_193 | negative_not_branch | Verify behavior when NOT SAFETY_LOCKED (negative guard for CND_SAFE_GROUP) | yes |

### TC_PM_001
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}], 'when': []}`
- **Expectation:** `[{'signal': 'IGN_STS', 'value': '1', 'operator': '=='}, {'description': 'System state = ACCESSORY'}, {'signal': 'PWR_STATE', 'value': '1; RELAY_MAIN=ON'}]`

### TC_PM_002
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_003
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_004
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}, {'signal': 'GEAR_POS', 'value': 'P', 'operator': '=='}], 'when': []}`
- **Expectation:** `[{'description': 'System state = RUN'}, {'signal': 'PWR_STATE', 'value': '2; RELAY_MAIN=ON'}]`

### TC_PM_005
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}, {'signal': 'GEAR_POS', 'value': 'P', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_006
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_007
- **Operation:** `{'given': [{'signal': 'SYS_SHUTOFF', 'value': '1', 'operator': '=='}], 'when': []}`
- **Expectation:** `[{'description': 'System state = SHUT_OFF'}, {'signal': 'PWR_STATE', 'value': '3; RELAY_MAIN=OFF'}]`

### TC_PM_008
- **Operation:** `{'given': [{'signal': 'SYS_SHUTOFF', 'value': '1', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_009
- **Operation:** `{'given': [{'signal': 'SYS_SHUTOFF', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_010
- **Operation:** `{'given': [{'note': 'RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF', 'parse_status': 'unparsed'}], 'when': []}`
- **Expectation:** `[{'description': 'System state = OFF'}, {'signal': 'PWR_STATE', 'value': '0; WAKE_REQ=0'}]`

### TC_PM_011
- **Operation:** `{'given': [{'note': 'RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF', 'parse_status': 'unparsed'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_012
- **Operation:** `{'given': [{'timing': 'T_FAIL_TIMEOUT elapsed'}, {'timing': 'DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout'}], 'when': [{'timing': 'T_FAIL_TIMEOUT elapsed'}, {'timing': 'DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout'}]}`
- **Expectation:** `[{'description': 'System state = OFF'}, {'signal': 'PWR_STATE', 'value': '0; DIAG_FLAG=1'}]`

### TC_PM_013
- **Operation:** `{'given': [{'timing': 'T_FAIL_TIMEOUT elapsed'}, {'timing': 'DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_014
- **Operation:** `{'given': [{'timing': 'Previous State = NORMAL; Next State = SHUT_OFF'}], 'when': [{'timing': 'Previous State = NORMAL; Next State = SHUT_OFF'}]}`
- **Expectation:** `[{'description': 'System state = SHUT_OFF'}, {'description': 'OFF_REQUEST'}]`

### TC_PM_015
- **Operation:** `{'given': [{'timing': 'Previous State = NORMAL; Next State = SHUT_OFF'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_016
- **Operation:** `{'given': [{'note': 'SHUT_OFF_PERMISSION = Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)', 'parse_status': 'unparsed'}], 'when': []}`
- **Expectation:** `[{'signal': 'SHUT_OFF_PERMISSION', 'value': 'Condition_E', 'operator': '=='}]`

### TC_PM_017
- **Operation:** `{'given': [{'note': 'SHUT_OFF_PERMISSION = Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)', 'parse_status': 'unparsed'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_018
- **Operation:** `{'given': [{'signal': 'SHUT_OFF_PERMISSION', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_019
- **Operation:** `{'given': [{'signal': 'RESET_CONDITION', 'value': 'Condition_R1', 'operator': '=='}], 'when': []}`
- **Expectation:** `[]`

### TC_PM_020
- **Operation:** `{'given': [{'signal': 'RESET_CONDITION', 'value': 'Condition_R1', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_021
- **Operation:** `{'given': [{'signal': 'RESET_CONDITION', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_022
- **Operation:** `{'given': [{'note': 'Condition_E / Request input active for T_CONFIRM'}, {'signal': 'Condition_A / Vehicle condition', 'value': 'stationary', 'operator': '=='}, {'signal': 'Condition_B / Processing state', 'value': 'IDLE', 'operator': '=='}, {'signal': 'Condition_C / Communication status', 'value': 'NORMAL', 'operator': '=='}, {'signal': 'Condition_D / Backup request status', 'value': 'ACTIVE', 'operator': '=='}], 'when': []}`
- **Expectation:** `[{'description': 'System state = SHUT_OFF'}]`

### TC_PM_023
- **Operation:** `{'given': [{'note': 'Condition_E / Request input active for T_CONFIRM'}, {'signal': 'Condition_A / Vehicle condition', 'value': 'stationary', 'operator': '=='}, {'signal': 'Condition_B / Processing state', 'value': 'IDLE', 'operator': '=='}, {'signal': 'Condition_C / Communication status', 'value': 'NORMAL', 'operator': '=='}, {'signal': 'Condition_D / Backup request status', 'value': 'ACTIVE', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_024
- **Operation:** `{'given': [{'signal': 'Condition_A / Vehicle condition', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_025
- **Operation:** `{'given': [{'note': 'NORMAL → SHUT_OFF', 'parse_status': 'unparsed'}], 'when': []}`
- **Expectation:** `[{'description': 'System state = SHUT_OFF'}]`

### TC_PM_026
- **Operation:** `{'given': [{'note': 'NORMAL → SHUT_OFF', 'parse_status': 'unparsed'}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_027
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}], 'when': []}`
- **Expectation:** `[{'signal': 'IGN_STS', 'value': '1', 'operator': '=='}, {'description': 'System state = ACCESSORY'}, {'signal': 'PWR_STATE', 'value': '1; RELAY_MAIN=ON'}]`

### TC_PM_028
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}], 'when': [{'timing': 'elapsed_time < Nonems'}]}`
- **Expectation:** `[{'description': 'Transition/output must not fire early'}]`

### TC_PM_029
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '0', 'note': 'invert primary guard'}], 'when': [{'description': 'Hold other guards as appropriate'}]}`
- **Expectation:** `[{'description': 'Transition must not occur while guard false'}]`

### TC_PM_030
- **Operation:** `{'given': [{'signal': 'PWR_REQ_VALID', 'value': '1', 'operator': '=='}, {'signal': 'GEAR_POS', 'value': 'P', 'operator': '=='}], 'when': []}`
- **Expectation:** `[{'description': 'System state = RUN'}, {'signal': 'PWR_STATE', 'value': '2; RELAY_MAIN=ON'}]`
