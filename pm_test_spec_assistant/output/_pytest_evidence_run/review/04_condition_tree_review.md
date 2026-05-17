# Condition tree review

## Transition `TC2_XL_Test_Pow_SEC_03_01`

**Raw condition:**
```
(PWR_REQ_VALID AND VEHICLE_SAFE AND (NORMAL_ROUTE OR (BACKUP_ROUTE AND T_SHUT_CONFIRM elapsed)) AND NOT NOK_SHUTOFF)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- raw_text: PWR_REQ_VALID
  type: opaque
- raw_text: VEHICLE_SAFE
  type: opaque
- parse_status: ok
  raw_condition: NORMAL_ROUTE OR (BACKUP_ROUTE AND T_SHUT_CONFIRM elapsed)
  raw_text: NORMAL_ROUTE OR (BACKUP_ROUTE AND T_SHUT_CONFIRM elapsed)
  type: timing_condition
- raw_text: NOT NOK_SHUTOFF
  type: opaque
parse_status: partial
raw_condition: PWR_REQ_VALID AND VEHICLE_SAFE AND (NORMAL_ROUTE OR (BACKUP_ROUTE AND
  T_SHUT_CONFIRM elapsed)) AND NOT NOK_SHUTOFF
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
- parse_status: ok
  raw_condition: ENGINE_RUNNING
  raw_text: ENGINE_RUNNING
  type: opaque
- parse_status: ok
  raw_condition: GEAR_NOT_PARK
  raw_text: GEAR_NOT_PARK
  type: opaque
- children:
  - raw_text: DOOR_UNLOCKED
    type: opaque
  - operator: '>'
    signal: VEH_SPD
    type: signal_condition
    value: '0'
  parse_status: partial
  raw_condition: DOOR_UNLOCKED AND VEH_SPD > 0
  type: AND
- parse_status: ok
  raw_condition: DIAG_BLOCKED
  raw_text: DIAG_BLOCKED
  type: opaque
parse_status: partial
raw_condition: (ENGINE_RUNNING OR GEAR_NOT_PARK OR (DOOR_UNLOCKED AND VEH_SPD > 0)
  OR DIAG_BLOCKED)
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
  type: reference
- name: Condition_A
  type: reference
- name: Condition_B
  type: reference
- parse_status: ok
  raw_condition: Condition_C OR Condition_D
  raw_text: Condition_C OR Condition_D
  type: opaque
parse_status: partial
raw_condition: Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)
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
- operator: ==
  signal: Mode_cmd
  type: signal_condition
  value: '2'
- operator: ==
  signal: Battery_OK
  type: signal_condition
  value: '1'
parse_status: partial
raw_condition: Mode_cmd = 2 AND Battery_OK = 1
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
- operator: ==
  parse_status: ok
  raw_condition: Battery_OK = 0
  signal: Battery_OK
  type: signal_condition
  value: '0'
- parse_status: ok
  raw_condition: T_trans exceeded
  raw_text: T_trans exceeded
  type: timing_condition
parse_status: partial
raw_condition: Battery_OK = 0 OR T_trans exceeded
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
- raw_text: Condition_E / System request is active for confirmation time
  type: opaque
- raw_text: Condition_A / Vehicle condition is safe for shutoff
  type: opaque
- raw_text: Condition_A / Processing state is ready
  type: opaque
- parse_status: ok
  raw_condition: Condition_C / Communication status is valid OR Condition_D / External
    fallback request is detected
  raw_text: Condition_C / Communication status is valid OR Condition_D / External
    fallback request is detected
  type: opaque
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
- raw_text: Condition_E / Request input active for T_CONFIRM
  type: opaque
- operator: ==
  signal: Condition_A / Vehicle condition
  type: signal_condition
  value: stationary
- operator: ==
  signal: Condition_B / Processing state
  type: signal_condition
  value: IDLE
- operator: ==
  parse_status: ok
  raw_condition: Condition_C / Communication status = NORMAL OR Condition_D / Backup
    request status = ACTIVE
  raw_text: Condition_C / Communication status = NORMAL OR Condition_D / Backup request
    status = ACTIVE
  timer: null
  type: timing_condition
  value: NORMAL OR Condition_D / Backup request status = ACTIVE
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
- parse_status: ok
  raw_condition: Condition_R1 / System request becomes inactive
  raw_text: Condition_R1 / System request becomes inactive
  type: opaque
- parse_status: ok
  raw_condition: Condition_R1 / Vehicle condition becomes unsafe
  raw_text: Condition_R1 / Vehicle condition becomes unsafe
  type: opaque
- parse_status: ok
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
  type: reference
- name: Condition_A
  type: reference
- name: Condition_B
  type: reference
- parse_status: ok
  raw_condition: Condition_C OR Condition_D
  raw_text: Condition_C OR Condition_D
  type: opaque
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
  parse_status: ok
  raw_condition: Condition_R1
  type: reference
- name: Condition_R2
  parse_status: ok
  raw_condition: Condition_R2
  type: reference
- name: Condition_R3
  parse_status: ok
  raw_condition: Condition_R3
  type: reference
parse_status: partial
raw_condition: Condition_R1 OR Condition_R2 OR Condition_R3
type: OR
```


