# Test reference rows (from spec tables)

| ID | Given | When | Expected |
| --- | --- | --- | --- |
| TC_001 | E=true, A=true, B=true, C=true, D=false | Evaluate permission | SHUT_OFF |
| TC_002 | E=true, A=true, B=true, C=false, D=true | Evaluate permission | SHUT_OFF |
| TC_003 | E=true, A=true, B=true, C=false, D=false | Evaluate permission | Not SHUT_OFF |
| TC_004 | E=false, A=true, B=true, C=true, D=false | Evaluate permission | Not SHUT_OFF |
