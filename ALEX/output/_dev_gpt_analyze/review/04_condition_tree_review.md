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