## Transition `TC2_T1_01`

**Raw condition:**
```
((OK_SHUTOFF = 1 AND NOT NOK_SHUTOFF = (*1)) OR (FORCE_SHUTOFF = 150 AND CND_FORCE_ALLOWED = 0))
```

**Parsed tree (deterministic parser):**
```yaml
children:
- children:
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
        table: table_1
        table_id: T1_01
      value: '1'
    comparator_value: '1'
    confidence: medium
    footnotes: []
    id: ref_a1b7077b
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
      id: ref_dc7a8e49
      issue_status: ok
      name: NOK_SHUTOFF
      parser_reason: Detected as NOT condition because token starts with NOT.
      raw_text: NOT NOK_SHUTOFF = (*1)
      review_status: pending
      source: *id001
      type: condition
    confidence: medium
    id: not_610c2466
    issue_status: ok
    parser_reason: Detected as NOT gate because row text starts with NOT.
    raw_text: NOT NOK_SHUTOFF = (*1)
    review_status: pending
    source: *id001
    type: NOT
  confidence: high
  id: and_b197d5ba
  issue_status: ok
  parser_reason: Two consecutive rows share OR/AND prefix; combined leaves under AND.
  review_status: parsed
  source: *id001
  type: AND
- children:
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
    id: ref_df1b12bb
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
    comparator_value: '0'
    confidence: medium
    footnotes: []
    id: ref_cb14e14e
    issue_status: ok
    name: CND_FORCE_ALLOWED
    parser_reason: Detected as condition reference from row path leaf token.
    raw_text: CND_FORCE_ALLOWED = 0
    review_status: pending
    source: *id001
    type: condition
  confidence: high
  id: and_b54630b3
  issue_status: ok
  parser_reason: Two consecutive rows share OR/AND prefix; combined leaves under AND.
  review_status: parsed
  source: *id001
  type: AND
confidence: high
id: or_400618e2
issue_status: ok
parse_status: ok
parser_reason: Multiple OR/AND row branches detected; combined as OR of AND groups.
review_status: parsed
source: *id001
type: OR
```


## Transition `TC2_T2_01`

