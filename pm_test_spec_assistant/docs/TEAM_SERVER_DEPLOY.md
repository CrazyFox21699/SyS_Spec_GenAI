# ALEX team server deployment (5 engineers)

This guide covers running ALEX on one shared LAN/VPN server for a small engineering team with per-user login, job isolation, and individual Microsoft 365 sign-in.

## Requirements

- Python 3.9+
- Network access from engineer laptops to the server (VLAN / VPN)
- Optional: GPU host or same machine for Ollama
- Azure app registration for M365 Copilot (see [IT_ADMIN_M365_SETUP.md](IT_ADMIN_M365_SETUP.md))

## 1. Install

```bash
cd pm_test_spec_assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure production + team auth

Edit `config.yaml`:

```yaml
deployment:
  mode: production
  host: 0.0.0.0
  port: 8765
team_auth:
  enabled: true
  session_hours: 12
  cookie_secure: false   # set true behind HTTPS reverse proxy
security:
  enabled: true
  require_token: false
assist:
  copilot:
    enabled: false   # GitHub Copilot CLI is single-user per machine
  m365:
    enabled: true
```

Set `assist.m365.client_id` (and tenant if needed) for your Azure app.

## 3. Create team accounts (IT)

```bash
python scripts/create_team_user.py --username alice --role engineer
python scripts/create_team_user.py --username bob --role engineer
python scripts/create_team_user.py --username admin --role admin
```

Passwords are prompted (minimum 8 characters). User database: `web_data/alex_users.db`.

**First admin must be created on the server** (CLI or script) before anyone can sign in. The login page does not offer in-browser account creation.

## 4. Hidden admin console (IT only)

After signing in as admin, open:

`http://<server-ip>:8765/admin`

This page is **not linked** from the main ALEX sidebar. Non-admin users receive 404 if they open the URL.

From `/admin` you can:

- Create engineer accounts
- Reset passwords
- Enable / disable users

## 5. Run services

**Terminal 1 — web UI**

```bash
python run_web.py
```

Open `http://<server-ip>:8765/login` from engineer machines.

**Terminal 2 — analyze worker** (required when `deployment.mode: production`)

```bash
python -m web.worker
```

**Terminal 3 — Ollama** (shared inference)

```bash
ollama serve
```

Ensure `llm.base_url` / `assist.ollama.base_url` point at the Ollama host.

## 5. Per-user behavior

| Resource | Location |
|---|---|
| Login sessions | `web_data/alex_users.db` |
| Uploads | `web_data/uploads/{username}/` |
| Job output | `web_data/output/{username}/{job_id}/` |
| M365 tokens | `web_data/users/{username}/m365/session.json` |

- Engineers see only their own jobs.
- Admins see all jobs.
- Each engineer signs in to M365 separately on the Review tab; Resolve with AI uses that user's token.

## 6. HTTPS (recommended)

Place Nginx or another reverse proxy in front of uvicorn:

- Terminate TLS with an internal certificate
- Set `team_auth.cookie_secure: true`
- Proxy to `127.0.0.1:8765`

Restrict firewall rules to the engineer VLAN.

## 7. Concurrent edits

When two browser tabs save the same job, the second save receives HTTP **409** with *Someone else saved — refresh*. The UI sends `If-Match: {bundle_version}` on save requests.

## 8. Operations

| Task | Command / action |
|---|---|
| Reset password | Admin console `/admin` → Reset password, or CLI `create_team_user.py` |
| Backup | Copy `web_data/output/`, `web_data/uploads/`, `web_data/alex_users.db` |
| Audit | `GET /api/review/audit-log?job_id=...` includes `username` |
| Logs | Worker + uvicorn stdout |

## 9. Limitations (by design)

- No Azure AD SSO (username/password only)
- GitHub Copilot CLI is not multi-user on one server — use M365 per-user + Ollama
- Single uvicorn process (no horizontal scale without shared session store)

## Quick verification

1. Create two engineer accounts.
2. Sign in as user A → run analyze → note job id.
3. Sign in as user B → confirm user A's job is not listed and API returns 403.
4. Each user completes M365 device login independently on Review.
