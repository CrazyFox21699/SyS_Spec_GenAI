# Condition tree review

## Transition `TC2_XL_Test_Pow_SEC_03_01`

**Raw condition:**
```
(PWR_REQ_VALID AND VEHICLE_SAFE AND (NORMAL_ROUTE OR (BACKUP_ROUTE AND T_SHUT_CONFIRM elapsed)) AND NOT NOK_SHUTOFF)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- detail: Refer to lower condition group
  operator: ==
  parse_status: ok
  raw_condition: PWR_REQ_VALID
  raw_text: PWR_REQ_VALID
  signal: PWR_REQ_VALID
  source:
    file: GPT_GenLogic.xlsx
    row: 24
    section: 5. Control Conditions - Merged Logic Table
    section_index: 3
    sheet: Test_Power_State_Spec
  table_token: PWR_REQ_VALID
  type: boolean_predicate
  value: '1'
- detail: Refer to lower condition group
  operator: ==
  parse_status: ok
  raw_condition: VEHICLE_SAFE
  raw_text: VEHICLE_SAFE
  signal: VEHICLE_SAFE
  source:
    file: GPT_GenLogic.xlsx
    row: 25
    section: 5. Control Conditions - Merged Logic Table
    section_index: 3
    sheet: Test_Power_State_Spec
  table_token: VEHICLE_SAFE
  type: boolean_predicate
  value: '1'
- children:
  - detail: Normal route condition
    operator: ==
    parse_status: ok
    raw_condition: NORMAL_ROUTE
    raw_text: NORMAL_ROUTE
    signal: NORMAL_ROUTE
    source:
      file: GPT_GenLogic.xlsx
      row: 27
      section: 5. Control Conditions - Merged Logic Table
      section_index: 3
      sheet: Test_Power_State_Spec
    table_token: NORMAL_ROUTE
    type: boolean_predicate
    value: '1'
  - children:
    - detail: Backup path valid
      operator: ==
      parse_status: ok
      raw_condition: BACKUP_ROUTE
      raw_text: BACKUP_ROUTE
      signal: BACKUP_ROUTE
      source:
        file: GPT_GenLogic.xlsx
        row: 29
        section: 5. Control Conditions - Merged Logic Table
        section_index: 3
        sheet: Test_Power_State_Spec
      table_token: BACKUP_ROUTE
      type: boolean_predicate
      value: '1'
    - atom_kind: timing_condition
      detail: Timer condition
      parse_status: ok
      raw_condition: T_SHUT_CONFIRM elapsed
      raw_text: T_SHUT_CONFIRM elapsed
      source:
        file: GPT_GenLogic.xlsx
        row: 30
        section: 5. Control Conditions - Merged Logic Table
        section_index: 3
        sheet: Test_Power_State_Spec
      table_token: T_SHUT_CONFIRM elapsed
      timer_qualified:
        constant_ref:
          definition: Shutoff confirmation time
          name: T_SHUT_CONFIRM
          source:
            file: GPT_GenLogic.xlsx
            row: 13
            sheet: Test_Power_State_Spec
        qualified_condition: null
        qualifier: elapsed
        raw_text: T_SHUT_CONFIRM elapsed
        timer_symbol: T_SHUT_CONFIRM
        type: timer_qualified
      type: timing_condition
    parse_status: ok
    type: AND
  parse_status: ok
  type: OR
- detail: Negative blocking condition
  parse_status: partial
  raw_condition: NOT NOK_SHUTOFF
  raw_text: NOT NOK_SHUTOFF
  source:
    file: GPT_GenLogic.xlsx
    row: 31
    section: 5. Control Conditions - Merged Logic Table
    section_index: 3
    sheet: Test_Power_State_Spec
  table_token: NOT NOK_SHUTOFF
  type: opaque
parse_status: partial
raw_condition: ''
type: AND
```

**Timing normalizations:**
- `elapsed` → `elapsed` (review: True)
  - Pattern matched; manual interpretation needed.

## Transition `TC2_XL_Test_Pow_SEC_03_02`

**Raw condition:**
```
(ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0) OR DIAG_BLOCKED)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- detail: Engine/process still running
  operator: ==
  parse_status: ok
  raw_condition: ENGINE_RUNNING
  raw_text: ENGINE_RUNNING
  signal: ENGINE_RUNNING
  source:
    file: GPT_GenLogic.xlsx
    row: 33
    section: 5. Control Conditions - Merged Logic Table
    section_index: 3
    sheet: Test_Power_State_Spec
  table_token: ENGINE_RUNNING
  type: boolean_predicate
  value: '1'
- detail: Gear position is not P
  operator: ==
  parse_status: ok
  raw_condition: GEAR_NOT_PARK
  raw_text: GEAR_NOT_PARK
  signal: GEAR_NOT_PARK
  source:
    file: GPT_GenLogic.xlsx
    row: 34
    section: 5. Control Conditions - Merged Logic Table
    section_index: 3
    sheet: Test_Power_State_Spec
  table_token: GEAR_NOT_PARK
  type: boolean_predicate
  value: '1'
- children:
  - detail: Door lock not satisfied
    operator: ==
    parse_status: ok
    raw_condition: DOOR_UNLOCKED
    raw_text: DOOR_UNLOCKED
    signal: DOOR_UNLOCKED
    source:
      file: GPT_GenLogic.xlsx
      row: 36
      section: 5. Control Conditions - Merged Logic Table
      section_index: 3
      sheet: Test_Power_State_Spec
    table_token: DOOR_UNLOCKED
    type: boolean_predicate
    value: '1'
  - atom_kind: state_condition
    detail: Vehicle speed is non-zero
    operator: '>'
    parse_status: ok
    raw_condition: VEH_SPD > 0
    signal: VEH_SPD
    source:
      file: GPT_GenLogic.xlsx
      row: 37
      section: 5. Control Conditions - Merged Logic Table
      section_index: 3
      sheet: Test_Power_State_Spec
    table_token: VEH_SPD > 0
    type: signal_condition
    value: '0'
    value_domain: boolean
  parse_status: ok
  type: AND
- detail: Diagnostic prohibits transition
  operator: ==
  parse_status: ok
  raw_condition: DIAG_BLOCKED
  raw_text: DIAG_BLOCKED
  signal: DIAG_BLOCKED
  source:
    file: GPT_GenLogic.xlsx
    row: 38
    section: 5. Control Conditions - Merged Logic Table
    section_index: 3
    sheet: Test_Power_State_Spec
  table_token: DIAG_BLOCKED
  type: boolean_predicate
  value: '1'
parse_status: ok
raw_condition: ''
type: OR
```


## Transition `TC2_XL_02_State_01_01`

**Raw condition:**
```
Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- name: Condition_E
  parse_status: partial
  raw_condition: Condition_E
  type: reference
- name: Condition_A
  parse_status: partial
  raw_condition: Condition_A
  type: reference
- name: Condition_B
  parse_status: partial
  raw_condition: Condition_B
  type: reference
- children:
  - name: Condition_C
    parse_status: partial
    raw_condition: Condition_C
    type: reference
  - name: Condition_D
    parse_status: partial
    raw_condition: Condition_D
    type: reference
  parse_status: partial
  raw_condition: Condition_C OR Condition_D
  type: OR
parse_status: partial
raw_condition: ''
source:
  bbox:
    col_end: 10
    col_start: 1
    row_end: 4
    row_start: 1
  file: PM_Behavior_Logic_Sample.xlsx
  region: 1
  row: 2
  sheet: 02_State_Machine
table_token: Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)
type: AND
```