**Raw condition:**
```
(CND_REQ_GROUP = 1 AND CND_SAFE_GROUP = 1 AND (CND_NORMAL_ROUTE = 1 OR CND_BACKUP_ROUTE = 1 OR CND_BACKUP_TIMER_OK = 2 OR POWER = OFF OR CND_OUTPUT_READY = 2))
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
      table: table_2
      table_id: T2_01
    value: '1'
  comparator_value: '1'
  confidence: medium
  footnotes: []
  id: ref_df03c9e9
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
  comparator_value: '1'
  confidence: medium
  footnotes: []
  id: ref_04f179d5
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
    comparator_value: '1'
    confidence: medium
    footnotes: []
    id: ref_f0ed68a6
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
      comparator_value: '1'
      confidence: medium
      footnotes: []
      id: ref_13cd77ad
      issue_status: ok
      name: CND_BACKUP_ROUTE
      parser_reason: Detected as condition reference from row path leaf token.
      raw_text: CND_BACKUP_ROUTE = 1
      review_status: pending
      source: *id001
      type: condition
    confidence: high
    id: op_a035ec5b
    issue_status: ok
    parser_reason: Detected `AND` gate at column depth 1 (nesting level 1).
    raw_text: AND
    review_status: parsed
    source: *id001
    type: AND
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
    id: ref_18cfa807
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
      comparator_value: 'OFF'
      confidence: medium
      footnotes: []
      id: ref_196fa6c1
      issue_status: ok
      name: POWER
      parser_reason: Detected as condition reference from row path leaf token.
      raw_text: POWER = OFF
      review_status: pending
      source: *id001
      type: condition
    confidence: high
    id: op_c17e6b36
    issue_status: ok
    parser_reason: Detected `AND` gate at column depth 2 (nesting level 2).
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
    id: ref_d66c2571
    issue_status: ok
    name: CND_OUTPUT_READY
    parser_reason: Detected as condition reference from row path leaf token.
    raw_text: CND_OUTPUT_READY = 2
    review_status: pending
    source: *id001
    type: condition
  confidence: high
  id: or_9984d74e
  issue_status: ok
  parser_reason: Multiple table rows share OR at the same nesting depth; merged into
    one OR group under AND.
  review_status: parsed
  source: *id001
  type: OR
confidence: high
id: and_6a09f9b7
issue_status: ok
parse_status: ok
parser_reason: All rows begin with AND; each row parsed by column depth and combined
  under AND.
review_status: parsed
source: *id001
type: AND
```


## Transition `TC2_T3_01`

**Raw condition:**
```
(REQ_MAIN_OK (*1) AND REQ_STABLE (*4) AND (REQ_SRC_A_VALID (*2) OR REQ_SRC_B_VALID (*3)))
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
      table: table_3
      table_id: T3_01
    value: null
  confidence: medium
  footnotes:
  - '1'
  id: ref_4b104c6d
  issue_status: ok
  name: REQ_MAIN_OK
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: REQ_MAIN_OK (*1)
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
  id: ref_6590b775
  issue_status: ok
  name: REQ_STABLE
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: REQ_STABLE (*4)
  review_status: pending
  source: *id001
  type: condition
- children:
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
    id: ref_aa4b028a
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
    id: ref_2679e743
    issue_status: ok
    name: REQ_SRC_B_VALID
    parser_reason: Detected as condition reference from row path leaf token.
    raw_text: REQ_SRC_B_VALID (*3)
    review_status: pending
    source: *id001
    type: condition
  confidence: high
  id: or_cc358963
  issue_status: ok
  parser_reason: Multiple table rows share OR at the same nesting depth; merged into
    one OR group under AND.
  review_status: parsed
  source: *id001
  type: OR
confidence: high
id: and_18d91826
issue_status: ok
parse_status: ok
parser_reason: All rows begin with AND; each row parsed by column depth and combined
  under AND.
review_status: parsed
source: *id001
type: AND
```


## Transition `TC2_T4_01`

**Raw condition:**
```
(VEHICLE_STOPPED = 2(*1) AND DRIVER_SAFE (*2) AND NOT SAFETY_LOCKED (*5) AND (PROCESS_IDLE (*3) OR PROCESS_PREPARED (*4)))
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
      table: table_4
      table_id: T4_01
    value: '2'
  comparator_value: '2'
  confidence: medium
  footnotes:
  - '1'
  id: ref_63aefe8b
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
  id: ref_525b38ed
  issue_status: ok
  name: DRIVER_SAFE
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: DRIVER_SAFE (*2)
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
    id: ref_82cedba0
    issue_status: ok
    name: SAFETY_LOCKED
    parser_reason: Detected as NOT condition because token starts with NOT.
    raw_text: NOT SAFETY_LOCKED (*5)
    review_status: pending
    source: *id001
    type: condition
  confidence: medium
  id: not_5aa1fc2d
  issue_status: ok
  parser_reason: Detected as NOT gate because row text starts with NOT.
  raw_text: NOT SAFETY_LOCKED (*5)
  review_status: pending
  source: *id001
  type: NOT
- children:
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
    id: ref_6e6fbf82
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
    id: ref_de313db7
    issue_status: ok
    name: PROCESS_PREPARED
    parser_reason: Detected as condition reference from row path leaf token.
    raw_text: PROCESS_PREPARED (*4)
    review_status: pending
    source: *id001
    type: condition
  confidence: high
  id: or_b7c8a1bc
  issue_status: ok
  parser_reason: Multiple table rows share OR at the same nesting depth; merged into
    one OR group under AND.
  review_status: parsed
  source: *id001
  type: OR
confidence: high
id: and_c8b630cb
issue_status: ok
parse_status: ok
parser_reason: All rows begin with AND; each row parsed by column depth and combined
  under AND.
review_status: parsed
source: *id001
type: AND
```


