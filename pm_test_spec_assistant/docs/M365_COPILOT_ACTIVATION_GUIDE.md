# M365 Copilot — Activation guide for ALEX

If ALEX shows the banner **"M365 Copilot API not entitled"** or you see this error in the server logs:

```
M365 create conversation failed (400): {"error":{"code":"BadRequest",
 "message":"This API is not supported for MSA accounts
 (no addressUrl for Microsoft.CopilotChat,False)."}}
```

your signed-in account is **not authorised to call the Microsoft 365 Copilot Chat Graph API** (`POST graph.microsoft.com/beta/copilot/conversations`).

This guide explains why, exactly **which license** unblocks the call, how to verify it, and the fallbacks you can use while waiting.

---

## 1. Why the call fails today

Microsoft only routes `Microsoft.CopilotChat` to accounts that satisfy **all** three conditions:

1. The account is a **work or school account** in an Entra ID (Azure AD) tenant — not a personal Microsoft Account (MSA) like `@outlook.com`, `@hotmail.com`, `@live.com`, `@msn.com`. MSA accounts always carry the placeholder tenant id `9188040d-6c67-4c5b-b112-36a304b66dad`.
2. The user has the SKU **`Microsoft 365 Copilot`** assigned (the paid $30/user/month add-on). Free Copilot variants such as `M365_COPILOT_CHAT` (the chat included in Microsoft 365 Business Premium) do **not** unlock the Graph API.
3. Tenant admin has consented to the delegated Graph permissions that ALEX requests (`User.Read`, `Sites.Read.All`, `Mail.Read`, `People.Read.All`, `Chat.Read`, `ChannelMessage.Read.All`, `OnlineMeetingTranscript.Read.All`, `ExternalItem.Read.All`).

If any of these fail you will get either the 400 above (no addressUrl / MSA) or a 401/403/404 with a Copilot license hint.

---

## 2. What to ask IT — copy/paste request

> Subject: **Assign Microsoft 365 Copilot license + tenant admin consent for ALEX**
>
> Hi team,
>
> The ALEX test-spec assistant calls the Microsoft 365 Copilot Chat Graph API (`/copilot/conversations`). For my work account to use that endpoint please:
>
> 1. **Assign me the `Microsoft 365 Copilot` add-on license** (SKU `Microsoft_365_Copilot`). I already have an M365 Business Premium / E3 / E5 base license, so we just need the add-on on top.
> 2. Confirm the Azure AD app registration `<paste-client-id>` (multi-tenant, public client) has **tenant admin consent** for these delegated Graph scopes: `User.Read`, `Sites.Read.All`, `Mail.Read`, `People.Read.All`, `Chat.Read`, `ChannelMessage.Read.All`, `OnlineMeetingTranscript.Read.All`, `ExternalItem.Read.All`, `offline_access`.
> 3. Send me back the **client_id** and **tenant_id** to paste into ALEX → Review tab → M365 Copilot tile.
>
> Verification steps for you are in this guide: `docs/M365_COPILOT_ACTIVATION_GUIDE.md` section 3.
>
> Thanks!

Substitute the placeholder with the value shown in ALEX (Review tab → M365 Copilot tile → "Application (client) ID").

---

## 3. IT verification path (admin steps)