## Transition `TC2_XL_02_State_01_02`

**Raw condition:**
```
Mode_cmd = 2 AND Battery_OK = 1
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: Mode_cmd = 2
  signal: Mode_cmd
  type: signal_condition
  value: '2'
  value_domain: literal
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: Battery_OK = 1
  signal: Battery_OK
  type: signal_condition
  value: '1'
  value_domain: boolean
parse_status: ok
raw_condition: ''
source:
  bbox:
    col_end: 10
    col_start: 1
    row_end: 4
    row_start: 1
  file: PM_Behavior_Logic_Sample.xlsx
  region: 1
  row: 3
  sheet: 02_State_Machine
table_token: Mode_cmd = 2 AND Battery_OK = 1
type: AND
```


## Transition `TC2_XL_02_State_01_03`

**Raw condition:**
```
Battery_OK = 0 OR T_trans exceeded
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: Battery_OK = 0
  signal: Battery_OK
  type: signal_condition
  value: '0'
  value_domain: boolean
- atom_kind: timing_condition
  parse_status: ok
  raw_condition: T_trans exceeded
  raw_text: T_trans exceeded
  timer_qualified:
    constant_ref:
      definition: T_trans
      name: T_TRANS
      source:
        file: PM_StateFlow_Timing_Sample.pdf
        row: null
        section: null
        table: null
    qualified_condition: null
    qualifier: exceeded
    raw_text: T_trans exceeded
    timer_symbol: T_TRANS
    type: timer_qualified
  type: timing_condition
parse_status: ok
raw_condition: ''
source:
  bbox:
    col_end: 10
    col_start: 1
    row_end: 4
    row_start: 1
  file: PM_Behavior_Logic_Sample.xlsx
  region: 1
  row: 4
  sheet: 02_State_Machine
table_token: Battery_OK = 0 OR T_trans exceeded
type: OR
```

**Timing normalizations:**
- `exceeded` → `exceeded` (review: True)
  - Pattern matched; manual interpretation needed.

## Transition `WD2_001`

**Raw condition:**
```
Condition_E / System request is active for confirmation time AND Condition_A / Vehicle condition is safe for shutoff AND Condition_A / Processing state is ready AND (Condition_C / Communication status is valid OR Condition_D / External fallback request is detected)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- parse_status: partial
  raw_condition: Condition_E / System request is active for confirmation time
  raw_text: Condition_E / System request is active for confirmation time
  type: opaque
- parse_status: partial
  raw_condition: Condition_A / Vehicle condition is safe for shutoff
  raw_text: Condition_A / Vehicle condition is safe for shutoff
  type: opaque
- parse_status: partial
  raw_condition: Condition_A / Processing state is ready
  raw_text: Condition_A / Processing state is ready
  type: opaque
- children:
  - parse_status: partial
    raw_condition: Condition_C / Communication status is valid
    raw_text: Condition_C / Communication status is valid
    type: opaque
  - parse_status: partial
    raw_condition: Condition_D / External fallback request is detected
    raw_text: Condition_D / External fallback request is detected
    type: opaque
  parse_status: partial
  raw_condition: Condition_C / Communication status is valid OR Condition_D / External
    fallback request is detected
  type: OR
parse_status: partial
raw_condition: Condition_E / System request is active for confirmation time AND Condition_A
  / Vehicle condition is safe for shutoff AND Condition_A / Processing state is ready
  AND (Condition_C / Communication status is valid OR Condition_D / External fallback
  request is detected)
type: AND
```


## Transition `WD4_001`

**Raw condition:**
```
Condition_E / Request input active for T_CONFIRM AND Condition_A / Vehicle condition = stationary AND Condition_B / Processing state = IDLE AND (Condition_C / Communication status = NORMAL OR Condition_D / Backup request status = ACTIVE)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- parse_status: partial
  raw_condition: Condition_E / Request input active for T_CONFIRM
  raw_text: Condition_E / Request input active for T_CONFIRM
  type: opaque
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: Condition_A / Vehicle condition = stationary
  signal: Condition_A / Vehicle condition
  type: signal_condition
  value: stationary
  value_domain: literal
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: Condition_B / Processing state = IDLE
  signal: Condition_B / Processing state
  type: signal_condition
  value: IDLE
  value_domain: enum
- children:
  - atom_kind: state_condition
    operator: ==
    parse_status: ok
    raw_condition: Condition_C / Communication status = NORMAL
    signal: Condition_C / Communication status
    type: signal_condition
    value: NORMAL
    value_domain: enum
  - atom_kind: state_condition
    operator: ==
    parse_status: ok
    raw_condition: Condition_D / Backup request status = ACTIVE
    signal: Condition_D / Backup request status
    type: signal_condition
    value: ACTIVE
    value_domain: enum
  parse_status: ok
  raw_condition: Condition_C / Communication status = NORMAL OR Condition_D / Backup
    request status = ACTIVE
  type: OR
parse_status: partial
raw_condition: Condition_E / Request input active for T_CONFIRM AND Condition_A /
  Vehicle condition = stationary AND Condition_B / Processing state = IDLE AND (Condition_C
  / Communication status = NORMAL OR Condition_D / Backup request status = ACTIVE)
type: AND
```


## Transition `WD6_001`

**Raw condition:**
```
(Condition_R1 / System request becomes inactive OR Condition_R1 / Vehicle condition becomes unsafe OR Condition_R3 / Communication invalid timeout is detected)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- parse_status: partial
  raw_condition: Condition_R1 / System request becomes inactive
  raw_text: Condition_R1 / System request becomes inactive
  type: opaque
- parse_status: partial
  raw_condition: Condition_R1 / Vehicle condition becomes unsafe
  raw_text: Condition_R1 / Vehicle condition becomes unsafe
  type: opaque
- atom_kind: timing_condition
  parse_status: ok
  raw_condition: Condition_R3 / Communication invalid timeout is detected
  raw_text: Condition_R3 / Communication invalid timeout is detected
  type: timing_condition
parse_status: partial
raw_condition: (Condition_R1 / System request becomes inactive OR Condition_R1 / Vehicle
  condition becomes unsafe OR Condition_R3 / Communication invalid timeout is detected)
type: OR
```

**Timing normalizations:**
- `timeout` → `timeout` (review: True)
  - Pattern matched; manual interpretation needed.

## Transition `FORMULA_001`

**Raw condition:**
```
Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- name: Condition_E
  parse_status: partial
  raw_condition: Condition_E
  type: reference
- name: Condition_A
  parse_status: partial
  raw_condition: Condition_A
  type: reference
- name: Condition_B
  parse_status: partial
  raw_condition: Condition_B
  type: reference
- children:
  - name: Condition_C
    parse_status: partial
    raw_condition: Condition_C
    type: reference
  - name: Condition_D
    parse_status: partial
    raw_condition: Condition_D
    type: reference
  parse_status: partial
  raw_condition: Condition_C OR Condition_D
  type: OR
parse_status: partial
raw_condition: Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)
type: AND
```


## Transition `FORMULA_002`

**Raw condition:**
```
Condition_R1 OR Condition_R2 OR Condition_R3
```

**Parsed tree (deterministic parser):**
```yaml
children:
- name: Condition_R1
  parse_status: partial
  raw_condition: Condition_R1
  type: reference
- name: Condition_R2
  parse_status: partial
  raw_condition: Condition_R2
  type: reference
- name: Condition_R3
  parse_status: partial
  raw_condition: Condition_R3
  type: reference
parse_status: partial
raw_condition: Condition_R1 OR Condition_R2 OR Condition_R3
type: OR
```