## Transition `TC2_T1_01`

**Raw condition:**
```
((OK_SHUTOFF = 1 AND NOT NOK_SHUTOFF = (*1)) OR (FORCE_SHUTOFF = 150 AND CND_FORCE_ALLOWED = 0))
```

**Parsed tree (deterministic parser):**
```yaml
children:
- children:
  - atom:
      footnote_refs: []
      negated: false
      operator: '='
      raw_text: OK_SHUTOFF = 1
      resolution: resolved
      signal: OK_SHUTOFF
      source: &id001
        control: SHUTOFF_DECISION
        document: edited_Shutoff_Condition_Spec.docx
        file: edited_Shutoff_Condition_Spec.docx
        table: table_1
        table_id: T1_01
      value: '1'
    comparator_value: '1'
    confidence: medium
    footnotes: []
    id: ref_c3589585
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
      id: ref_be1d17be
      issue_status: ok
      name: NOK_SHUTOFF
      parser_reason: Detected as NOT condition because token starts with NOT.
      raw_text: NOT NOK_SHUTOFF = (*1)
      review_status: pending
      source: *id001
      type: condition
    confidence: medium
    id: not_e2453789
    issue_status: ok
    parser_reason: Detected as NOT gate because row text starts with NOT.
    raw_text: NOT NOK_SHUTOFF = (*1)
    review_status: pending
    source: *id001
    type: NOT
  confidence: high
  id: and_8fe5ddc3
  issue_status: ok
  parser_reason: Two consecutive rows share OR/AND prefix; combined leaves under AND.
  review_status: parsed
  source: *id001
  type: AND
- children:
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
    id: ref_cc235960
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
    comparator_value: '0'
    confidence: medium
    footnotes: []
    id: ref_a5101e50
    issue_status: ok
    name: CND_FORCE_ALLOWED
    parser_reason: Detected as condition reference from row path leaf token.
    raw_text: CND_FORCE_ALLOWED = 0
    review_status: pending
    source: *id001
    type: condition
  confidence: high
  id: and_05e146bc
  issue_status: ok
  parser_reason: Two consecutive rows share OR/AND prefix; combined leaves under AND.
  review_status: parsed
  source: *id001
  type: AND
confidence: high
id: or_9795a242
issue_status: ok
parse_status: ok
parser_reason: Multiple OR/AND row branches detected; combined as OR of AND groups.
review_status: parsed
source: *id001
type: OR
```


## Transition `TC2_T2_01`

**Raw condition:**
```
(CND_REQ_GROUP = 1 AND CND_SAFE_GROUP = 1 AND (CND_NORMAL_ROUTE = 1 OR CND_BACKUP_ROUTE = 1 OR CND_BACKUP_TIMER_OK = 2 OR POWER = OFF OR CND_OUTPUT_READY = 2))
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
      table: table_2
      table_id: T2_01
    value: '1'
  comparator_value: '1'
  confidence: medium
  footnotes: []
  id: ref_0b1431ef
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
  comparator_value: '1'
  confidence: medium
  footnotes: []
  id: ref_e98a3c61
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
    comparator_value: '1'
    confidence: medium
    footnotes: []
    id: ref_d94b2e4d
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
      comparator_value: '1'
      confidence: medium
      footnotes: []
      id: ref_137b1e40
      issue_status: ok
      name: CND_BACKUP_ROUTE
      parser_reason: Detected as condition reference from row path leaf token.
      raw_text: CND_BACKUP_ROUTE = 1
      review_status: pending
      source: *id001
      type: condition
    confidence: high
    id: op_52965c5b
    issue_status: ok
    parser_reason: Detected `AND` gate at column depth 1 (nesting level 1).
    raw_text: AND
    review_status: parsed
    source: *id001
    type: AND
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
    id: ref_cea2b651
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
      comparator_value: 'OFF'
      confidence: medium
      footnotes: []
      id: ref_102d2ec8
      issue_status: ok
      name: POWER
      parser_reason: Detected as condition reference from row path leaf token.
      raw_text: POWER = OFF
      review_status: pending
      source: *id001
      type: condition
    confidence: high
    id: op_624864bc
    issue_status: ok
    parser_reason: Detected `AND` gate at column depth 2 (nesting level 2).
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
    id: ref_8245a972
    issue_status: ok
    name: CND_OUTPUT_READY
    parser_reason: Detected as condition reference from row path leaf token.
    raw_text: CND_OUTPUT_READY = 2
    review_status: pending
    source: *id001
    type: condition
  confidence: high
  id: or_d8cb5140
  issue_status: ok
  parser_reason: Multiple table rows share OR at the same nesting depth; merged into
    one OR group under AND.
  review_status: parsed
  source: *id001
  type: OR
confidence: high
id: and_76f35c60
issue_status: ok
parse_status: ok
parser_reason: All rows begin with AND; each row parsed by column depth and combined
  under AND.
review_status: parsed
source: *id001
type: AND
```


