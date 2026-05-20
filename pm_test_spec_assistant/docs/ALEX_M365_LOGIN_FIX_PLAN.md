# P0 — M365 Login Fix Plan (ALEX_AI_TMC)

**Status:** Implemented (2026-05-19)

**Goal:** Device-code sign-in completes reliably with your Azure app before any Copilot reasoning work.

**Your app:** `ALEX_AI_TMC`  
- Client ID: `6e3eb9f1-7686-4596-b881-f8993295d2e9`  
- Tenant ID: `e2c3c862-4f82-47ba-a65b-2f475bd4d5c7`

---

## Root cause (expired code)

| Cause | Fix |
|-------|-----|
| Click **Sign in** multiple times | Each `login/start` invalidates previous device code |
| iPhone QR / old devicelogin tab | Use **fresh Mac tab** + **keyboard-enter** code from ALEX |
| 12+ Graph scopes on device flow | Login with **minimal scopes** only (`User.Read` + OIDC) |
| Tenant fallback `common` vs GUID | Keep **explicit tenant GUID** for Azure Free |
| Background poll after new start | Cancel pending on start; single poll loop in UI |

---

## Azure portal (manual — do first)

1. **Authentication** → Allow public client flows = **Yes**
2. **API permissions** → Delegated **`User.Read`** → **Grant admin consent**
3. Confirm app type: **Public client / mobile & desktop**

---

## Code changes (Agent mode)

### 1. `web/m365_auth.py`

- Split `DEVICE_LOGIN_SCOPES` vs `COPILOT_API_SCOPES`
- `_scopes(cfg, for_device_login=True)` for device code only
- `cancel_device_login()` — clear `pending_login.json` on new start / disconnect
- `start_device_login`: cancel first; store `expires_at`, `verification_uri_complete`; no tenant fallback when tenant is GUID
- `poll_device_login`: check expiry; handle `expired_token`, `authorization_declined`, `bad_verification_code`
- `_friendly_auth_error`: expired-code guidance (EN)
- `m365_status`: return `local_client_id`, `local_tenant_id` for form repopulation

### 2. `web/main.py`

- `POST /api/m365/login/cancel` → `m365_auth.cancel_device_login()`

### 3. `web/static/js/app.js`

- `state.m365SignInGeneration` — abort stale poll loops
- `signInM365`: call cancel before start; use `verification_uri_complete` if present; **no** auto `window.open` (user clicks link)
- Countdown `#m365-login-expires` from `expires_in`
- Populate Client ID / Tenant from `loadM365Status()` when `has_local_config`
- Disable Sign in while `m365LoginInProgress`

### 4. Tests — `tests/test_m365_auth.py`

- Device login uses minimal scopes
- Explicit tenant does not fallback
- Expired pending returns failed status

### 5. Cache bust

- `index.html`: `app.js?v=59`

---

## Verification

```bash
cd pm_test_spec_assistant
source .venv/bin/activate
pytest tests/test_m365_auth.py -q
python run_web.py
```

1. Review → Save Client ID + Tenant GUID  
2. Sign in **once** → enter code on Mac  
3. `GET /api/m365/status` → `api_ready: true`, `display_name` set  
4. Optional: token works for `GET https://graph.microsoft.com/v1.0/me`

**Success criteria:** Top bar **M365 · Signed In**; session in `web_data/m365/session.json` (gitignored).

**After login:** Copilot chat (`/copilot/conversations`) may still 403 without license — separate from login P0.

---

## User action to unlock code edits

Switch Cursor to **Agent mode** and say: **"implement M365 login fix plan"** — then all files above will be patched and tested.