## Transition `TC2_T1_01`

**Raw condition:**
```
(OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom:
    footnote_refs: []
    negated: false
    operator: '='
    raw_text: OK_SHUTOFF = 1
    resolution: resolved
    signal: OK_SHUTOFF
    source: &id001
      control: SHUTOFF_DECISION
      document: Shutoff_Condition_Spec_v2.docx
      file: Shutoff_Condition_Spec_v2.docx
      section_zone: control_conditions
      table: table_1
      table_id: T1_01
    value: '1'
    value_domain: boolean
  comparator_value: '1'
  confidence: medium
  footnotes: []
  id: ref_d2b82079
  issue_status: ok
  name: OK_SHUTOFF
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: OK_SHUTOFF = 1
  review_status: pending
  source: *id001
  type: condition
- children:
  - atom:
      footnote_refs:
      - (*1)
      negated: true
      operator: ==
      raw_text: NOK_SHUTOFF = (*1)
      resolution: resolved
      signal: NOK_SHUTOFF
      source: *id001
      value: null
    confidence: medium
    footnotes:
    - '1'
    id: ref_bcddef2b
    issue_status: ok
    name: NOK_SHUTOFF
    parser_reason: Detected as NOT condition because token starts with NOT.
    raw_text: NOT NOK_SHUTOFF = (*1)
    review_status: pending
    source: *id001
    type: condition
  confidence: medium
  id: not_17467b03
  issue_status: ok
  parser_reason: Detected as NOT gate because row text starts with NOT.
  raw_text: NOT NOK_SHUTOFF = (*1)
  review_status: pending
  source: *id001
  type: NOT
- atom:
    footnote_refs: []
    negated: false
    operator: '='
    raw_text: FORCE_SHUTOFF = 150
    resolution: resolved
    signal: FORCE_SHUTOFF
    source: *id001
    value: '150'
  comparator_value: '150'
  confidence: medium
  footnotes: []
  id: ref_0cca89e1
  issue_status: ok
  name: FORCE_SHUTOFF
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: FORCE_SHUTOFF = 150
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs: []
    negated: false
    operator: '='
    raw_text: CND_FORCE_ALLOWED = 0
    resolution: resolved
    signal: CND_FORCE_ALLOWED
    source: *id001
    value: '0'
    value_domain: boolean
  comparator_value: '0'
  confidence: medium
  footnotes: []
  id: ref_7304bcef
  issue_status: ok
  name: CND_FORCE_ALLOWED
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: CND_FORCE_ALLOWED = 0
  review_status: pending
  source: *id001
  type: condition
confidence: high
id: op_b8eac4dc
issue_status: ok
parse_status: ok
parser_reason: Merged-cell `OR` scope groups 4 sibling branches from multi-row condition
  table.
raw_text: OR
review_status: parsed
source: *id001
type: OR
```


## Transition `TC2_T2_01`

**Raw condition:**
```
(CND_REQ_GROUP = 1 AND CND_SAFE_GROUP = 1 AND (CND_NORMAL_ROUTE = 1 OR CND_BACKUP_ROUTE = 1) AND (CND_BACKUP_TIMER_OK = 2 AND POWER = OFF) AND CND_OUTPUT_READY = 2)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom:
    footnote_refs: []
    negated: false
    operator: '='
    raw_text: CND_REQ_GROUP = 1
    resolution: resolved
    signal: CND_REQ_GROUP
    source: &id001
      control: OK_SHUTOFF
      document: Shutoff_Condition_Spec_v2.docx
      file: Shutoff_Condition_Spec_v2.docx
      section_zone: control_conditions
      table: table_2
      table_id: T2_01
    value: '1'
    value_domain: boolean
  comparator_value: '1'
  confidence: medium
  footnotes: []
  id: ref_da3e2e4c
  issue_status: ok
  name: CND_REQ_GROUP
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: CND_REQ_GROUP = 1
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs: []
    negated: false
    operator: '='
    raw_text: CND_SAFE_GROUP = 1
    resolution: resolved
    signal: CND_SAFE_GROUP
    source: *id001
    value: '1'
    value_domain: boolean
  comparator_value: '1'
  confidence: medium
  footnotes: []
  id: ref_dec0b406
  issue_status: ok
  name: CND_SAFE_GROUP
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: CND_SAFE_GROUP = 1
  review_status: pending
  source: *id001
  type: condition
- children:
  - atom:
      footnote_refs: []
      negated: false
      operator: '='
      raw_text: CND_NORMAL_ROUTE = 1
      resolution: resolved
      signal: CND_NORMAL_ROUTE
      source: *id001
      value: '1'
      value_domain: boolean
    comparator_value: '1'
    confidence: medium
    footnotes: []
    id: ref_f9903de9
    issue_status: ok
    name: CND_NORMAL_ROUTE
    parser_reason: Detected as condition reference from row path leaf token.
    raw_text: CND_NORMAL_ROUTE = 1
    review_status: pending
    source: *id001
    type: condition
  - children:
    - atom:
        footnote_refs: []
        negated: false
        operator: '='
        raw_text: CND_BACKUP_ROUTE = 1
        resolution: resolved
        signal: CND_BACKUP_ROUTE
        source: *id001
        value: '1'
        value_domain: boolean
      comparator_value: '1'
      confidence: medium
      footnotes: []
      id: ref_cc4ac1c4
      issue_status: ok
      name: CND_BACKUP_ROUTE
      parser_reason: Detected as condition reference from row path leaf token.
      raw_text: CND_BACKUP_ROUTE = 1
      review_status: pending
      source: *id001
      type: condition
    confidence: high
    id: op_571e05fa
    issue_status: ok
    parser_reason: Detected `AND` gate at column depth 0 (nesting level 0).
    raw_text: AND
    review_status: parsed
    source: *id001
    type: AND
  confidence: high
  id: op_2c1716ec
  issue_status: ok
  parser_reason: Grouped 2 consecutive rows sharing `OR` after merged-cell scope stripping.
  raw_text: OR
  review_status: parsed
  source: *id001
  type: OR
- children:
  - atom:
      footnote_refs: []
      negated: false
      operator: '='
      raw_text: CND_BACKUP_TIMER_OK = 2
      resolution: resolved
      signal: CND_BACKUP_TIMER_OK
      source: *id001
      value: '2'
    comparator_value: '2'
    confidence: medium
    footnotes: []
    id: ref_a6f25b35
    issue_status: ok
    name: CND_BACKUP_TIMER_OK
    parser_reason: Detected as condition reference from row path leaf token.
    raw_text: CND_BACKUP_TIMER_OK = 2
    review_status: pending
    source: *id001
    type: condition
  - children:
    - atom:
        footnote_refs: []
        negated: false
        operator: '='
        raw_text: POWER = OFF
        resolution: resolved
        signal: POWER
        source: *id001
        value: 'OFF'
        value_domain: boolean
      comparator_value: 'OFF'
      confidence: medium
      footnotes: []
      id: ref_66441890
      issue_status: ok
      name: POWER
      parser_reason: Detected as condition reference from row path leaf token.
      raw_text: POWER = OFF
      review_status: pending
      source: *id001
      type: condition
    confidence: high
    id: op_f808396b
    issue_status: ok
    parser_reason: Detected `AND` gate at column depth 1 (nesting level 1).
    raw_text: AND
    review_status: parsed
    source: *id001
    type: AND
  confidence: high
  id: op_defbb5bc
  issue_status: ok
  parser_reason: Condition followed by operator at deeper column; grouped under implicit
    AND.
  raw_text: AND
  review_status: parsed
  source: *id001
  type: AND
- atom:
    footnote_refs: []
    negated: false
    operator: '='
    raw_text: CND_OUTPUT_READY = 2
    resolution: resolved
    signal: CND_OUTPUT_READY
    source: *id001
    value: '2'
  comparator_value: '2'
  confidence: medium
  footnotes: []
  id: ref_1d16bf13
  issue_status: ok
  name: CND_OUTPUT_READY
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: CND_OUTPUT_READY = 2
  review_status: pending
  source: *id001
  type: condition
confidence: high
id: op_c3177739
issue_status: ok
parse_status: ok
parser_reason: Merged-cell `AND` scope groups 5 sibling branches from multi-row condition
  table.
raw_text: AND
review_status: parsed
source: *id001
type: AND
```