## Transition `TC2_T3_01`

**Raw condition:**
```
(REQ_MAIN_OK (*1) AND REQ_STABLE (*4) AND (REQ_SRC_A_VALID (*2) OR REQ_SRC_B_VALID (*3)))
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
      table: table_3
      table_id: T3_01
    value: null
  confidence: medium
  footnotes:
  - '1'
  id: ref_5bea73c2
  issue_status: ok
  name: REQ_MAIN_OK
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: REQ_MAIN_OK (*1)
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
  id: ref_595c6851
  issue_status: ok
  name: REQ_STABLE
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: REQ_STABLE (*4)
  review_status: pending
  source: *id001
  type: condition
- children:
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
    id: ref_cdd7c824
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
    id: ref_8e69051c
    issue_status: ok
    name: REQ_SRC_B_VALID
    parser_reason: Detected as condition reference from row path leaf token.
    raw_text: REQ_SRC_B_VALID (*3)
    review_status: pending
    source: *id001
    type: condition
  confidence: high
  id: or_04c046ad
  issue_status: ok
  parser_reason: Multiple table rows share OR at the same nesting depth; merged into
    one OR group under AND.
  review_status: parsed
  source: *id001
  type: OR
confidence: high
id: and_dcf7928a
issue_status: ok
parse_status: ok
parser_reason: All rows begin with AND; each row parsed by column depth and combined
  under AND.
review_status: parsed
source: *id001
type: AND
```


## Transition `TC2_T4_01`

