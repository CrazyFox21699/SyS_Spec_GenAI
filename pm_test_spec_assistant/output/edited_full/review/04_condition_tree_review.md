# Condition tree review

## Transition `TC2_T1_01`

**Raw condition:**
```
(OK_SHUTOFF AND NOT NOK_SHUTOFF AND FORCE_SHUTOFF AND CND_FORCE_ALLOWED)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- children:
  - footnotes: []
    id: ref_88fee9c6
    name: OK_SHUTOFF
    raw_text: OK_SHUTOFF
    source: &id001
      control: SHUTOFF_DECISION
      document: edited_Shutoff_Condition_Spec.docx
      file: edited_Shutoff_Condition_Spec.docx
      table: table_1
      table_id: T1_01
    type: condition
  - children:
    - footnotes: []
      id: ref_43c479be
      name: NOK_SHUTOFF
      raw_text: NOT NOK_SHUTOFF
      source: *id001
      type: condition
    id: not_0c58ed67
    raw_text: NOT NOK_SHUTOFF
    source: *id001
    type: NOT
  - footnotes: []
    id: ref_4a01fae1
    name: FORCE_SHUTOFF
    raw_text: FORCE_SHUTOFF
    source: *id001
    type: condition
  - footnotes: []
    id: ref_742c7f57
    name: CND_FORCE_ALLOWED
    raw_text: CND_FORCE_ALLOWED
    source: *id001
    type: condition
  id: op_7a09a943
  raw_text: AND
  source: *id001
  type: AND
id: op_678bc3e6
parse_status: ok
raw_text: OR
source: *id001
type: OR
```


## Transition `TC2_T2_01`

**Raw condition:**
```
(CND_REQ_GROUP OR CND_SAFE_GROUP OR CND_NORMAL_ROUTE OR CND_BACKUP_ROUTE OR (CND_BACKUP_TIMER_OK AND POWER=OFF) OR CND_OUTPUT_READY)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- children:
  - footnotes: []
    id: ref_e6a16d80
    name: CND_REQ_GROUP
    raw_text: CND_REQ_GROUP
    source: &id001
      control: OK_SHUTOFF
      document: edited_Shutoff_Condition_Spec.docx
      file: edited_Shutoff_Condition_Spec.docx
      table: table_2
      table_id: T2_01
    type: condition
  id: op_8193dd3d
  raw_text: AND
  source: *id001
  type: AND
- children:
  - footnotes: []
    id: ref_2539f40a
    name: CND_SAFE_GROUP
    raw_text: CND_SAFE_GROUP
    source: *id001
    type: condition
  id: op_43890512
  raw_text: AND
  source: *id001
  type: AND
- children:
  - children:
    - footnotes: []
      id: ref_dd9a84fa
      name: CND_NORMAL_ROUTE
      raw_text: CND_NORMAL_ROUTE
      source: *id001
      type: condition
    id: op_75452923
    raw_text: OR
    source: *id001
    type: OR
  id: op_24cbe79a
  raw_text: AND
  source: *id001
  type: AND
- children:
  - children:
    - children:
      - footnotes: []
        id: ref_c00d6705
        name: CND_BACKUP_ROUTE
        raw_text: CND_BACKUP_ROUTE
        source: *id001
        type: condition
      id: op_18643e47
      raw_text: AND
      source: *id001
      type: AND
    id: op_246c393c
    raw_text: OR
    source: *id001
    type: OR
  id: op_a9ca1335
  raw_text: AND
  source: *id001
  type: AND
- children:
  - children:
    - footnotes: []
      id: ref_badbd358
      name: CND_BACKUP_TIMER_OK
      raw_text: CND_BACKUP_TIMER_OK
      source: *id001
      type: condition
    - children:
      - footnotes: []
        id: ref_492f013d
        name: POWER=OFF
        raw_text: POWER=OFF
        source: *id001
        type: condition
      id: op_b7a279c3
      raw_text: AND
      source: *id001
      type: AND
    id: and_65175424
    source: *id001
    type: AND
  id: op_40c8e1b6
  raw_text: OR
  source: *id001
  type: OR
- children:
  - footnotes: []
    id: ref_674e822e
    name: CND_OUTPUT_READY
    raw_text: CND_OUTPUT_READY
    source: *id001
    type: condition
  id: op_769552c8
  raw_text: OR
  source: *id001
  type: OR
id: or_cd8bea20
parse_status: partial
source: *id001
type: OR
```