## Transition `TC2_T3_01`

**Raw condition:**
```
(REQ_MAIN_OK (*1) AND REQ_SRC_A_VALID (*2) AND REQ_SRC_B_VALID (*3) AND REQ_STABLE (*4))
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom:
    footnote_refs:
    - (*1)
    negated: false
    operator: ==
    raw_text: REQ_MAIN_OK (*1)
    resolution: resolved
    signal: REQ_MAIN_OK
    source: &id001
      control: CND_REQ_GROUP
      document: Shutoff_Condition_Spec_v2.docx
      file: Shutoff_Condition_Spec_v2.docx
      section_zone: control_conditions
      table: table_3
      table_id: T3_01
    value: null
  confidence: medium
  footnotes:
  - '1'
  id: ref_ae59f8dd
  issue_status: ok
  name: REQ_MAIN_OK
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: REQ_MAIN_OK (*1)
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs:
    - (*2)
    negated: false
    operator: ==
    raw_text: REQ_SRC_A_VALID (*2)
    resolution: needs_llm
    signal: REQ_SRC_A_VALID
    source: *id001
    value: null
  confidence: medium
  footnotes:
  - '2'
  id: ref_965032ee
  issue_status: ok
  name: REQ_SRC_A_VALID
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: REQ_SRC_A_VALID (*2)
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs:
    - (*3)
    negated: false
    operator: ==
    raw_text: REQ_SRC_B_VALID (*3)
    resolution: needs_llm
    signal: REQ_SRC_B_VALID
    source: *id001
    value: null
  confidence: medium
  footnotes:
  - '3'
  id: ref_c5b56bee
  issue_status: ok
  name: REQ_SRC_B_VALID
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: REQ_SRC_B_VALID (*3)
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs:
    - (*4)
    negated: false
    operator: ==
    raw_text: REQ_STABLE (*4)
    resolution: needs_llm
    signal: REQ_STABLE
    source: *id001
    value: null
  confidence: medium
  footnotes:
  - '4'
  id: ref_882afd0b
  issue_status: ok
  name: REQ_STABLE
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: REQ_STABLE (*4)
  review_status: pending
  source: *id001
  type: condition
confidence: high
id: op_8dd2296c
issue_status: ok
parse_status: ok
parser_reason: Merged-cell `AND` scope groups 4 sibling branches from multi-row condition
  table.
raw_text: AND
review_status: parsed
source: *id001
type: AND
```


## Transition `TC2_T4_01`

**Raw condition:**
```
(VEHICLE_STOPPED = 2(*1) AND DRIVER_SAFE (*2) AND PROCESS_IDLE (*3) AND PROCESS_PREPARED (*4) AND NOT SAFETY_LOCKED (*5))
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom:
    footnote_refs:
    - (*1)
    negated: false
    operator: '='
    raw_text: VEHICLE_STOPPED = 2(*1)
    resolution: resolved
    signal: VEHICLE_STOPPED
    source: &id001
      control: CND_SAFE_GROUP
      document: Shutoff_Condition_Spec_v2.docx
      file: Shutoff_Condition_Spec_v2.docx
      section_zone: control_conditions
      table: table_4
      table_id: T4_01
    value: '2'
  comparator_value: '2'
  confidence: medium
  footnotes:
  - '1'
  id: ref_b99e84d0
  issue_status: ok
  name: VEHICLE_STOPPED
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: VEHICLE_STOPPED = 2(*1)
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs:
    - (*2)
    negated: false
    operator: ==
    raw_text: DRIVER_SAFE (*2)
    resolution: needs_llm
    signal: DRIVER_SAFE
    source: *id001
    value: null
  confidence: medium
  footnotes:
  - '2'
  id: ref_fed68512
  issue_status: ok
  name: DRIVER_SAFE
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: DRIVER_SAFE (*2)
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs:
    - (*3)
    negated: false
    operator: ==
    raw_text: PROCESS_IDLE (*3)
    resolution: needs_llm
    signal: PROCESS_IDLE
    source: *id001
    value: null
  confidence: medium
  footnotes:
  - '3'
  id: ref_561a65d6
  issue_status: ok
  name: PROCESS_IDLE
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: PROCESS_IDLE (*3)
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs:
    - (*4)
    negated: false
    operator: ==
    raw_text: PROCESS_PREPARED (*4)
    resolution: needs_llm
    signal: PROCESS_PREPARED
    source: *id001
    value: null
  confidence: medium
  footnotes:
  - '4'
  id: ref_6538a0bd
  issue_status: ok
  name: PROCESS_PREPARED
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: PROCESS_PREPARED (*4)
  review_status: pending
  source: *id001
  type: condition
- children:
  - atom:
      footnote_refs:
      - (*5)
      negated: true
      operator: ==
      raw_text: SAFETY_LOCKED (*5)
      resolution: needs_llm
      signal: SAFETY_LOCKED
      source: *id001
      value: null
    confidence: medium
    footnotes:
    - '5'
    id: ref_3781aff5
    issue_status: ok
    name: SAFETY_LOCKED
    parser_reason: Detected as NOT condition because token starts with NOT.
    raw_text: NOT SAFETY_LOCKED (*5)
    review_status: pending
    source: *id001
    type: condition
  confidence: medium
  id: not_50402dd0
  issue_status: ok
  parser_reason: Detected as NOT gate because row text starts with NOT.
  raw_text: NOT SAFETY_LOCKED (*5)
  review_status: pending
  source: *id001
  type: NOT
confidence: high
id: op_58496805
issue_status: ok
parse_status: ok
parser_reason: Merged-cell `AND` scope groups 5 sibling branches from multi-row condition
  table.
raw_text: AND
review_status: parsed
source: *id001
type: AND
```


## Transition `TC2_T1_01`