**Raw condition:**
```
(VEHICLE_STOPPED = 2(*1) AND DRIVER_SAFE (*2) AND NOT SAFETY_LOCKED (*5) AND (PROCESS_IDLE (*3) OR PROCESS_PREPARED (*4)))
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
      table: table_4
      table_id: T4_01
    value: '2'
  comparator_value: '2'
  confidence: medium
  footnotes:
  - '1'
  id: ref_0d727e04
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
  id: ref_0f2ff2f7
  issue_status: ok
  name: DRIVER_SAFE
  parser_reason: Detected as condition reference from row path leaf token.
  raw_text: DRIVER_SAFE (*2)
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
    id: ref_0c249b98
    issue_status: ok
    name: SAFETY_LOCKED
    parser_reason: Detected as NOT condition because token starts with NOT.
    raw_text: NOT SAFETY_LOCKED (*5)
    review_status: pending
    source: *id001
    type: condition
  confidence: medium
  id: not_9368d3c9
  issue_status: ok
  parser_reason: Detected as NOT gate because row text starts with NOT.
  raw_text: NOT SAFETY_LOCKED (*5)
  review_status: pending
  source: *id001
  type: NOT
- children:
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
    id: ref_826cef47
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
    id: ref_7ebaa6f9
    issue_status: ok
    name: PROCESS_PREPARED
    parser_reason: Detected as condition reference from row path leaf token.
    raw_text: PROCESS_PREPARED (*4)
    review_status: pending
    source: *id001
    type: condition
  confidence: high
  id: or_ddc6193f
  issue_status: ok
  parser_reason: Multiple table rows share OR at the same nesting depth; merged into
    one OR group under AND.
  review_status: parsed
  source: *id001
  type: OR
confidence: high
id: and_16ad5ec4
issue_status: ok
parse_status: ok
parser_reason: All rows begin with AND; each row parsed by column depth and combined
  under AND.
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
- raw_text: PWR_REQ_VALID
  type: opaque
- operator: ==
  signal: IGN_STS
  type: signal_condition
  value: '1'
- operator: ==
  raw_text: 'NOT NOK_SHUTOFF | T_ACC_CONFIRM=250ms | PWR_REQ=1; IGN_STS=1 | Diagram:
    OFF→ACCESSORY'
  timer: null
  type: timing_condition
  value: '250ms | PWR_REQ=1; IGN_STS=1 | Diagram: OFF→ACCESSORY'
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
- raw_text: PWR_REQ_VALID
  type: opaque
- operator: ==
  signal: GEAR_POS
  type: signal_condition
  value: P
- operator: ==
  raw_text: 'BATT_OK=1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1 |
    Diagram: ACCESSORY→RUN'
  timer: null
  type: timing_condition
  value: '1 | T_RUN_CONFIRM=400ms | PWR_REQ=1; GEAR_POS=P; BATT_OK=1 | Diagram: ACCESSORY→RUN'
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
- raw_text: SYS_SHUTOFF
  type: opaque
- operator: ==
  raw_text: 'NOT NOK_SHUTOFF | T_SHUT_CONFIRM=300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P;
    VEH_SPD=0 | Diagram: RUN→SHUT_OFF'
  timer: null
  type: timing_condition
  value: '300ms | PWR_REQ=1; IGN_STS=0; GEAR_POS=P; VEH_SPD=0 | Diagram: RUN→SHUT_OFF'
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
operator: ==
parse_status: ok
raw_condition: 'RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF
  | Diagram: SHUT_OFF→OFF'
raw_text: 'RELAY_MAIN feedback = OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF
  | Diagram: SHUT_OFF→OFF'
timer: null
type: timing_condition
value: 'OFF | T_FAIL_TIMEOUT=1000ms | RELAY_MAIN feedback=OFF | Diagram: SHUT_OFF→OFF'
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
- parse_status: ok
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
- parse_status: ok
  raw_condition: 'diagnostic | Diagram: Any→OFF fallback'
  raw_text: 'diagnostic | Diagram: Any→OFF fallback'
  type: opaque
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
- operator: ==
  signal: SHUT_OFF_PERMISSION
  type: signal_condition
  value: Condition_E
- name: Condition_A
  type: reference
- name: Condition_B
  type: reference
- parse_status: ok
  raw_condition: Condition_C OR Condition_D
  raw_text: Condition_C OR Condition_D
  type: opaque
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
- operator: ==
  parse_status: ok
  raw_condition: RESET_CONDITION = Condition_R1
  signal: RESET_CONDITION
  type: signal_condition
  value: Condition_R1
- name: Condition_R2
  parse_status: ok
  raw_condition: Condition_R2
  type: reference
- name: Condition_R3
  parse_status: ok
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
- raw_text: Condition_E / Request input active for T_CONFIRM
  type: opaque
- operator: ==
  signal: Condition_A / Vehicle condition
  type: signal_condition
  value: stationary
- operator: ==
  signal: Condition_B / Processing state
  type: signal_condition
  value: IDLE
- operator: ==
  parse_status: ok
  raw_condition: Condition_C / Communication status = NORMAL OR Condition_D / Backup
    request status = ACTIVE
  raw_text: Condition_C / Communication status = NORMAL OR Condition_D / Backup request
    status = ACTIVE
  timer: null
  type: timing_condition
  value: NORMAL OR Condition_D / Backup request status = ACTIVE
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
parse_status: ok
raw_condition: NORMAL → SHUT_OFF
raw_text: NORMAL → SHUT_OFF
type: opaque
```


## Transition `SM_P_001`

**Raw condition:**
```
OK_SHUTOFF = TRUE
```

**Parsed tree (deterministic parser):**
```yaml
operator: ==
parse_status: ok
raw_condition: OK_SHUTOFF = TRUE
signal: OK_SHUTOFF
type: signal_condition
value: 'TRUE'
```


