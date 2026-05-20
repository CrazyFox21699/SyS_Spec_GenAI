# M365 Developer Program — Setup ALEX Copilot (step-by-step)

Use this when your **company tenant blocks** app registration and you only have personal Gmail/Outlook. The Dev Program gives you a **sandbox work/school tenant** where you can register your own Azure app.

**Time:** ~30–45 minutes first time  
**Cost:** Free (renewable sandbox)

---

## Part 1 — Join Microsoft 365 Developer Program

> **Update (2025–2026):** Microsoft **no longer grants Instant sandbox automatically** to most new members. Many users never see **Instant sandbox** and instead get *“You don’t currently qualify for a Microsoft 365 Developer Program sandbox subscription.”* This is a **Microsoft policy change**, not an ALEX bug. See **Part 1B — Alternatives** below if sandbox is unavailable.

### 1A — Try Dev Program (may not get sandbox)

1. Open [https://developer.microsoft.com/microsoft-365/dev-program](https://developer.microsoft.com/microsoft-365/dev-program)
2. Click **Join now** / **Start building**
3. Sign in with a **Microsoft account** (Outlook/Hotmail OK for joining)
4. Complete profile (country, goals, phone verification)
5. Open [Developer Program dashboard](https://developer.microsoft.com/en-us/microsoft-365/profile)
6. Look for **Set up E5 subscription** / **Configure sandbox** / **Instant sandbox**

**If sandbox provisions successfully**, you receive email with:
- Admin user `you@yourtenant.onmicrosoft.com`
- Temporary password

7. Sign in to [https://portal.office.com](https://portal.office.com) with that admin account

**If you see “You don’t currently qualify”:** skip to **Part 1B** — use GitHub Copilot (recommended for you) or Azure Free app registration.

### 1B — Alternatives when Instant sandbox is missing

| Path | Effort | M365 Copilot API in ALEX | Good for |
|------|--------|--------------------------|----------|
| **B1 — GitHub Copilot** (you already login OK) | Low | No Graph API; CLI + brief / future auto-fallback | **Reasoning today** |
| **B2 — Azure Free account** | Medium | Unlikely without Copilot license; Client ID + login may work for Graph `/me` only | Register app with personal MS account |
| **B3 — M365 trial / paid dev license** | Paid | Possible if license includes Copilot | Production-like test |
| **B4 — Visual Studio subscription** | If owned | May unlock Dev Program sandbox per Microsoft rules | Check VS Pro/Enterprise linked account |

#### B1 — GitHub Copilot (recommended now)

1. Review tab → **GitHub Copilot CLI** → Login (device flow)
2. **Check connection** → verified
3. Logic tab → **Resolve with AI** (after Phase 0) or **Export brief** → ask in Cursor → **Import knowledge patches**

#### B2 — Azure Free (Client ID only, no sandbox email)

Use when you want to experiment with M365 login UI even without Copilot chat license:

1. [https://azure.microsoft.com/free/](https://azure.microsoft.com/free/) → Start free
2. Sign in with personal Microsoft account → create subscription
3. [https://portal.azure.com](https://portal.azure.com) → **Microsoft Entra ID** → **App registrations** → New registration (`ALEX-local`)
4. **Authentication** → Allow public client flows = Yes
5. Copy **Application (client) ID** → paste in ALEX Review tab
6. **Sign in** at device login with the **same Microsoft account** used for Azure

**Expectation:** Login may succeed for `User.Read`, but **Resolve with AI** may fail with Copilot license / permission errors. Use GitHub Copilot for reasoning.

---

## Part 2 — Register Azure app (Client ID for ALEX)

1. Open [https://portal.azure.com](https://portal.azure.com) — sign in with **sandbox admin** account (same tenant)
2. Search **Microsoft Entra ID** (formerly Azure Active Directory)
3. **App registrations** → **New registration**
4. Fill in:
   | Field | Value |
   |-------|--------|
   | Name | `ALEX-local` |
   | Supported account types | **Accounts in any organizational directory (Multitenant)** *or* **Single tenant** (sandbox only) |
   | Redirect URI | Leave empty for now |

5. Click **Register**
6. Copy **Application (client) ID** (GUID) — you will paste this into ALEX

### Enable public client (device code login)

7. Go to **Authentication** (left menu)
8. **Advanced settings** → **Allow public client flows** → **Yes** → Save
9. Redirect URI optional later for PKCE (future ALEX upgrade)

### API permissions (delegated)

10. **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions**
11. Add at minimum:
    - `User.Read`
    - `openid`, `profile`, `offline_access` (often added via scope string)
12. For Copilot chat API, ALEX also requests beta Copilot scopes — add what Graph shows as available for **Copilot** / chat in your tenant. If unsure, start with defaults in ALEX [`m365_auth.py`](../web/m365_auth.py) `DEFAULT_SCOPES` and adjust after first login error.
13. Click **Grant admin consent for [your sandbox tenant]** (you are admin — one click)

---

## Part 3 — Configure ALEX (ALEX_AI_TMC — your Azure Free app)

You already registered **`ALEX_AI_TMC`**. Use these values in ALEX:

| Field | Value |
|-------|--------|
| Application (client) ID | `6e3eb9f1-7686-4596-b881-f8993295d2e9` |
| Directory (tenant) ID | `e2c3c862-4f82-47ba-a65b-2f475bd4d5c7` |

**Azure portal checklist (do once):**

1. [portal.azure.com](https://portal.azure.com) → **Microsoft Entra ID** → **App registrations** → **ALEX_AI_TMC**
2. **Authentication** → **Allow public client flows** = **Yes** → Save
3. **API permissions** → **Microsoft Graph** → **Delegated** → add **`User.Read`**
4. Click **Grant admin consent for [your directory]** (you are admin on Azure Free)
5. Do **not** add dozens of Graph scopes yet — start with `User.Read` only

**Sign-in procedure (avoid “code expired”):**

1. Start ALEX: `cd pm_test_spec_assistant && source .venv/bin/activate && python run_web.py`
2. Open [http://127.0.0.1:8765](http://127.0.0.1:8765) — hard refresh (Cmd+Shift+R)
3. **Review** tab → paste Client ID + Tenant ID above → **Save**
4. Click **Sign in** **once** — wait for the code panel (do not click Sign in again)
5. On **this Mac**, open [https://microsoft.com/devicelogin](https://microsoft.com/devicelogin) in a **new** tab (avoid old tabs)
6. **Type** the code from ALEX with the keyboard — do **not** scan QR on iPhone (often reuses an old/expired code)
7. Sign in with the **same Microsoft account** you used to create the Azure Free subscription
8. Approve consent if prompted → ALEX top bar should show **M365 · Signed In**

**If login succeeds but Resolve with AI fails:** that is expected on Azure Free without M365 Copilot license — Graph `/me` works; Copilot chat API may return 403. Use GitHub Copilot for reasoning until license is available.

---

## Part 3 (generic) — Configure ALEX

1. Start web UI:
   ```bash
   cd pm_test_spec_assistant
   source .venv/bin/activate
   python run_web.py
   ```
2. Open [http://127.0.0.1:8765](http://127.0.0.1:8765) — hard refresh
3. Go to **Review** tab → **Microsoft 365 Copilot** section
4. Paste **Application (client) ID**
5. **Tenant ID:** use `common` first; if login fails, use your sandbox **Directory (tenant) ID** from Azure → Entra ID → Overview
6. Click **Save** → **Sign in**
7. Browser opens `microsoft.com/devicelogin` — enter the code shown in ALEX
8. Sign in with **sandbox admin** (`you@yourtenant.onmicrosoft.com`), not personal Outlook
9. Top bar should show **M365 Copilot · Signed In · …**

### Config file (optional)

Edit [`config.yaml`](../config.yaml):

```yaml
assist:
  default_provider: m365
  require_m365_login: false   # allow GitHub Copilot fallback when M365 unavailable
  copilot:
    enabled: true             # GitHub Copilot CLI on Review tab
  m365:
    enabled: true
    client_id: ""             # or paste GUID here / use UI local save
    tenant_id: common         # or sandbox tenant GUID
```

---

## Part 4 — Verify Resolve with AI

1. **Load sample package** or upload a spec
2. Run **Review specification**
3. Open **Logic & Definitions** → pick a logic group
4. Add engineer note (e.g. boundary clarification)
5. Click **Resolve with AI**
6. Expected: status shows provider `m365`; candidates update after validation

If M365 fails, with GitHub Copilot logged in on Review tab, ALEX should fall back to **GitHub Copilot CLI** (after provider-routing implementation in plan Phase 0).

---

## Part 5 — Copilot license on sandbox

Sandbox tenants **may not** include full **Microsoft 365 Copilot** license by default.

| Symptom | What to do |
|---------|------------|
| Login OK but Graph Copilot chat returns 403 / license error | Check [Microsoft 365 admin center](https://admin.microsoft.com) → Users → Licenses for Copilot |
| No Copilot license in sandbox | Use **GitHub Copilot** fallback on Review tab; export brief and import patches manually until license available |
| Dev Program FAQ mentions Copilot trials | Follow current Microsoft docs for sandbox Copilot enablement |

---

## Part 6 — GitHub Copilot (your working path today)

You said GitHub Copilot login works — keep it:

1. Review tab → **GitHub Copilot CLI** → **Login** → complete device flow
2. **Check connection** → should show verified
3. Until M365 sandbox Copilot works: use **Export M365 brief** / copy brief → ask in Cursor → **Import knowledge patches**

After Phase 0 implementation: **Resolve with AI** auto-uses GitHub when M365 not signed in.

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| **“Mã bạn nhập đã hết hạn” / code expired** | Click **Sign in once** only. Open a **fresh** devicelogin tab on Mac. **Type** code from ALEX (no iPhone QR). Do not click Sign in again while waiting. Clear M365 settings → Save → retry. |
| Multiple Sign in clicks | Each click starts a **new** device code and **invalidates** the previous one — wait for one flow to finish |
| Old browser tab | Close all `microsoft.com/devicelogin` tabs before starting |
| Wrong tenant | For Azure Free use **Directory (tenant) ID** `e2c3c862-…`, not `common` |
| No Instant sandbox / “You don’t currently qualify” | **Common in 2025–2026** — use **Part 1B** (GitHub Copilot or Azure Free) |
| Needs Client ID | Part 2 or Part 1B-B2 |
| Wrong tenant / app not found | New app registration in **your** tenant; paste new Client ID; clear M365 settings in ALEX |
| Personal @outlook.com rejected | For Azure Free, sign in with the **same account that owns the Azure subscription** |
| Admin consent required | Grant consent in Azure → API permissions (Part 2 step 13) |
| Login OK, Copilot chat 403 | No M365 Copilot license on tenant — use GitHub Copilot fallback |
| Company laptop blocks Azure portal | Use personal browser profile for sandbox setup only |

### Code fixes (P0 — apply in Agent mode)

These changes in ALEX reduce expired-code failures:

1. **`web/m365_auth.py`** — use minimal **device login scopes** only: `openid`, `profile`, `offline_access`, `User.Read` (not full `DEFAULT_SCOPES` with Sites/Mail/Chat)
2. **Cancel stale pending login** on each `login/start` (single-flight)
3. **Do not fallback** from explicit tenant GUID to `common` (use `e2c3c862-…` consistently)
4. **Handle `expired_token`** with clear English/Vietnamese-friendly message
5. **Return `verification_uri_complete`** — link with code pre-filled
6. **`web/static/js/app.js`** — no auto `window.open` on stale tab; show countdown; disable Sign in during poll; abort previous sign-in loop
7. **`POST /api/m365/login/cancel`** — cancel in-flight login on Sign out / new Sign in

After code deploy: hard refresh UI (`app.js?v=59`), restart `run_web.py`, retry Part 3 sign-in steps above.

---

## Related docs

- [ALEX_M365_REASONING_UPGRADE_PLAN.md](./ALEX_M365_REASONING_UPGRADE_PLAN.md) — architecture and auth tiers
- [COPILOT_PROMPTS.md](./COPILOT_PROMPTS.md) — prompt templates