**Raw condition:**
```
(HUY = OK OR OK_SHUTOFF = 1 OR NOT NOK_SHUTOFF = (*1) OR FORCE_SHUTOFF = 150 OR CND_FORCE_ALLOWED = 0)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom:
    footnote_refs: []
    negated: false
    operator: '='
    raw_text: HUY = OK
    resolution: resolved
    signal: HUY
    source: &id001
      control: SHUTOFF_DECISION
      document: edited_Shutoff_Condition_Spec.docx
      file: edited_Shutoff_Condition_Spec.docx
      section_zone: control_conditions
      table: table_1
      table_id: T1_01
    value: OK
    value_domain: enum
  comparator_value: OK
  confidence: medium
  footnotes: []
  id: ref_5299edc3
  issue_status: ok
  name: HUY
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: HUY = OK
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs: []
    negated: false
    operator: '='
    raw_text: OK_SHUTOFF = 1
    resolution: resolved
    signal: OK_SHUTOFF
    source: *id001
    value: '1'
    value_domain: boolean
  comparator_value: '1'
  confidence: medium
  footnotes: []
  id: ref_2a9a8676
  issue_status: ok
  name: OK_SHUTOFF
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: OK_SHUTOFF = 1
  review_status: pending
  source: *id001
  type: condition
- children:
  - atom:
      footnote_refs:
      - (*1)
      negated: true
      operator: ==
      raw_text: NOK_SHUTOFF = (*1)
      resolution: resolved
      signal: NOK_SHUTOFF
      source: *id001
      value: null
    confidence: medium
    footnotes:
    - '1'
    id: ref_74674f07
    issue_status: ok
    name: NOK_SHUTOFF
    parser_reason: Detected as NOT condition because token starts with NOT.
    raw_text: NOT NOK_SHUTOFF = (*1)
    review_status: pending
    source: *id001
    type: condition
  confidence: medium
  id: not_66a771e2
  issue_status: ok
  parser_reason: Detected as NOT gate because row text starts with NOT.
  raw_text: NOT NOK_SHUTOFF = (*1)
  review_status: pending
  source: *id001
  type: NOT
- atom:
    footnote_refs: []
    negated: false
    operator: '='
    raw_text: FORCE_SHUTOFF = 150
    resolution: resolved
    signal: FORCE_SHUTOFF
    source: *id001
    value: '150'
  comparator_value: '150'
  confidence: medium
  footnotes: []
  id: ref_70ef5a20
  issue_status: ok
  name: FORCE_SHUTOFF
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: FORCE_SHUTOFF = 150
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs: []
    negated: false
    operator: '='
    raw_text: CND_FORCE_ALLOWED = 0
    resolution: resolved
    signal: CND_FORCE_ALLOWED
    source: *id001
    value: '0'
    value_domain: boolean
  comparator_value: '0'
  confidence: medium
  footnotes: []
  id: ref_992b0d30
  issue_status: ok
  name: CND_FORCE_ALLOWED
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: CND_FORCE_ALLOWED = 0
  review_status: pending
  source: *id001
  type: condition
confidence: high
id: op_3bcb1fb0
issue_status: ok
parse_status: ok
parser_reason: Merged-cell `OR` scope groups 5 sibling branches from multi-row condition
  table.
raw_text: OR
review_status: parsed
source: *id001
type: OR
```


## Transition `TC2_T2_01`

**Raw condition:**
```
(CND_REQ_GROUP = 1 AND CND_SAFE_GROUP = 1 AND (CND_NORMAL_ROUTE = 1 OR CND_BACKUP_ROUTE = 1) AND (CND_BACKUP_TIMER_OK = 2 AND POWER = OFF) AND CND_OUTPUT_READY = 2)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom:
    footnote_refs: []
    negated: false
    operator: '='
    raw_text: CND_REQ_GROUP = 1
    resolution: resolved
    signal: CND_REQ_GROUP
    source: &id001
      control: OK_SHUTOFF
      document: edited_Shutoff_Condition_Spec.docx
      file: edited_Shutoff_Condition_Spec.docx
      section_zone: control_conditions
      table: table_2
      table_id: T2_01
    value: '1'
    value_domain: boolean
  comparator_value: '1'
  confidence: medium
  footnotes: []
  id: ref_09eeb93d
  issue_status: ok
  name: CND_REQ_GROUP
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: CND_REQ_GROUP = 1
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs: []
    negated: false
    operator: '='
    raw_text: CND_SAFE_GROUP = 1
    resolution: resolved
    signal: CND_SAFE_GROUP
    source: *id001
    value: '1'
    value_domain: boolean
  comparator_value: '1'
  confidence: medium
  footnotes: []
  id: ref_15792f0b
  issue_status: ok
  name: CND_SAFE_GROUP
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: CND_SAFE_GROUP = 1
  review_status: pending
  source: *id001
  type: condition
- children:
  - atom:
      footnote_refs: []
      negated: false
      operator: '='
      raw_text: CND_NORMAL_ROUTE = 1
      resolution: resolved
      signal: CND_NORMAL_ROUTE
      source: *id001
      value: '1'
      value_domain: boolean
    comparator_value: '1'
    confidence: medium
    footnotes: []
    id: ref_cfaa665d
    issue_status: ok
    name: CND_NORMAL_ROUTE
    parser_reason: Detected as condition reference from row path leaf token.
    raw_text: CND_NORMAL_ROUTE = 1
    review_status: pending
    source: *id001
    type: condition
  - children:
    - atom:
        footnote_refs: []
        negated: false
        operator: '='
        raw_text: CND_BACKUP_ROUTE = 1
        resolution: resolved
        signal: CND_BACKUP_ROUTE
        source: *id001
        value: '1'
        value_domain: boolean
      comparator_value: '1'
      confidence: medium
      footnotes: []
      id: ref_1133a8c6
      issue_status: ok
      name: CND_BACKUP_ROUTE
      parser_reason: Detected as condition reference from row path leaf token.
      raw_text: CND_BACKUP_ROUTE = 1
      review_status: pending
      source: *id001
      type: condition
    confidence: high
    id: op_46cc22bf
    issue_status: ok
    parser_reason: Detected `AND` gate at column depth 0 (nesting level 0).
    raw_text: AND
    review_status: parsed
    source: *id001
    type: AND
  confidence: high
  id: op_1bcb4b56
  issue_status: ok
  parser_reason: Grouped 2 consecutive rows sharing `OR` after merged-cell scope stripping.
  raw_text: OR
  review_status: parsed
  source: *id001
  type: OR
- children:
  - atom:
      footnote_refs: []
      negated: false
      operator: '='
      raw_text: CND_BACKUP_TIMER_OK = 2
      resolution: resolved
      signal: CND_BACKUP_TIMER_OK
      source: *id001
      value: '2'
    comparator_value: '2'
    confidence: medium
    footnotes: []
    id: ref_a026c431
    issue_status: ok
    name: CND_BACKUP_TIMER_OK
    parser_reason: Detected as condition reference from row path leaf token.
    raw_text: CND_BACKUP_TIMER_OK = 2
    review_status: pending
    source: *id001
    type: condition
  - children:
    - atom:
        footnote_refs: []
        negated: false
        operator: '='
        raw_text: POWER = OFF
        resolution: resolved
        signal: POWER
        source: *id001
        value: 'OFF'
        value_domain: boolean
      comparator_value: 'OFF'
      confidence: medium
      footnotes: []
      id: ref_88d6edb9
      issue_status: ok
      name: POWER
      parser_reason: Detected as condition reference from row path leaf token.
      raw_text: POWER = OFF
      review_status: pending
      source: *id001
      type: condition
    confidence: high
    id: op_45658592
    issue_status: ok
    parser_reason: Detected `AND` gate at column depth 1 (nesting level 1).
    raw_text: AND
    review_status: parsed
    source: *id001
    type: AND
  confidence: high
  id: op_d7140aea
  issue_status: ok
  parser_reason: Condition followed by operator at deeper column; grouped under implicit
    AND.
  raw_text: AND
  review_status: parsed
  source: *id001
  type: AND
- atom:
    footnote_refs: []
    negated: false
    operator: '='
    raw_text: CND_OUTPUT_READY = 2
    resolution: resolved
    signal: CND_OUTPUT_READY
    source: *id001
    value: '2'
  comparator_value: '2'
  confidence: medium
  footnotes: []
  id: ref_f799a376
  issue_status: ok
  name: CND_OUTPUT_READY
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: CND_OUTPUT_READY = 2
  review_status: pending
  source: *id001
  type: condition
confidence: high
id: op_c20a3625
issue_status: ok
parse_status: ok
parser_reason: Merged-cell `AND` scope groups 5 sibling branches from multi-row condition
  table.
raw_text: AND
review_status: parsed
source: *id001
type: AND
```


