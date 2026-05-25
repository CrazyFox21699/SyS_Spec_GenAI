"""Analyze worker process for production queue (run: python -m web.worker)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.env_loader import load_dotenv

load_dotenv()

from src.pipeline import run_analyze
from src.utils.config_path import get_config_path
from src.utils.yaml_utils import load_yaml
from web.job_queue import complete, dequeue
from web.job_store import init_db, update_job_record

WEB_DATA = ROOT / "web_data"
OUTPUT = WEB_DATA / "output"
CONFIG_PATH = get_config_path()


def main() -> None:
    cfg = load_yaml(CONFIG_PATH)
    data_root = WEB_DATA
    init_db(data_root, production=True)
    ollama_host = os.environ.get("OLLAMA_HOST", cfg.get("llm", {}).get("base_url", "http://localhost:11434"))
    print(f"ALEX worker started; OLLAMA_HOST={ollama_host}")

    while True:
        item = dequeue(data_root)
        if not item:
            time.sleep(2)
            continue
        job_id, payload = item
        out_dir = OUTPUT / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        update_job_record(job_id, status="running", progress=0, output_dir=str(out_dir))

        def progress(step: str, pct: int) -> None:
            update_job_record(job_id, current_step=step, progress=pct, status="running")

        try:
            from web.metrics import inc, observe_analyze_duration, record_bundle_gate_summary

            inc("alex_analyze_started_total")
            t0 = time.time()
            input_dir = Path(payload.get("input_dir", ""))
            if not input_dir.is_dir():
                raise FileNotFoundError(f"Input directory not found: {input_dir}")
            selected = payload.get("selected_files")
            sel_set = set(selected) if selected else None
            bundle = run_analyze(
                input_dir,
                out_dir,
                CONFIG_PATH,
                force=True,
                selected_files=sel_set,
                progress=progress,
                enable_llm=bool(payload.get("enable_ollama")),
                strict_mode=bool(payload.get("strict_mode", True)),
            )
            summary = bundle.get("summary", {})
            update_job_record(
                job_id,
                status="done",
                progress=100,
                current_step="Ready for review",
                warnings=summary.get("warnings", 0),
                errors=summary.get("errors", 0),
            )
            from web.bundle_store import save_split_bundle
            from web.job_store import upsert_logic_groups

            ver = save_split_bundle(out_dir, bundle)
            update_job_record(job_id, bundle_version=ver)
            groups = [
                {
                    "logic_id": rb.get("id", rb.get("name", "")),
                    "control_name": rb.get("name", ""),
                    "gate_status": rb.get("gate_status", ""),
                    "parse_status": rb.get("parse_status", ""),
                    "unresolved_count": len(rb.get("gaps") or []),
                }
                for rb in bundle.get("resolved_logic_blocks") or []
            ]
            if groups:
                upsert_logic_groups(job_id, groups)
            record_bundle_gate_summary(bundle.get("resolved_logic_blocks") or [])
            observe_analyze_duration(time.time() - t0)
            inc("alex_analyze_completed_total")
        except Exception as exc:  # noqa: BLE001
            from web.metrics import inc

            inc("alex_analyze_failed_total")
            update_job_record(job_id, status="error", error_message=str(exc), current_step="Failed")
        finally:
            complete(data_root, job_id)


if __name__ == "__main__":
    main()
