# ALEX — Company deployment (clean package)

Use this when moving ALEX from a personal/dev machine to a **company laptop or shared server** with no personal credentials, analysis history, or home-directory paths.

---

## 1. Before you zip (sender — your Mac)

From `pm_test_spec_assistant/`:

```bash
python scripts/sanitize_for_company_deploy.py
```

This removes:

| Location | What it contained |
|----------|-------------------|
| `web_data/m365/` | M365 OAuth tokens, `local_config.json` (Azure client ID) |
| `web_data/output/` | Past analysis jobs, bundles, reasoning sessions |
| `web_data/uploads/` | Spec files you uploaded or copied from samples |
| `web_data/library.yaml` | Library root + absolute file paths on your machine |
| `web_data/copilot_knowledge/` | Temporary Copilot CLI context files |
| `web_data/library_files/` | Files copied in by Library drag-drop |
| `.venv/` | Your local Python env (recipient creates their own) |
| `__pycache__/`, `.pytest_cache/` | Build/cache noise |

Preview without deleting:

```bash
python scripts/sanitize_for_company_deploy.py --dry-run
```

### Do **not** include in the zip (unless IT explicitly wants samples)

| Path | Reason |
|------|--------|
| `../pm_sample_inputs/` | Sample specs — OK for demo, omit if any customer data touched them |
| `.venv/` | Already removed by sanitizer |
| `.git/` | Optional — include only if company uses git clone instead of zip |

### Cannot be cleaned by script (your Mac only)

These live **outside** the project folder. They are **not** copied when you zip `pm_test_spec_assistant/`, but you should know they exist on your machine:

- `~/.copilot/config.json` — GitHub Copilot CLI login
- `gh auth login` session — GitHub CLI
- Browser profile used for ALEX — may remember last `job_id` in localStorage
- `~/.ollama/` — local LLM models

None of these are required for a clean company install.

---

## 2. What is safe in the repo (no secrets by default)

| File | Status |
|------|--------|
| `config.yaml` | `assist.m365.client_id` is empty by default; sanitizer blanks GUIDs if pasted |
| Source code | No embedded API keys |
| `web_data/library.yaml.example` | Empty template — safe to commit |

Credentials appear **only after** someone signs in on the company machine (stored under `web_data/m365/`, gitignored).

---

## 3. Recipient setup (company machine)

### 3.1 Unpack and install

```bash
cd pm_test_spec_assistant
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Optional (only if you will use those features):

```bash
brew install tesseract      # OCR for diagrams
# Ollama: install from https://ollama.com — local only, no cloud account in ALEX
# GitHub Copilot CLI: npm install -g @github/copilot — uses engineer's GitHub login
```

### 3.2 First run — verify clean state

```bash
python run_web.py
```

Open http://127.0.0.1:8765 and check **Review → AI sign-in**:

- **M365:** badge should show **NEEDS CLIENT ID** or **SIGN IN** — not “Signed in as …”
- **GitHub Copilot:** **SIGN IN** until engineer runs Login on that machine

If M365 still shows a personal name, delete `web_data/m365/` and restart.

### 3.3 Company-specific configuration (IT)

1. **M365 (optional):** IT creates Azure app registration → engineer pastes **Application (client) ID** in Review tab → Sign in with **work account**. See [M365_COPILOT_ACTIVATION_GUIDE.md](M365_COPILOT_ACTIVATION_GUIDE.md).
2. **GitHub Copilot CLI (optional):** Engineer runs Login in ALEX with their **company GitHub + Copilot license**.
3. **Ollama (optional):** Local only — `ollama serve` + pull a model; set `llm.model` in `config.yaml` if needed.
4. **No AI:** ALEX runs fully for parse, review, MCDC skeleton, export — AI providers are optional.

### 3.4 Library tab

On first use, pick a **company-local folder** as library root. Do not reuse a `library.yaml` from another machine (paths will be wrong). After sanitize, `library.yaml` is empty.

---

## 4. Verification checklist (recipient / IT)

- [ ] `web_data/m365/` empty or absent before first company login
- [ ] `web_data/output/` empty — no old job IDs
- [ ] `web_data/library.yaml` has `root: ''` and no `/Users/...` paths
- [ ] `config.yaml` → `assist.m365.client_id: ""` unless IT pre-provisions company app ID
- [ ] Web UI M365 tile shows no personal `display_name` until intentional sign-in
- [ ] Zip did not include `.venv` or personal upload folders

---

## 5. Re-sanitize before each handoff

If the same folder is used for demos then handed to another team:

```bash
python scripts/sanitize_for_company_deploy.py
```

Sign out in UI first (M365 **Sign out**, **Clear** client ID) for a clean UX, then run the script.

---

## Related

- [README.md](../README.md) — install and tabs
- [M365_COPILOT_ACTIVATION_GUIDE.md](M365_COPILOT_ACTIVATION_GUIDE.md) — IT license steps
- [M365_DEV_PROGRAM_SETUP.md](M365_DEV_PROGRAM_SETUP.md) — sandbox tenant (if company blocks app registration)