## Transition `TC2_T3_01`

**Raw condition:**
```
(REQ_MAIN_OK (*1) AND REQ_STABLE (*4) AND (REQ_SRC_A_VALID (*2) OR REQ_SRC_B_VALID (*3)))
```

**Parsed tree (deterministic parser):**
```yaml
children:
- footnotes:
  - '1'
  id: ref_50ce8306
  name: REQ_MAIN_OK (*1)
  raw_text: REQ_MAIN_OK (*1)
  source: &id001
    control: CND_REQ_GROUP
    document: edited_Shutoff_Condition_Spec.docx
    file: edited_Shutoff_Condition_Spec.docx
    table: table_3
    table_id: T3_01
  type: condition
- footnotes:
  - '4'
  id: ref_38d64dc2
  name: REQ_STABLE (*4)
  raw_text: REQ_STABLE (*4)
  source: *id001
  type: condition
- children:
  - footnotes:
    - '2'
    id: ref_53d2dbfc
    name: REQ_SRC_A_VALID (*2)
    raw_text: REQ_SRC_A_VALID (*2)
    source: *id001
    type: condition
  - footnotes:
    - '3'
    id: ref_99b181b3
    name: REQ_SRC_B_VALID (*3)
    raw_text: REQ_SRC_B_VALID (*3)
    source: *id001
    type: condition
  id: op_690acb76
  raw_text: OR
  source: *id001
  type: OR
id: op_b0514031
parse_status: ok
raw_text: AND
source: *id001
type: AND
```


## Transition `TC2_T4_01`

**Raw condition:**
```
(VEHICLE_STOPPED (*1) AND DRIVER_SAFE (*2) AND NOT SAFETY_LOCKED (*5) AND (PROCESS_IDLE (*3) OR PROCESS_PREPARED (*4)))
```

**Parsed tree (deterministic parser):**
```yaml
children:
- footnotes:
  - '1'
  id: ref_e087bb25
  name: VEHICLE_STOPPED (*1)
  raw_text: VEHICLE_STOPPED (*1)
  source: &id001
    control: CND_SAFE_GROUP
    document: edited_Shutoff_Condition_Spec.docx
    file: edited_Shutoff_Condition_Spec.docx
    table: table_4
    table_id: T4_01
  type: condition
- footnotes:
  - '2'
  id: ref_ebe5c3a3
  name: DRIVER_SAFE (*2)
  raw_text: DRIVER_SAFE (*2)
  source: *id001
  type: condition
- children:
  - footnotes:
    - '5'
    id: ref_fd6920ed
    name: SAFETY_LOCKED (*5)
    raw_text: NOT SAFETY_LOCKED (*5)
    source: *id001
    type: condition
  id: not_24a31563
  raw_text: NOT SAFETY_LOCKED (*5)
  source: *id001
  type: NOT
- children:
  - footnotes:
    - '3'
    id: ref_d4fc0630
    name: PROCESS_IDLE (*3)
    raw_text: PROCESS_IDLE (*3)
    source: *id001
    type: condition
  - footnotes:
    - '4'
    id: ref_b022787b
    name: PROCESS_PREPARED (*4)
    raw_text: PROCESS_PREPARED (*4)
    source: *id001
    type: condition
  id: op_183c6133
  raw_text: OR
  source: *id001
  type: OR
id: op_b74c8a86
parse_status: ok
raw_text: AND
source: *id001
type: AND
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

