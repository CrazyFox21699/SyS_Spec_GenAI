#!/usr/bin/env python3
"""Start local web UI: python run_web.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        print("Missing dependencies. Run:")
        print(f"  cd {ROOT}")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    print("Starting ALEX at http://127.0.0.1:8765/")
    print("Press Ctrl+C to stop.")
    uvicorn.run("web.main:app", host="127.0.0.1", port=8765, reload=False)
