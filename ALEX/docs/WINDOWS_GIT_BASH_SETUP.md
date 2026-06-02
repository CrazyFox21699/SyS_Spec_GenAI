# ALEX Windows Setup

Use this path for a Windows laptop when Ubuntu and Mac already work.

## Required

- Windows 10 or 11
- Git Bash or WSL
- Python 3.10+
- The full ALEX repository, not copied single files

## First-time setup

```bash
cd ALEX
chmod +x setup_windows.sh run_windows.sh verify_windows.sh
./setup_windows.sh
```

The script creates `.venv`, installs `requirements.txt`, creates local runtime folders, creates `.env` from `.env.example` if needed, and resets the local admin account.

## Verify

```bash
./verify_windows.sh
```

## Run

```bash
./run_windows.sh
```

Open:

```text
http://127.0.0.1:8765/login
```

Default local login:

```text
admin / Alex@2025!
```

## Notes

- `run_windows.sh` uses `config.local.yaml` by default so the Windows laptop can run locally without changing Ubuntu deployment config.
- If M365 Copilot is used, fill `.env` and the M365 values in the same way as Ubuntu.
- If Git Bash cannot find Python, install Python from python.org, enable "Add python.exe to PATH", reopen Git Bash, then run `./setup_windows.sh` again.
