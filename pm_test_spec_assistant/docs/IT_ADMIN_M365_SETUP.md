# IT Admin — Microsoft 365 Copilot setup for ALEX

Use this checklist when deploying ALEX inside a company tenant.

## Azure app registration

1. Register a **public client** application in Azure Entra ID.
2. Enable **Mobile and desktop flows** (device code / PKCE).
3. Add delegated permissions:
   - `openid`, `profile`, `offline_access`
   - Microsoft Graph: scopes required by your Copilot Chat API entitlement
4. Copy **Application (client) ID** into ALEX Review → M365 sign-in.

## Tenant policy

- Assign **Microsoft 365 Copilot** license to engineers who need in-app API access.
- Personal Microsoft accounts (MSA) cannot call Copilot Chat API — use **Paste from Copilot Web** instead.

## Engineer workflow

1. Sign in on the Review tab (device code on the same Mac).
2. Resolve with AI → review **AI patch review** panel → **Apply selected**.
3. Export audit trail: `GET /api/review/audit-log?job_id=…`

## Security

- Do not commit `config.yaml` secrets or token cache files.
- Run `scripts/sanitize_for_company_deploy.py` before packaging.