## Transition `TC2_T3_01`

**Raw condition:**
```
(REQ_MAIN_OK (*1) AND REQ_SRC_A_VALID (*2) AND REQ_SRC_B_VALID (*3) AND REQ_STABLE (*4))
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom:
    footnote_refs:
    - (*1)
    negated: false
    operator: ==
    raw_text: REQ_MAIN_OK (*1)
    resolution: resolved
    signal: REQ_MAIN_OK
    source: &id001
      control: CND_REQ_GROUP
      document: edited_Shutoff_Condition_Spec.docx
      file: edited_Shutoff_Condition_Spec.docx
      section_zone: control_conditions
      table: table_3
      table_id: T3_01
    value: null
  confidence: medium
  footnotes:
  - '1'
  id: ref_8048e76f
  issue_status: ok
  name: REQ_MAIN_OK
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: REQ_MAIN_OK (*1)
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs:
    - (*2)
    negated: false
    operator: ==
    raw_text: REQ_SRC_A_VALID (*2)
    resolution: needs_llm
    signal: REQ_SRC_A_VALID
    source: *id001
    value: null
  confidence: medium
  footnotes:
  - '2'
  id: ref_91b071f1
  issue_status: ok
  name: REQ_SRC_A_VALID
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: REQ_SRC_A_VALID (*2)
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs:
    - (*3)
    negated: false
    operator: ==
    raw_text: REQ_SRC_B_VALID (*3)
    resolution: needs_llm
    signal: REQ_SRC_B_VALID
    source: *id001
    value: null
  confidence: medium
  footnotes:
  - '3'
  id: ref_d10fb297
  issue_status: ok
  name: REQ_SRC_B_VALID
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: REQ_SRC_B_VALID (*3)
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs:
    - (*4)
    negated: false
    operator: ==
    raw_text: REQ_STABLE (*4)
    resolution: needs_llm
    signal: REQ_STABLE
    source: *id001
    value: null
  confidence: medium
  footnotes:
  - '4'
  id: ref_61c8ca54
  issue_status: ok
  name: REQ_STABLE
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: REQ_STABLE (*4)
  review_status: pending
  source: *id001
  type: condition
confidence: high
id: op_1375ed8d
issue_status: ok
parse_status: ok
parser_reason: Merged-cell `AND` scope groups 4 sibling branches from multi-row condition
  table.
raw_text: AND
review_status: parsed
source: *id001
type: AND
```


## Transition `TC2_T4_01`

**Raw condition:**
```
(VEHICLE_STOPPED = 2(*1) AND DRIVER_SAFE (*2) AND PROCESS_IDLE (*3) AND PROCESS_PREPARED (*4) AND NOT SAFETY_LOCKED (*5))
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom:
    footnote_refs:
    - (*1)
    negated: false
    operator: '='
    raw_text: VEHICLE_STOPPED = 2(*1)
    resolution: resolved
    signal: VEHICLE_STOPPED
    source: &id001
      control: CND_SAFE_GROUP
      document: edited_Shutoff_Condition_Spec.docx
      file: edited_Shutoff_Condition_Spec.docx
      section_zone: control_conditions
      table: table_4
      table_id: T4_01
    value: '2'
  comparator_value: '2'
  confidence: medium
  footnotes:
  - '1'
  id: ref_a85f1651
  issue_status: ok
  name: VEHICLE_STOPPED
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: VEHICLE_STOPPED = 2(*1)
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs:
    - (*2)
    negated: false
    operator: ==
    raw_text: DRIVER_SAFE (*2)
    resolution: needs_llm
    signal: DRIVER_SAFE
    source: *id001
    value: null
  confidence: medium
  footnotes:
  - '2'
  id: ref_7ba1a510
  issue_status: ok
  name: DRIVER_SAFE
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: DRIVER_SAFE (*2)
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs:
    - (*3)
    negated: false
    operator: ==
    raw_text: PROCESS_IDLE (*3)
    resolution: needs_llm
    signal: PROCESS_IDLE
    source: *id001
    value: null
  confidence: medium
  footnotes:
  - '3'
  id: ref_ed4e6737
  issue_status: ok
  name: PROCESS_IDLE
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: PROCESS_IDLE (*3)
  review_status: pending
  source: *id001
  type: condition
- atom:
    footnote_refs:
    - (*4)
    negated: false
    operator: ==
    raw_text: PROCESS_PREPARED (*4)
    resolution: needs_llm
    signal: PROCESS_PREPARED
    source: *id001
    value: null
  confidence: medium
  footnotes:
  - '4'
  id: ref_cc873d0d
  issue_status: ok
  name: PROCESS_PREPARED
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: PROCESS_PREPARED (*4)
  review_status: pending
  source: *id001
  type: condition
- children:
  - atom:
      footnote_refs:
      - (*5)
      negated: true
      operator: ==
      raw_text: SAFETY_LOCKED (*5)
      resolution: needs_llm
      signal: SAFETY_LOCKED
      source: *id001
      value: null
    confidence: medium
    footnotes:
    - '5'
    id: ref_ae141eb3
    issue_status: ok
    name: SAFETY_LOCKED
    parser_reason: Detected as NOT condition because token starts with NOT.
    raw_text: NOT SAFETY_LOCKED (*5)
    review_status: pending
    source: *id001
    type: condition
  confidence: medium
  id: not_aaae2ab6
  issue_status: ok
  parser_reason: Detected as NOT gate because row text starts with NOT.
  raw_text: NOT SAFETY_LOCKED (*5)
  review_status: pending
  source: *id001
  type: NOT
confidence: high
id: op_f9646692
issue_status: ok
parse_status: ok
parser_reason: Merged-cell `AND` scope groups 5 sibling branches from multi-row condition
  table.
raw_text: AND
review_status: parsed
source: *id001
type: AND
```


## Transition `TR_OFF_ACC`

**Raw condition:**
```
PWR_REQ_VALID AND IGN_STS=1 AND NOT NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram: OFF→ACCESSORY
```

**Parsed tree (deterministic parser):**
```yaml
children:
- operator: ==
  parse_status: ok
  raw_condition: PWR_REQ_VALID
  raw_text: PWR_REQ_VALID
  signal: PWR_REQ_VALID
  type: boolean_predicate
  value: '1'
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: IGN_STS=1
  signal: IGN_STS
  type: signal_condition
  value: '1'
  value_domain: boolean
- children:
  - atom_kind: edge_event
    from_state: 'OFF'
    parse_status: partial
    raw_condition: 'NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram:
      OFF→ACCESSORY'
    raw_text: 'NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram:
      OFF→ACCESSORY'
    requires_history: true
    to_state: ACCESSORY
    type: edge_event
  parse_status: partial
  raw_condition: 'NOT NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram:
    OFF→ACCESSORY'
  type: NOT
parse_status: partial
raw_condition: 'PWR_REQ_VALID AND IGN_STS=1 AND NOT NOK_SHUTOFF | T_ACC_CONFIRM=250ms
  | PWR_REQ=1; IGN_STS=1 | Diagram: OFF→ACCESSORY'
type: AND
```


## Transition `TR_ACC_RUN`

**Raw condition:**
```
PWR_REQ_VALID AND GEAR_POS=P AND BATT_OK=1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1 | Diagram: ACCESSORY→RUN
```

