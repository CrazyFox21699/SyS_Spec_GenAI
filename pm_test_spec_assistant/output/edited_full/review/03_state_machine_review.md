# State machine review (candidates)

Source files: ../pm_sample_inputs/edited_Shutoff_Condition_Spec.docx

- **NORMAL** — None (mode: None)
- **SHUT_OFF** — None (mode: None)

## Transitions (raw extraction)
- `SM_P_001` NORMAL → SHUT_OFF — cond: `OK_SHUTOFF = TRUE`
- `SM_P_002` NORMAL → NORMAL — cond: `NOK_SHUTOFF = TRUE`
- `SM_P_003` NORMAL → SHUT_OFF — cond: `RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE`
- `SM_D_001` NORMAL → SHUT_OFF — cond: `OK_SHUTOFF = TRUE`
- `SM_D_002` NORMAL → NORMAL — cond: `NOK_SHUTOFF = TRUE`
- `SM_D_003` NORMAL → NORMAL — cond: `RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE`
- `SM_D_001` NORMAL → SHUT_OFF — cond: `OK_SHUTOFF = TRUE`
- `SM_D_002` NORMAL → NORMAL — cond: `NOK_SHUTOFF = TRUE`
- `SM_D_003` NORMAL → NORMAL — cond: `RESET_SHUTOFF = TRUE or SHUTOFF_DECISION = FALSE`