## Transition `SM_P_002`

**Raw condition:**
```
NOK_SHUTOFF = TRUE
```

**Parsed tree (deterministic parser):**
```yaml
operator: ==
parse_status: ok
raw_condition: NOK_SHUTOFF = TRUE
signal: NOK_SHUTOFF
type: signal_condition
value: 'TRUE'
```


## Transition `SM_P_003`

**Raw condition:**
```
RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE
```

**Parsed tree (deterministic parser):**
```yaml
children:
- operator: ==
  parse_status: ok
  raw_condition: RESET_SHUTOFF = TRUE
  signal: RESET_SHUTOFF
  type: signal_condition
  value: 'TRUE'
- operator: ==
  parse_status: ok
  raw_condition: SHUTOFF_DECISION = FALSE
  signal: SHUTOFF_DECISION
  type: signal_condition
  value: 'FALSE'
parse_status: partial
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
operator: ==
parse_status: ok
raw_condition: OK_SHUTOFF = TRUE
signal: OK_SHUTOFF
type: signal_condition
value: 'TRUE'
```


## Transition `SM_D_002`

**Raw condition:**
```
NOK_SHUTOFF = TRUE
```

**Parsed tree (deterministic parser):**
```yaml
operator: ==
parse_status: ok
raw_condition: NOK_SHUTOFF = TRUE
signal: NOK_SHUTOFF
type: signal_condition
value: 'TRUE'
```


## Transition `SM_D_003`

**Raw condition:**
```
RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE
```

**Parsed tree (deterministic parser):**
```yaml
children:
- operator: ==
  parse_status: ok
  raw_condition: RESET_SHUTOFF = TRUE
  signal: RESET_SHUTOFF
  type: signal_condition
  value: 'TRUE'
- operator: ==
  parse_status: ok
  raw_condition: SHUTOFF_DECISION = FALSE
  signal: SHUTOFF_DECISION
  type: signal_condition
  value: 'FALSE'
parse_status: partial
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
operator: ==
parse_status: ok
raw_condition: OK_SHUTOFF = TRUE
signal: OK_SHUTOFF
type: signal_condition
value: 'TRUE'
```


## Transition `SM_P_002`

**Raw condition:**
```
NOK_SHUTOFF = TRUE
```

**Parsed tree (deterministic parser):**
```yaml
operator: ==
parse_status: ok
raw_condition: NOK_SHUTOFF = TRUE
signal: NOK_SHUTOFF
type: signal_condition
value: 'TRUE'
```


## Transition `SM_P_003`

**Raw condition:**
```
RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE
```

**Parsed tree (deterministic parser):**
```yaml
children:
- operator: ==
  parse_status: ok
  raw_condition: RESET_SHUTOFF = TRUE
  signal: RESET_SHUTOFF
  type: signal_condition
  value: 'TRUE'
- operator: ==
  parse_status: ok
  raw_condition: SHUTOFF_DECISION = FALSE
  signal: SHUTOFF_DECISION
  type: signal_condition
  value: 'FALSE'
parse_status: partial
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
operator: ==
parse_status: ok
raw_condition: OK_SHUTOFF = TRUE
signal: OK_SHUTOFF
type: signal_condition
value: 'TRUE'
```


## Transition `SM_D_002`

**Raw condition:**
```
NOK_SHUTOFF = TRUE
```

**Parsed tree (deterministic parser):**
```yaml
operator: ==
parse_status: ok
raw_condition: NOK_SHUTOFF = TRUE
signal: NOK_SHUTOFF
type: signal_condition
value: 'TRUE'
```


## Transition `SM_D_003`

**Raw condition:**
```
RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE
```

**Parsed tree (deterministic parser):**
```yaml
children:
- operator: ==
  parse_status: ok
  raw_condition: RESET_SHUTOFF = TRUE
  signal: RESET_SHUTOFF
  type: signal_condition
  value: 'TRUE'
- operator: ==
  parse_status: ok
  raw_condition: SHUTOFF_DECISION = FALSE
  signal: SHUTOFF_DECISION
  type: signal_condition
  value: 'FALSE'
parse_status: partial
raw_condition: RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE
type: OR
```