**Parsed tree (deterministic parser):**
```yaml
children:
- operator: ==
  parse_status: ok
  raw_condition: PWR_REQ_VALID
  raw_text: PWR_REQ_VALID
  signal: PWR_REQ_VALID
  type: boolean_predicate
  value: '1'
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: GEAR_POS=P
  signal: GEAR_POS
  type: signal_condition
  value: P
  value_domain: literal
- atom_kind: edge_event
  from_state: ACCESSORY
  parse_status: partial
  raw_condition: 'BATT_OK=1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1
    | Diagram: ACCESSORY→RUN'
  raw_text: 'BATT_OK=1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1 |
    Diagram: ACCESSORY→RUN'
  requires_history: true
  to_state: RUN
  type: edge_event
parse_status: partial
raw_condition: 'PWR_REQ_VALID AND GEAR_POS=P AND BATT_OK=1 | T_RUN_CONFIRM=400ms |
  PWR_REQ=1; GEAR_POS=P; BATT_OK=1 | Diagram: ACCESSORY→RUN'
type: AND
```


## Transition `TR_RUN_SHUT`

**Raw condition:**
```
SYS_SHUTOFF AND NOT NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P; VEH_SPD=0 | Diagram: RUN→SHUT_OFF
```

**Parsed tree (deterministic parser):**
```yaml
children:
- operator: ==
  parse_status: ok
  raw_condition: SYS_SHUTOFF
  raw_text: SYS_SHUTOFF
  signal: SYS_SHUTOFF
  type: boolean_predicate
  value: '1'
- children:
  - atom_kind: edge_event
    from_state: RUN
    parse_status: partial
    raw_condition: 'NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P;
      VEH_SPD=0 | Diagram: RUN→SHUT_OFF'
    raw_text: 'NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P;
      VEH_SPD=0 | Diagram: RUN→SHUT_OFF'
    requires_history: true
    to_state: SHUT_OFF
    type: edge_event
  parse_status: partial
  raw_condition: 'NOT NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P;
    VEH_SPD=0 | Diagram: RUN→SHUT_OFF'
  type: NOT
parse_status: partial
raw_condition: 'SYS_SHUTOFF AND NOT NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1;
  IGN_STS=0; GEAR_POS=P; VEH_SPD=0 | Diagram: RUN→SHUT_OFF'
type: AND
```


## Transition `TR_SHUT_OFF`

**Raw condition:**
```
RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF
```

**Parsed tree (deterministic parser):**
```yaml
atom_kind: edge_event
from_state: SHUT_OFF
parse_status: partial
raw_condition: 'RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF
  | Diagram: SHUT_OFF→OFF'
raw_text: 'RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF
  | Diagram: SHUT_OFF→OFF'
requires_history: true
to_state: 'OFF'
type: edge_event
```

**Timing normalizations:**
- `T=1000ms` → `elapsed_time >= 1000ms` (review: True)
  - Equality-style timing in requirements often maps to threshold crossing in tests.
  - Configured default_interpret_equal_time_as: >=
- `TIMEOUT` → `TIMEOUT` (review: True)
  - Pattern matched; manual interpretation needed.

## Transition `TR_FAIL_OFF`

**Raw condition:**
```
T_FAIL_TIMEOUT elapsed OR DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout or diagnostic | Diagram: Any→OFF fallback
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom_kind: timing_condition
  parse_status: ok
  raw_condition: T_FAIL_TIMEOUT elapsed
  raw_text: T_FAIL_TIMEOUT elapsed
  type: timing_condition
- operator: ==
  parse_status: ok
  raw_condition: DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout
  raw_text: DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms | Inject timeout
  timer: null
  type: timing_condition
  value: 80ms | Inject timeout
- atom_kind: edge_event
  from_state: Any
  parse_status: partial
  raw_condition: 'diagnostic | Diagram: Any→OFF fallback'
  raw_text: 'diagnostic | Diagram: Any→OFF fallback'
  requires_history: true
  to_state: OFF fallback
  type: edge_event
parse_status: partial
raw_condition: 'T_FAIL_TIMEOUT elapsed OR DIAG_BLOCKED | 1000ms / T_DIAG_FILTER=80ms
  | Inject timeout or diagnostic | Diagram: Any→OFF fallback'
type: OR
```

**Timing normalizations:**
- `elapsed` → `elapsed` (review: True)
  - Pattern matched; manual interpretation needed.
- `TIMEOUT` → `TIMEOUT` (review: True)
  - Pattern matched; manual interpretation needed.
- `timeout` → `timeout` (review: True)
  - Pattern matched; manual interpretation needed.

## Transition `SM_001`

**Raw condition:**
```
TC_PM_003 | Power Mode Control | Condition B false | Verify shutoff is not triggered when vehicle is not stopped | Given Mode_cmd=1, IGN_SW=0, VehicleSpeed>0, Battery_OK=1; When T_shutdown>=100ms | Mode_STS shall not become 0 due to TR_PM_001 | Negative path
```

**Parsed tree (deterministic parser):**
```yaml
operator: ==
parse_status: ok
raw_condition: TC_PM_003 | Power Mode Control | Condition B false | Verify shutoff
  is not triggered when vehicle is not stopped | Given Mode_cmd=1, IGN_SW=0, VehicleSpeed>0,
  Battery_OK=1; When T_shutdown>=100ms | Mode_STS shall not become 0 due to TR_PM_001
  | Negative path
raw_text: TC_PM_003 | Power Mode Control | Condition B false | Verify shutoff is not
  triggered when vehicle is not stopped | Given Mode_cmd=1, IGN_SW=0, VehicleSpeed>0,
  Battery_OK=1; When T_shutdown>=100ms | Mode_STS shall not become 0 due to TR_PM_001
  | Negative path
timer: null
type: timing_condition
value: 1, IGN_SW=0, VehicleSpeed>0, Battery_OK=1; When T_shutdown>=100ms | Mode_STS
  shall not become 0 due to TR_PM_001 | Negative path
```


## Transition `SM_001`

**Raw condition:**
```
Previous State = NORMAL; Next State = SHUT_OFF
```

**Parsed tree (deterministic parser):**
```yaml
operator: ==
parse_status: ok
raw_condition: Previous State = NORMAL; Next State = SHUT_OFF
raw_text: Previous State = NORMAL; Next State = SHUT_OFF
timer: null
type: timing_condition
value: NORMAL; Next State = SHUT_OFF
```


## Transition `SM_P_001`

**Raw condition:**
```
SHUT_OFF_PERMISSION = Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: SHUT_OFF_PERMISSION = Condition_E
  signal: SHUT_OFF_PERMISSION
  type: signal_condition
  value: Condition_E
  value_domain: literal
- name: Condition_A
  parse_status: partial
  raw_condition: Condition_A
  type: reference
- name: Condition_B
  parse_status: partial
  raw_condition: Condition_B
  type: reference
- children:
  - name: Condition_C
    parse_status: partial
    raw_condition: Condition_C
    type: reference
  - name: Condition_D
    parse_status: partial
    raw_condition: Condition_D
    type: reference
  parse_status: partial
  raw_condition: Condition_C OR Condition_D
  type: OR
parse_status: partial
raw_condition: SHUT_OFF_PERMISSION = Condition_E AND Condition_A AND Condition_B AND
  (Condition_C OR Condition_D)
type: AND
```


## Transition `SM_P_002`

