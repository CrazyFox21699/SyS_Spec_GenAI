# ALEX Windows Setup

Use this path for a Windows laptop when Ubuntu and Mac already work.

## Required

- Windows 10 or 11
- Python 3.10+
- The full ALEX repository, not copied single files

## Easiest Setup (CMD / Double Click)

From File Explorer, open the ALEX folder and run:

```text
setup_windows.bat
```

Then start ALEX with:

```text
run_windows.bat
```

Optional check:

```text
verify_windows.bat
```

Open:

```text
http://127.0.0.1:8765/login
```

Default local login:

```text
admin / Alex@2025!
```

Keep the `run_windows.bat` terminal open while using ALEX. Press `Ctrl+C` to stop.

## Git Bash / WSL Setup

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
- `run_windows.bat` also uses `config.local.yaml` by default.
- If M365 Copilot is used, fill `.env` and the M365 values in the same way as Ubuntu.
- If Windows cannot find Python, install Python from python.org, enable "Add python.exe to PATH", reopen the terminal, then run `setup_windows.bat` again.
