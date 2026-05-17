# Test spec I/O format (Expected input / output)

ALEX and Copilot should write **machine-readable setup lines** that test engineers and automation can apply directly.

## Expected input (one line per setup step)

Use newline-separated lines:

```
Given: A=1
Given: B=2
Precondition: State ON
```

| Prefix | Meaning |
|--------|---------|
| `Given: SIG=value` | Set signal / variable before the step |
| `Precondition: …` | System state or context (e.g. state machine state) |

Optional timing from `when` may appear as:

```
When: T_DEBOUNCE elapsed
```

## Expected output (one line per check)

```
Then: C=5
Then: Engine=OFF
```

| Prefix | Meaning |
|--------|---------|
| `Then: SIG=value` | Assert signal / variable after the step |

## Rules

- One assignment or assertion per line.
- Use `SIG=value` (no spaces around `=`).
- Keep signal names exactly as in the spec (e.g. `PWR_REQ_VALID`, `MODE_STS`).
- Do not paste raw logic trees, Python dicts, or long prose in these columns.
- Evidence and trace live in **Evidence navigation** (logic / transition links), not in I/O text.

## Example (shutdown)

**Expected input**

```
Precondition: State RUN
Given: PWR_REQ_VALID=1
Given: VEHICLE_SAFE=1
Given: NOK_SHUTOFF=0
```

**Expected output**

```
Then: PWR_STATE=0
Then: RELAY_MAIN=OFF
```