**Raw condition:**
```
RESET_CONDITION = Condition_R1 OR Condition_R2 OR Condition_R3
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: RESET_CONDITION = Condition_R1
  signal: RESET_CONDITION
  type: signal_condition
  value: Condition_R1
  value_domain: literal
- name: Condition_R2
  parse_status: partial
  raw_condition: Condition_R2
  type: reference
- name: Condition_R3
  parse_status: partial
  raw_condition: Condition_R3
  type: reference
parse_status: partial
raw_condition: RESET_CONDITION = Condition_R1 OR Condition_R2 OR Condition_R3
type: OR
```


## Transition `SM_LB_001`

**Raw condition:**
```
Condition_E / Request input active for T_CONFIRM AND Condition_A / Vehicle condition = stationary AND Condition_B / Processing state = IDLE AND (Condition_C / Communication status = NORMAL OR Condition_D / Backup request status = ACTIVE)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- parse_status: partial
  raw_condition: Condition_E / Request input active for T_CONFIRM
  raw_text: Condition_E / Request input active for T_CONFIRM
  type: opaque
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: Condition_A / Vehicle condition = stationary
  signal: Condition_A / Vehicle condition
  type: signal_condition
  value: stationary
  value_domain: literal
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: Condition_B / Processing state = IDLE
  signal: Condition_B / Processing state
  type: signal_condition
  value: IDLE
  value_domain: enum
- children:
  - atom_kind: state_condition
    operator: ==
    parse_status: ok
    raw_condition: Condition_C / Communication status = NORMAL
    signal: Condition_C / Communication status
    type: signal_condition
    value: NORMAL
    value_domain: enum
  - atom_kind: state_condition
    operator: ==
    parse_status: ok
    raw_condition: Condition_D / Backup request status = ACTIVE
    signal: Condition_D / Backup request status
    type: signal_condition
    value: ACTIVE
    value_domain: enum
  parse_status: ok
  raw_condition: Condition_C / Communication status = NORMAL OR Condition_D / Backup
    request status = ACTIVE
  type: OR
parse_status: partial
raw_condition: Condition_E / Request input active for T_CONFIRM AND Condition_A /
  Vehicle condition = stationary AND Condition_B / Processing state = IDLE AND (Condition_C
  / Communication status = NORMAL OR Condition_D / Backup request status = ACTIVE)
type: AND
```


## Transition `SM_D_001`

**Raw condition:**
```
NORMAL → SHUT_OFF
```

**Parsed tree (deterministic parser):**
```yaml
atom_kind: edge_event
from_state: NORMAL
parse_status: partial
raw_condition: NORMAL → SHUT_OFF
raw_text: NORMAL → SHUT_OFF
requires_history: true
to_state: SHUT_OFF
type: edge_event
```


## Transition `SM_P_001`

**Raw condition:**
```
OK_SHUTOFF = TRUE
```

**Parsed tree (deterministic parser):**
```yaml
atom_kind: state_condition
operator: ==
parse_status: ok
raw_condition: OK_SHUTOFF = TRUE
signal: OK_SHUTOFF
type: signal_condition
value: 'TRUE'
value_domain: boolean
```


## Transition `SM_P_002`

**Raw condition:**
```
NOK_SHUTOFF = TRUE
```

**Parsed tree (deterministic parser):**
```yaml
atom_kind: state_condition
operator: ==
parse_status: ok
raw_condition: NOK_SHUTOFF = TRUE
signal: NOK_SHUTOFF
type: signal_condition
value: 'TRUE'
value_domain: boolean
```


## Transition `SM_P_003`

**Raw condition:**
```
RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: RESET_SHUTOFF = TRUE
  signal: RESET_SHUTOFF
  type: signal_condition
  value: 'TRUE'
  value_domain: boolean
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: SHUTOFF_DECISION = FALSE
  signal: SHUTOFF_DECISION
  type: signal_condition
  value: 'FALSE'
  value_domain: boolean
parse_status: ok
raw_condition: RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE
type: OR
```


## Transition `SM_D_001`

**Raw condition:**
```
OK_SHUTOFF = TRUE
```

**Parsed tree (deterministic parser):**
```yaml
atom_kind: state_condition
operator: ==
parse_status: ok
raw_condition: OK_SHUTOFF = TRUE
signal: OK_SHUTOFF
type: signal_condition
value: 'TRUE'
value_domain: boolean
```


## Transition `SM_D_002`

**Raw condition:**
```
NOK_SHUTOFF = TRUE
```

**Parsed tree (deterministic parser):**
```yaml
atom_kind: state_condition
operator: ==
parse_status: ok
raw_condition: NOK_SHUTOFF = TRUE
signal: NOK_SHUTOFF
type: signal_condition
value: 'TRUE'
value_domain: boolean
```


## Transition `SM_D_003`

**Raw condition:**
```
RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: RESET_SHUTOFF = TRUE
  signal: RESET_SHUTOFF
  type: signal_condition
  value: 'TRUE'
  value_domain: boolean
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: SHUTOFF_DECISION = FALSE
  signal: SHUTOFF_DECISION
  type: signal_condition
  value: 'FALSE'
  value_domain: boolean
parse_status: ok
raw_condition: RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE
type: OR
```


## Transition `SM_P_001`

**Raw condition:**
```
OK_SHUTOFF = TRUE
```

**Parsed tree (deterministic parser):**
```yaml
atom_kind: state_condition
operator: ==
parse_status: ok
raw_condition: OK_SHUTOFF = TRUE
signal: OK_SHUTOFF
type: signal_condition
value: 'TRUE'
value_domain: boolean
```


## Transition `SM_P_002`

**Raw condition:**
```
NOK_SHUTOFF = TRUE
```

**Parsed tree (deterministic parser):**
```yaml
atom_kind: state_condition
operator: ==
parse_status: ok
raw_condition: NOK_SHUTOFF = TRUE
signal: NOK_SHUTOFF
type: signal_condition
value: 'TRUE'
value_domain: boolean
```


## Transition `SM_P_003`

**Raw condition:**
```
RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: RESET_SHUTOFF = TRUE
  signal: RESET_SHUTOFF
  type: signal_condition
  value: 'TRUE'
  value_domain: boolean
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: SHUTOFF_DECISION = FALSE
  signal: SHUTOFF_DECISION
  type: signal_condition
  value: 'FALSE'
  value_domain: boolean
parse_status: ok
raw_condition: RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE
type: OR
```


## Transition `SM_D_001`

**Raw condition:**
```
OK_SHUTOFF = TRUE
```

**Parsed tree (deterministic parser):**
```yaml
atom_kind: state_condition
operator: ==
parse_status: ok
raw_condition: OK_SHUTOFF = TRUE
signal: OK_SHUTOFF
type: signal_condition
value: 'TRUE'
value_domain: boolean
```


## Transition `SM_D_002`

**Raw condition:**
```
NOK_SHUTOFF = TRUE
```

**Parsed tree (deterministic parser):**
```yaml
atom_kind: state_condition
operator: ==
parse_status: ok
raw_condition: NOK_SHUTOFF = TRUE
signal: NOK_SHUTOFF
type: signal_condition
value: 'TRUE'
value_domain: boolean
```


## Transition `SM_D_003`

**Raw condition:**
```
RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE
```

**Parsed tree (deterministic parser):**
```yaml
children:
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: RESET_SHUTOFF = TRUE
  signal: RESET_SHUTOFF
  type: signal_condition
  value: 'TRUE'
  value_domain: boolean
- atom_kind: state_condition
  operator: ==
  parse_status: ok
  raw_condition: SHUTOFF_DECISION = FALSE
  signal: SHUTOFF_DECISION
  type: signal_condition
  value: 'FALSE'
  value_domain: boolean
parse_status: ok
raw_condition: RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE
type: OR
```

