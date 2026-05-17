# Condition tree review

## Transition `TR_001`

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
- children:
  - name: Condition_C
    parse_status: ok
    raw_condition: Condition_C
    type: reference
  - name: Condition_D
    parse_status: ok
    raw_condition: Condition_D
    type: reference
  parse_status: partial
  raw_condition: (Condition_C OR Condition_D)
  type: OR
parse_status: partial
raw_condition: Condition_E AND Condition_A AND Condition_B AND (Condition_C OR Condition_D)
type: AND
```


## Transition `TR_002`

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


## Transition `TR_003`

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

## Transition `TR_004`

**Raw condition:**
```
Verify shutoff when all mandatory conditions are true and Condition_C is true
```

**Parsed tree (deterministic parser):**
```yaml
children:
- raw_text: Verify shutoff when all mandatory conditions are true
  type: opaque
- raw_text: Condition_C is true
  type: opaque
parse_status: partial
raw_condition: Verify shutoff when all mandatory conditions are true and Condition_C
  is true
type: AND
```


## Transition `TR_005`

**Raw condition:**
```
Verify system does not shut off before timing threshold
```

**Parsed tree (deterministic parser):**
```yaml
parse_status: ok
raw_condition: Verify system does not shut off before timing threshold
raw_text: Verify system does not shut off before timing threshold
type: opaque
```


## Transition `TR_001`

**Raw condition:**
```
Verify shutoff when all mandatory conditions are satisfied and Condition_C branch is true
```

**Parsed tree (deterministic parser):**
```yaml
children:
- raw_text: Verify shutoff when all mandatory conditions are satisfied
  type: opaque
- raw_text: Condition_C branch is true
  type: opaque
parse_status: partial
raw_condition: Verify shutoff when all mandatory conditions are satisfied and Condition_C
  branch is true
type: AND
```


## Transition `TR_002`

**Raw condition:**
```
Verify shutoff when OR branch Condition_D is true
```

**Parsed tree (deterministic parser):**
```yaml
children:
- parse_status: ok
  raw_condition: Verify shutoff when
  raw_text: Verify shutoff when
  type: opaque
- parse_status: ok
  raw_condition: branch Condition_D is true
  raw_text: branch Condition_D is true
  type: opaque
parse_status: partial
raw_condition: Verify shutoff when OR branch Condition_D is true
type: OR
```


## Transition `TR_003`

**Raw condition:**
```
Verify no shutoff before shutdown timer threshold
```

**Parsed tree (deterministic parser):**
```yaml
parse_status: ok
raw_condition: Verify no shutoff before shutdown timer threshold
raw_text: Verify no shutoff before shutdown timer threshold
type: opaque
```


## Transition `TR_004`

**Raw condition:**
```
Verify no shutoff when vehicle speed is not zero
```

**Parsed tree (deterministic parser):**
```yaml
parse_status: ok
raw_condition: Verify no shutoff when vehicle speed is not zero
raw_text: Verify no shutoff when vehicle speed is not zero
type: opaque
```

