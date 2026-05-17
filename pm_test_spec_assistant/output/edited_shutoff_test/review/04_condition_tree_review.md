# Condition tree review

## Transition `TC2_T1_01`

**Raw condition:**
```
((OK_SHUTOFF AND NOT NOK_SHUTOFF) OR (FORCE_SHUTOFF AND CND_FORCE_ALLOWED))
```

**Parsed tree (deterministic parser):**
```yaml
children:
- children:
  - footnotes: []
    id: ref_927a6a4c
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
      id: ref_da0409e0
      name: NOK_SHUTOFF
      raw_text: NOT NOK_SHUTOFF
      source: *id001
      type: condition
    id: not_1cddc834
    raw_text: NOT NOK_SHUTOFF
    source: *id001
    type: NOT
  id: and_bb2fbdf5
  source: *id001
  type: AND
- children:
  - footnotes: []
    id: ref_857cf8ac
    name: FORCE_SHUTOFF
    raw_text: FORCE_SHUTOFF
    source: *id001
    type: condition
  - footnotes: []
    id: ref_ef0e56f1
    name: CND_FORCE_ALLOWED
    raw_text: CND_FORCE_ALLOWED
    source: *id001
    type: condition
  id: and_d278e5c6
  source: *id001
  type: AND
id: or_bbe73796
source: *id001
type: OR
```


## Transition `TC2_T2_01`

**Raw condition:**
```
((CND_REQ_GROUP AND CND_SAFE_GROUP) OR CND_NORMAL_ROUTE OR CND_BACKUP_ROUTE OR (CND_BACKUP_TIMER_OK AND POWER=OFF) OR CND_OUTPUT_READY)
```

**Parsed tree (deterministic parser):**
```yaml
children:
- children:
  - footnotes: []
    id: ref_1197f2aa
    name: CND_REQ_GROUP
    raw_text: CND_REQ_GROUP
    source: &id001
      control: OK_SHUTOFF
      document: edited_Shutoff_Condition_Spec.docx
      file: edited_Shutoff_Condition_Spec.docx
      table: table_2
      table_id: T2_01
    type: condition
  - footnotes: []
    id: ref_7ff91f80
    name: CND_SAFE_GROUP
    raw_text: CND_SAFE_GROUP
    source: *id001
    type: condition
  id: op_f2ce0803
  source: *id001
  type: AND
- children:
  - children:
    - footnotes: []
      id: ref_7566f2dc
      name: CND_NORMAL_ROUTE
      raw_text: CND_NORMAL_ROUTE
      source: *id001
      type: condition
    id: op_402b0500
    raw_text: OR
    source: *id001
    type: OR
  id: op_9d9eb28f
  raw_text: AND
  source: *id001
  type: AND
- children:
  - children:
    - children:
      - footnotes: []
        id: ref_3a395fc9
        name: CND_BACKUP_ROUTE
        raw_text: CND_BACKUP_ROUTE
        source: *id001
        type: condition
      id: op_7b7fbe88
      raw_text: AND
      source: *id001
      type: AND
    id: op_bdf3e388
    raw_text: OR
    source: *id001
    type: OR
  id: op_e3abc411
  raw_text: AND
  source: *id001
  type: AND
- children:
  - children:
    - footnotes: []
      id: ref_07b37bea
      name: CND_BACKUP_TIMER_OK
      raw_text: CND_BACKUP_TIMER_OK
      source: *id001
      type: condition
    - footnotes: []
      id: ref_0834865e
      name: POWER=OFF
      raw_text: POWER=OFF
      source: *id001
      type: condition
    id: and_76966ec1
    raw_text: CND_BACKUP_TIMER_OK AND POWER=OFF
    source: *id001
    type: AND
  id: op_844367e5
  raw_text: OR
  source: *id001
  type: OR
- children:
  - footnotes: []
    id: ref_e74c5cab
    name: CND_OUTPUT_READY
    raw_text: CND_OUTPUT_READY
    source: *id001
    type: condition
  id: op_fa44268a
  raw_text: OR
  source: *id001
  type: OR
id: or_1eb60a2d
parse_status: partial
source: *id001
type: OR
```


## Transition `TC2_T3_01`

**Raw condition:**
```
((REQ_MAIN_OK (*1) AND REQ_STABLE (*4)) OR (REQ_SRC_A_VALID (*2) OR REQ_SRC_B_VALID (*3)))
```

**Parsed tree (deterministic parser):**
```yaml
children:
- children:
  - footnotes:
    - '1'
    id: ref_00c8e581
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
    id: ref_c9c55b50
    name: REQ_STABLE (*4)
    raw_text: REQ_STABLE (*4)
    source: *id001
    type: condition
  id: op_e4f09860
  source: *id001
  type: AND
- children:
  - footnotes:
    - '2'
    id: ref_eebcebf3
    name: REQ_SRC_A_VALID (*2)
    raw_text: REQ_SRC_A_VALID (*2)
    source: *id001
    type: condition
  - footnotes:
    - '3'
    id: ref_a002874a
    name: REQ_SRC_B_VALID (*3)
    raw_text: REQ_SRC_B_VALID (*3)
    source: *id001
    type: condition
  id: op_008b9aa2
  source: *id001
  type: OR
id: or_3901f261
parse_status: partial
source: *id001
type: OR
```


## Transition `TC2_T4_01`

**Raw condition:**
```
((VEHICLE_STOPPED (*1) AND DRIVER_SAFE (*2) AND NOT SAFETY_LOCKED (*5)) OR (PROCESS_IDLE (*3) OR PROCESS_PREPARED (*4)))
```

**Parsed tree (deterministic parser):**
```yaml
children:
- children:
  - footnotes:
    - '1'
    id: ref_06ee92e8
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
    id: ref_831872b6
    name: DRIVER_SAFE (*2)
    raw_text: DRIVER_SAFE (*2)
    source: *id001
    type: condition
  - children:
    - footnotes:
      - '5'
      id: ref_82e443fe
      name: SAFETY_LOCKED (*5)
      raw_text: NOT SAFETY_LOCKED (*5)
      source: *id001
      type: condition
    id: not_de9957a2
    raw_text: NOT SAFETY_LOCKED (*5)
    source: *id001
    type: NOT
  id: op_df4db21a
  source: *id001
  type: AND
- children:
  - footnotes:
    - '3'
    id: ref_8c9afa08
    name: PROCESS_IDLE (*3)
    raw_text: PROCESS_IDLE (*3)
    source: *id001
    type: condition
  - footnotes:
    - '4'
    id: ref_600c0f35
    name: PROCESS_PREPARED (*4)
    raw_text: PROCESS_PREPARED (*4)
    source: *id001
    type: condition
  id: op_917b6d5d
  source: *id001
  type: OR
id: or_fffb62de
parse_status: partial
source: *id001
type: OR
```