1. Open [Microsoft 365 admin center](https://admin.microsoft.com).
2. **Users → Active users → click the user → Licenses and apps.**
3. Tick **`Microsoft 365 Copilot`** as a separate license line item (it must not be merged into "Business Premium"). Save.
4. Go to [Azure portal → Microsoft Entra ID → App registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/applicationsListBlade) and find the app registration whose client ID matches what ALEX shows.
5. On that app, open **API permissions**. Under *Microsoft Graph (delegated)*, click **Grant admin consent for `<tenant name>`**. The status must turn into a green check for every scope listed in section 2.
6. Confirm under **Authentication** that the app is configured as:
   - **Public client/native** = Yes
   - **Allow public client flows** = Yes (needed for device code login)
   - **Supported account types** = "Accounts in any organizational directory (Any Microsoft Entra ID tenant - Multitenant)" (recommended)

---

## 4. Engineer self-check after IT activates

### 4a. Confirm the SKU is on your account

After signing into ALEX, copy the access token from the M365 session file (`pm_test_spec_assistant/web_data/m365/session.json`, field `access_token`) and run:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://graph.microsoft.com/v1.0/me/licenseDetails \
  | jq '.value[].skuPartNumber'
```

Expected output must include `Microsoft_365_Copilot`. If you only see `SPB`, `ENTERPRISEPREMIUM`, etc. without `Microsoft_365_Copilot`, the add-on was not assigned. ALEX automatically performs this probe at login and stores the result under `copilot_license_skus` in the session, viewable on `/api/m365/status`.

### 4b. Confirm tenant is not the MSA placeholder

```bash
python -c "
import base64, json, sys
tok = open('pm_test_spec_assistant/web_data/m365/session.json').read()
payload = json.loads(tok)['access_token'].split('.')[1]
payload += '=' * (-len(payload) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload))
print('tid =', claims.get('tid'))
print('upn =', claims.get('upn') or claims.get('unique_name'))
"
```

`tid` must **not** equal `9188040d-6c67-4c5b-b112-36a304b66dad`. If it does, you are still signed in with a personal account — sign out (ALEX → Review → M365 Copilot tile → Sign out), then sign back in with the work account.

### 4c. Quick functional probe

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  https://graph.microsoft.com/beta/copilot/conversations
```

A 200/201 with an `id` field means the API is unlocked. Re-run "Resolve with AI" in ALEX.

---

## 5. While you wait — fallbacks already wired in ALEX

ALEX never blocks you on M365 — when the API is not entitled the resolve flow auto-falls back, in this order:

1. **GitHub Copilot CLI** — install [`gh copilot`](https://docs.github.com/copilot/github-copilot-in-the-cli) and run `gh auth login`. Free with any GitHub Copilot subscription (Pro/Business/Enterprise).
2. **Ollama** — start an Ollama daemon locally (`ollama serve`) and pull a code-savvy model (e.g. `ollama pull llama3:8b-instruct-q5_K_M`). Fully offline.
3. **Paste from Copilot Web** — open [https://copilot.microsoft.com](https://copilot.microsoft.com) in a browser (this works for any account including MSA at the free tier), paste the brief from the Knowledge workbench, then copy the JSON answer back into ALEX via the new **"Paste from Copilot Web"** button in the Knowledge workbench. ALEX validates the patches through the same logic-compliance loop as the API path.

The provider chain ALEX uses for `provider=auto` skips `m365` entirely until your account is entitled, so there is no wasted HTTP round-trip.

---

## 6. What ALEX changed under the hood (for the curious)

- [pm_test_spec_assistant/web/m365_auth.py](../web/m365_auth.py): decodes `id_token.tid` at login + refresh, probes `GET /me/licenseDetails`, persists `is_msa` / `has_copilot_license` / `copilot_license_skus` on the session.
- [pm_test_spec_assistant/web/m365_copilot.py](../web/m365_copilot.py): raises a typed `M365CopilotNotEntitledError` when the Graph response matches MSA / no-license hints — no more 500 stack traces.
- [pm_test_spec_assistant/web/ai_provider.py](../web/ai_provider.py): `resolve_knowledge_provider_chain` drops `m365` from the auto chain whenever `is_copilot_chat_entitled()` returns false; `apply_knowledge_m365` translates the typed error into a structured response with a link to this guide.
- [pm_test_spec_assistant/web/main.py](../web/main.py): `/api/m365/status` now reports `copilot_chat_entitled`, `not_entitled_reason`, `entitlement_note`, and `copilot_license_skus`. `/api/review/logic-clarification` passes `activation_guide` to the UI so the banner can deep-link here.
