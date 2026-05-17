"""FastAPI web UI for ALEX."""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.exporters.customer_testspec_exporter import (
    build_customer_testspec_preview,
    derive_module_name,
    export_customer_testspec,
)
from src.classifiers.file_classifier import FILE_TYPE_LABELS, PIPELINE_ROLE_BY_FILE_TYPE
from src.parsers.excel_parser import extract_excel_workbook
from src.parsers.excel_parser import peek_excel_text
from src.parsers.image_parser import extract_image_metadata
from src.parsers.pdf_parser import extract_pdf_document, peek_pdf_text
from src.parsers.word_parser import extract_word_document
from src.parsers.word_parser import peek_word_text
from src.pipeline import run_analyze
from web.copilot_bridge import (
    _command_dict,
    get_command as get_copilot_command,
    probe_copilot_cli,
    run_logic_assist,
    start_definition_query_command,
    start_logic_assist_command,
    start_login,
    verify_copilot_access,
)


def _file_type_label(file_type: str) -> str:
    return FILE_TYPE_LABELS.get(file_type, "System Spec")
from src.utils.file_filters import is_ingestible_file, skip_reason
from src.utils.yaml_utils import dump_yaml, load_yaml
from src.utils.feature_flags import app_config, feature_enabled
from web.bundle_helpers import bundle_path_for_job, ensure_enriched_bundle
from web.candidate_mutations import (
    clone_candidate,
    create_blank_candidate,
    sanitize_id,
    soft_delete_candidate,
)
from web.jobs import append_log, create_job, get_job, run_job_background, update_job
from src.engine.condition_resolver import resolve_condition
from src.engine.source_index import build_source_index
from web.llm_assist import (
    apply_engineer_knowledge_with_ollama,
    assist_io_fill_prompt,
    copilot_enabled,
    default_provider,
    llm_enabled_for_assist,
    ollama_status,
    resolve_definition_with_ollama,
    run_assist,
)
from web.review_workbench import (
    build_ai_queue,
    build_capability_summary,
    build_definition_inbox,
    build_evidence_graph,
    build_workbench_summary,
    paginate_workbook_rows,
)

ROOT = Path(__file__).resolve().parent.parent
WEB_DATA = ROOT / "web_data"
UPLOADS = WEB_DATA / "uploads"
OUTPUT = WEB_DATA / "output"
STATIC = Path(__file__).resolve().parent / "static"
CONFIG_PATH = ROOT / "config.yaml"

UPLOADS.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ALEX", version="0.2.0-web")


def _deployment_mode() -> str:
    try:
        return str((load_yaml(CONFIG_PATH).get("deployment") or {}).get("mode", "local"))
    except OSError:
        return "local"


@app.on_event("startup")
def _startup() -> None:
    from web.job_store import init_db

    init_db(WEB_DATA, production=_deployment_mode() == "production")


_prod_cfg = load_yaml(CONFIG_PATH) if CONFIG_PATH.exists() else {}
if _deployment_mode() == "production" or (_prod_cfg.get("security") or {}).get("enabled"):
    from web.security import SecurityMiddleware

    sec = _prod_cfg.get("security") or {}
    app.add_middleware(
        SecurityMiddleware,
        require_token=bool(sec.get("require_token", False)),
        max_upload_mb=int(sec.get("max_upload_mb", 50)),
        rate_limit_per_minute=int(sec.get("rate_limit_per_minute", 120)),
    )

if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

# Session state: file registry + user overrides
_file_registry: dict[str, dict[str, Any]] = {}
_review_overrides: dict[str, dict[str, Any]] = {}
_ENGINEER_DEF_RE = re.compile(r"^\s*([A-Z][A-Z0-9_=]+)\s*[:=]\s*(.+?)\s*$")
_ENGINEER_MEAN_RE = re.compile(r"^\s*([A-Z][A-Z0-9_=]+)\s+(?:means?|is)\s+(.+?)\s*$", re.I)
_ENGINEER_SIG_VAL_RE = re.compile(r"([A-Z][A-Z0-9_=]+)\s*=\s*([^,]+)")
_BULK_MISSING_RE = re.compile(
    r"(?i)(?:"
    r"all\s+(?:of\s+)?(?:the\s+)?(?:remaining|other)\s+"
    r"(?:missing\s+)?(?:definitions?|terms?|signals?)?\s*(?:are\s+)?(?:equal\s+to|=)\s*(.+)"
    r"|all\s+missing\s*=\s*(.+)"
    r"|all\s+missing\s+(?:are\s+)?(?:equal\s+to|=)\s*(.+)"
    r")\s*$"
)
_TEXT_DEF_RE = re.compile(r"^\s*([A-Z][A-Z0-9_=]+)\s*(?::|=|\||\t)\s*(.+?)\s*$")
_TEXT_EXTS = {".txt", ".md", ".json", ".yaml", ".yml", ".cpp", ".h", ".hpp", ".c", ".csv", ".log", ".xml"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}


class AnalyzeRequest(BaseModel):
    selected_files: Optional[list[str]] = None
    use_all_detected: bool = True
    enable_ollama: bool = False
    strict_mode: bool = False
    generate_candidates: bool = True
    input_dir: Optional[str] = None


class FileSelectRequest(BaseModel):
    files: list[dict[str, Any]]


class ReviewUpdateRequest(BaseModel):
    item_type: str
    item_id: str
    review_status: str
    note: Optional[str] = None


class CandidateEditRequest(BaseModel):
    candidate_id: str
    fields: dict[str, Any]


class CopilotAssistRequest(BaseModel):
    logic_id: Optional[str] = None
    mode: str = "single"
    language: str = "EN"
    engineer_note: Optional[str] = None


class LogicClarificationRequest(BaseModel):
    logic_id: str
    note: str = ""
    term: str = ""


class DefinitionQueryRequest(BaseModel):
    logic_id: str
    term: str = ""
    question: str
    note: str = ""


class WorkbookReviewUpdateRequest(BaseModel):
    candidate_id: str
    use_case: Optional[str] = None
    operation: Optional[str] = None
    expected_input: Optional[str] = None
    expected_output: Optional[str] = None
    review_status: Optional[str] = None
    engineer_confirmation_required: Optional[str] = None
    open_questions: Optional[str] = None
    language: str = "EN"


class TestCandidateCreateRequest(BaseModel):
    logic_id: Optional[str] = None
    control_name: Optional[str] = None
    template: str = "blank"


class TestCandidateCloneRequest(BaseModel):
    source_candidate_id: str
    logic_id: Optional[str] = None


def _cfg() -> dict[str, Any]:
    return load_yaml(CONFIG_PATH) if CONFIG_PATH.exists() else {}


def _require_feature(name: str) -> None:
    if not feature_enabled(_cfg(), name, default=False):
        raise HTTPException(403, f"Feature '{name}' is disabled in config.yaml")


def _list_uploaded_files() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in sorted(UPLOADS.iterdir()):
        if not p.is_file() or not is_ingestible_file(p):
            continue
        key = str(p.resolve())
        reg = _file_registry.get(key, {})
        stat = p.stat()
        ft = reg.get("file_type", "system_spec")
        rows.append(
            {
                "path": key,
                "name": p.name,
                "file_type": ft,
                "file_type_label": reg.get("file_type_label") or _file_type_label(ft),
                "role": reg.get("role", "system_spec"),
                "reason": reg.get("reason", []),
                "selected": reg.get("selected", True),
                "modified": stat.st_mtime,
                "modified_label": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "size": stat.st_size,
            }
        )
    return rows


def _classify_uploads() -> list[dict[str, Any]]:
    from src.classifiers.file_classifier import classify_file

    cfg = load_yaml(CONFIG_PATH)
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for p in UPLOADS.iterdir():
        if not p.is_file():
            continue
        if not is_ingestible_file(p):
            skipped.append({"file": p.name, "reason": skip_reason(p) or "skipped"})
            continue
        r = classify_file(p, cfg)
        key = str(p.resolve())
        prev = _file_registry.get(key, {})
        row = {
            "path": key,
            "name": p.name,
            "file_type": r.file_type,
            "file_type_label": r.file_type_label,
            "role": r.role,
            "reason": r.reason,
            "selected": prev.get("selected", True),
            "user_confirmation_suggested": r.user_confirmation_suggested,
        }
        _file_registry[key] = row
        rows.append(row)
    return rows


def _bundle_for_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if job and job.bundle:
        return ensure_enriched_bundle(job.bundle)
    if job and job.output_dir:
        from web.bundle_store import load_split_bundle

        split = load_split_bundle(Path(job.output_dir))
        if split:
            return ensure_enriched_bundle(split)
    disk = bundle_path_for_job(OUTPUT, job_id)
    if disk:
        return ensure_enriched_bundle(load_yaml(disk))
    if job and job.output_dir:
        path = Path(job.output_dir) / "ui_bundle.yaml"
        if path.exists():
            return ensure_enriched_bundle(load_yaml(path))
    if job:
        raise HTTPException(404, "No analysis bundle yet — wait for review to finish")
    raise HTTPException(404, f"Job not found: {job_id}")


def _save_bundle_to_job(job_id: str, bundle: dict[str, Any]) -> None:
    bundle = ensure_enriched_bundle(bundle)
    job = get_job(job_id)
    out_dir = Path(job.output_dir) if job and job.output_dir else OUTPUT / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    dump_yaml(out_dir / "ui_bundle.yaml", bundle)
    if job:
        update_job(job_id, bundle=bundle)


def _safe_file_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser().resolve()
    allowed_roots = [ROOT.resolve(), UPLOADS.resolve(), OUTPUT.resolve()]
    if not any(path.is_relative_to(root) for root in allowed_roots):
        raise HTTPException(403, "File path is outside the review workspace")
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "File not found")
    return path


def _extract_engineer_definitions(
    note: str,
    logic_id: str,
    focus_term: str = "",
    *,
    missing_terms: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Parse engineer clarification into per-signal definitions.

    Supports:
    - One per line: CND_NORMAL_ROUTE = 1
    - Comma-separated: CND_NORMAL_ROUTE=1, CND_BACKUP_ROUTE=0
    - Bulk: all remaining missing definitions are equal to 100
    """
    defs: dict[str, dict[str, Any]] = {}
    missing = [str(t).strip() for t in (missing_terms or []) if str(t).strip()]
    focus = focus_term.strip()
    assigned: set[str] = set()

    def add_def(name: str, definition: str) -> None:
        nm = name.strip()
        body = definition.strip()
        if not nm or not body:
            return
        if nm.upper() == "SIG" and focus:
            nm = focus
        defs[nm] = {"name": nm, "definition": body, "logic_id": logic_id}
        assigned.add(nm)

    def apply_bulk(value: str) -> None:
        val = value.strip()
        if not val or not missing:
            return
        for term in missing:
            if term in assigned:
                continue
            if focus and term == focus:
                continue
            add_def(term, f"= {val}")

    text = (note or "").strip()
    if not text:
        return defs

    for line in text.splitlines():
        chunk = line.strip()
        if not chunk or chunk.startswith("#"):
            continue
        bulk = _BULK_MISSING_RE.search(chunk)
        if bulk:
            val = next((g for g in bulk.groups() if g), "")
            apply_bulk(val)
            continue
        for m in _ENGINEER_SIG_VAL_RE.finditer(chunk):
            add_def(m.group(1), m.group(2))
        m = _ENGINEER_DEF_RE.match(chunk)
        if m:
            add_def(m.group(1), m.group(2))
            continue
        m = _ENGINEER_MEAN_RE.match(chunk)
        if m:
            add_def(m.group(1), m.group(2))

    bulk_full = _BULK_MISSING_RE.search(text)
    if bulk_full:
        val = next((g for g in bulk_full.groups() if g), "")
        apply_bulk(val)

    for m in _ENGINEER_SIG_VAL_RE.finditer(text):
        add_def(m.group(1), m.group(2))

    if focus and focus not in defs:
        # Plain prose for the focused term only (no SIG= pattern matched).
        leftover = text
        for name in assigned:
            leftover = re.sub(rf"(?i)\b{re.escape(name)}\s*=\s*[^,]+", "", leftover)
        leftover = _BULK_MISSING_RE.sub("", leftover).strip(" ,/\n")
        if _BULK_MISSING_RE.search(text) or not leftover or leftover.lower().startswith("all missing"):
            leftover = ""
        if leftover and not _ENGINEER_SIG_VAL_RE.search(leftover):
            add_def(focus, leftover)

    return defs


def _apply_engineer_knowledge(
    bundle: dict[str, Any],
    logic_id: str,
    note: str,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    from src.engine.engineer_rules import dedupe_logic_block_given

    if llm_enabled_for_assist(cfg):
        out = apply_engineer_knowledge_with_ollama(
            bundle, cfg, logic_id=logic_id, engineer_note=note
        )
        if out.get("ok"):
            return {
                "provider": "ollama",
                "candidates_updated": out.get("candidates_updated", 0),
            }
        return {
            "provider": "ollama",
            "candidates_updated": dedupe_logic_block_given(bundle, logic_id),
            "error": out.get("error"),
        }
    return {
        "provider": "none",
        "candidates_updated": dedupe_logic_block_given(bundle, logic_id),
    }


def _missing_definition_terms(bundle: dict[str, Any], logic_id: str) -> list[str]:
    from web.review_workbench import build_definition_inbox

    try:
        inbox = build_definition_inbox(bundle, logic_id)
    except KeyError:
        return []
    return [
        str(row.get("term") or "")
        for row in inbox.get("terms") or []
        if row.get("resolution") == "missing_definition"
    ]


def _extract_text_definitions(text: str, source_name: str, logic_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, line in enumerate((text or "").splitlines(), start=1):
        m = _TEXT_DEF_RE.match(line)
        if not m:
            continue
        rows.append(
            {
                "name": m.group(1).strip(),
                "definition": m.group(2).strip(),
                "logic_id": logic_id,
                "source": {
                    "file": source_name,
                    "table": f"logic_attachment:{logic_id}",
                    "row": idx,
                },
            }
        )
    return rows


def _extract_supplemental_definitions(path: Path, logic_id: str) -> list[dict[str, Any]]:
    ext = path.suffix.lower()
    try:
        if ext in {".xlsx", ".xlsm"}:
            cfg = load_yaml(CONFIG_PATH)
            state_patterns = cfg.get("classification", {}).get("state_name_patterns", [])
            workbook = extract_excel_workbook(path, state_patterns)
            rows = workbook.get("condition_definitions", [])
        elif ext == ".docx":
            rows = extract_word_document(path).get("condition_definitions", [])
        elif ext == ".pdf":
            rows = extract_pdf_document(path).get("condition_definitions", [])
        elif ext in _IMAGE_EXTS:
            rows = extract_image_metadata(path).get("condition_definitions", [])
        elif ext in _TEXT_EXTS:
            text = path.read_text(encoding="utf-8", errors="replace")
            rows = _extract_text_definitions(text, path.name, logic_id)
        else:
            rows = []
    except Exception:
        rows = []

    normalized: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        definition = str(row.get("definition") or "").strip()
        if not name or not definition:
            continue
        source = dict(row.get("source") or {})
        source.setdefault("file", path.name)
        source.setdefault("table", f"logic_attachment:{logic_id}")
        normalized.append(
            {
                "name": name,
                "definition": definition,
                "logic_id": logic_id,
                "source": source,
            }
        )
    return normalized


def _attachment_dir(job_id: str, logic_id: str) -> Path:
    return OUTPUT / job_id / "logic_attachments" / logic_id


def _build_attachment_preview(path: Path) -> tuple[str, str]:
    ext = path.suffix.lower()
    try:
        if ext in _TEXT_EXTS:
            return ("text", path.read_text(encoding="utf-8", errors="replace")[:4000])
        if ext == ".docx":
            return ("docx", peek_word_text(path, 4000))
        if ext == ".pdf":
            blob = extract_pdf_document(path)
            text = "\n".join(page.get("text", "") for page in blob.get("pages", []))
            if not text.strip():
                text = "\n".join(row.get("ocr_text", "") for row in blob.get("image_analyses", []))
            return ("pdf", text[:4000] or "No PDF text layer or OCR text available.")
        if ext in {".xlsx", ".xlsm"}:
            text, sheets = peek_excel_text(path, 4000)
            prefix = f"Sheets: {', '.join(sheets[:6])}\n" if sheets else ""
            return ("excel", prefix + text)
        if ext in _IMAGE_EXTS:
            meta = extract_image_metadata(path)
            preview = meta.get("ocr_text") or meta.get("note") or json.dumps(meta, ensure_ascii=False)
            return ("image", preview[:4000])
    except Exception as exc:  # noqa: BLE001
        return ("unknown", f"Preview unavailable: {exc}")
    return ("binary", f"Binary attachment stored at {path.name}.")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html_path = STATIC / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>ALEX</h1><p>static/index.html missing</p>")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/projects")
def api_projects() -> dict[str, Any]:
    default = (ROOT / "config.yaml")
    cfg = load_yaml(default) if default.exists() else {}
    sample = ROOT.parent / "pm_sample_inputs" / "input"
    return {
        "projects": [
            {"id": "uploads", "label": "Uploaded files", "path": str(UPLOADS)},
            {"id": "sample", "label": "Sample inputs", "path": str(sample) if sample.is_dir() else None},
        ],
        "default_input": cfg.get("ui", {}).get("default_input_dir"),
    }


@app.post("/api/upload")
async def api_upload(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    saved = []
    replaced = []
    rejected = []
    for uf in files:
        name = Path(uf.filename or "upload.bin").name
        dest = UPLOADS / name
        if not is_ingestible_file(dest):
            rejected.append({"file": name, "reason": skip_reason(dest) or "rejected"})
            continue
        if dest.exists():
            replaced.append(dest.name)
        dest.write_bytes(await uf.read())
        saved.append(dest.name)
    classified = _classify_uploads()
    return {"saved": saved, "replaced": replaced, "rejected": rejected, "files": classified}


@app.post("/api/classify")
def api_classify() -> dict[str, Any]:
    skipped_list: list[dict[str, str]] = []
    for p in UPLOADS.iterdir():
        if p.is_file() and not is_ingestible_file(p):
            skipped_list.append({"file": p.name, "reason": skip_reason(p) or "skipped"})
    return {"files": _classify_uploads(), "skipped": skipped_list}


@app.get("/api/files")
def api_files() -> dict[str, Any]:
    if not _file_registry:
        _classify_uploads()
    files = _list_uploaded_files()
    selected = sum(1 for f in files if f.get("selected"))
    return {
        "files": files,
        "selected_count": selected,
        "total_count": len(files),
    }


@app.post("/api/files/clear")
def api_files_clear() -> dict[str, Any]:
    removed = []
    for p in list(UPLOADS.iterdir()):
        if p.is_file():
            p.unlink(missing_ok=True)
            removed.append(p.name)
    _file_registry.clear()
    return {"ok": True, "removed": removed, "files": []}


_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}


def _role_for_file_type(file_type: str, path: str) -> str:
    ext = Path(path).suffix.lower()
    if file_type == "system_spec" and ext in _IMAGE_EXT:
        return "diagram"
    return PIPELINE_ROLE_BY_FILE_TYPE.get(file_type, "system_spec")


@app.post("/api/files/select")
def api_files_select(body: FileSelectRequest) -> dict[str, Any]:
    for f in body.files:
        key = f.get("path")
        if not key:
            continue
        ft = f.get("file_type", "system_spec")
        row = {
            **f,
            "file_type": ft,
            "file_type_label": f.get("file_type_label") or _file_type_label(ft),
            "role": _role_for_file_type(ft, key),
        }
        if key in _file_registry:
            row["selected"] = f.get("selected", _file_registry[key].get("selected", True))
            _file_registry[key].update(row)
        else:
            _file_registry[key] = row
    files = _list_uploaded_files()
    return {
        "files": files,
        "selected_count": sum(1 for x in files if x.get("selected")),
        "total_count": len(files),
    }


@app.get("/metrics")
def api_metrics() -> Any:
    from fastapi.responses import PlainTextResponse
    from web.metrics import render_prometheus

    return PlainTextResponse(render_prometheus(), media_type="text/plain; version=0.0.4")


@app.get("/api/jobs")
def api_list_jobs() -> dict[str, Any]:
    """List completed analysis jobs (persisted on disk — survives server restart)."""
    jobs: list[dict[str, Any]] = []
    if _deployment_mode() == "production":
        try:
            from web.job_store import list_jobs

            for rec in list_jobs(limit=20):
                jobs.append(
                    {
                        "job_id": rec.job_id,
                        "status": rec.status,
                        "progress": rec.progress,
                        "created": rec.created_at,
                    }
                )
        except RuntimeError:
            pass
    if OUTPUT.is_dir():
        for d in sorted(OUTPUT.iterdir(), reverse=True):
            if not d.is_dir() or not d.name.startswith("analysis_"):
                continue
            bundle_path = d / "ui_bundle.yaml"
            if not bundle_path.exists():
                continue
            try:
                b = ensure_enriched_bundle(load_yaml(bundle_path))
                jobs.append(
                    {
                        "job_id": d.name,
                        "summary": b.get("summary", {}),
                        "understanding_percent": b.get("spec_understanding", {})
                        .get("overall", {})
                        .get("understanding_percent"),
                        "created": d.name.split("_")[1] if "_" in d.name else "",
                    }
                )
            except Exception:  # noqa: BLE001
                continue
    return {"jobs": jobs[:20]}


@app.post("/api/analyze")
def api_analyze(body: AnalyzeRequest) -> dict[str, Any]:
    input_dir = Path(body.input_dir) if body.input_dir else UPLOADS
    if not input_dir.is_dir():
        raise HTTPException(400, f"Input directory not found: {input_dir}")

    ingestible = [p for p in input_dir.iterdir() if p.is_file() and is_ingestible_file(p)]
    if not ingestible:
        raise HTTPException(
            400,
            "No ingestible files in uploads. Use Load sample package or upload .docx/.xlsx (not Word lock files ~$).",
        )

    job = create_job()
    out_dir = OUTPUT / job.job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    update_job(job.job_id, output_dir=out_dir)

    selected: Optional[set[str]] = None
    if not body.use_all_detected:
        if body.selected_files:
            selected = set(body.selected_files)
        else:
            selected = {f["path"] for f in _list_uploaded_files() if f.get("selected")}

    def run(progress_cb):
        return run_analyze(
            input_dir.resolve(),
            out_dir,
            CONFIG_PATH,
            force=True,
            selected_files=selected,
            progress=progress_cb,
            strict_mode=body.strict_mode,
            enable_llm=body.enable_ollama,
        )

    queue_payload = {
        "input_dir": str(input_dir.resolve()),
        "enable_ollama": body.enable_ollama,
        "strict_mode": body.strict_mode,
        "selected_files": sorted(selected) if selected else None,
    }
    run_job_background(
        job.job_id,
        run,
        use_queue=_deployment_mode() == "production",
        queue_payload=queue_payload,
    )
    return {"job_id": job.job_id, "status": "started"}


def _normalize_job_status(status: str) -> str:
    """Frontend expects completed / failed / running / waiting."""
    if status in ("done", "completed"):
        return "completed"
    if status in ("error", "failed"):
        return "failed"
    return status


@app.get("/api/analysis/status")
def api_analysis_status(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if job:
        return {
            "job_id": job.job_id,
            "status": _normalize_job_status(job.status),
            "current_step": job.current_step,
            "progress": job.progress,
            "warnings": job.warnings,
            "errors": job.errors,
            "log": job.log[-30:],
            "error_message": job.error_message,
        }
    disk = bundle_path_for_job(OUTPUT, job_id)
    if disk:
        b = ensure_enriched_bundle(load_yaml(disk))
        s = b.get("summary", {})
        return {
            "job_id": job_id,
            "status": "completed",
            "current_step": "Ready for review",
            "progress": 100,
            "warnings": s.get("warnings", 0),
            "errors": s.get("errors", 0),
            "log": ["Loaded from saved review on disk."],
            "error_message": None,
        }
    raise HTTPException(404, "Job not found")


@app.get("/api/review/signals")
def api_signals(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {"signals": b.get("signals", [])}


@app.get("/api/review/states")
def api_states(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {
        "states": b.get("states", []),
        "transitions": b.get("transitions", []),
        "diagram_semantics": b.get("diagram_semantics", {}),
        "diagrams": b.get("diagrams", []),
    }


@app.get("/api/files/preview")
def api_file_preview(path: str) -> FileResponse:
    file_path = _safe_file_path(path)
    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(file_path, filename=file_path.name, media_type=media_type or "application/octet-stream")


@app.get("/api/review/conditions")
def api_conditions(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {"condition_trees": b.get("condition_trees", [])}


@app.get("/api/review/logic-blocks")
def api_logic_blocks(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {"logic_blocks": b.get("logic_blocks", [])}


@app.get("/api/review/condition-definitions")
def api_condition_definitions(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {
        "condition_definitions": b.get("condition_definitions", []),
        "test_reference_rows": b.get("test_reference_rows", []),
    }


@app.get("/api/review/timing")
def api_timing(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {"timing_constraints": b.get("timing_constraints", [])}


@app.get("/api/review/traceability")
def api_traceability(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {
        "traceability": b.get("traceability", {}),
        "test_candidates": b.get("test_candidates", []),
        "traceability_matrix": b.get("traceability_matrix", []),
    }


@app.get("/api/review/two-column-rows")
def api_two_column_rows(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {"two_column_tables": b.get("two_column_tables", [])}


@app.get("/api/review/logic-tree")
def api_logic_tree(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {
        "logic_tree_views": b.get("logic_tree_views", []),
        "logic_blocks": b.get("logic_blocks", []),
        "logic_ast_rows": b.get("logic_ast_rows", []),
    }


@app.get("/api/review/logic-review")
def api_logic_review(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {
        "logic_review_items": b.get("logic_review_items", []),
        "logic_blocks": b.get("logic_blocks", []),
        "term_roles": b.get("term_roles") or {},
        "ai_assists": b.get("ai_assists", {}),
        "ai_queue": build_ai_queue(b),
    }


@app.get("/api/review/workbench")
def api_review_workbench(
    job_id: str,
    language: str = "EN",
    q: str = "",
    page: int = 1,
    page_size: int = 0,
    issues_only: bool = False,
) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    preview = build_customer_testspec_preview(b, language=language)
    rows, pagination = paginate_workbook_rows(
        preview["rows"],
        q=q,
        page=page,
        page_size=page_size,
        issues_only=issues_only,
    )
    return {
        "job_id": job_id,
        "language": language.upper(),
        "module_name": derive_module_name(b),
        "headers": preview["headers"],
        "rows": rows,
        "pagination": pagination,
        "validation_summary": preview.get("validation_summary"),
        "summary": build_workbench_summary(b, language=language),
    }


@app.get("/api/review/source-index")
def api_review_source_index(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    idx = b.get("source_index") or build_source_index(b)
    return {"job_id": job_id, "source_index": idx}


@app.get("/api/review/condition-resolve")
def api_review_condition_resolve(
    job_id: str,
    term: str,
    logic_id: str = "",
) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {"job_id": job_id, **resolve_condition(b, term, logic_id=logic_id)}


@app.get("/api/llm/status")
def api_llm_status() -> dict[str, Any]:
    cfg = _cfg()
    return {
        "default_provider": default_provider(cfg),
        "enabled": llm_enabled_for_assist(cfg),
        "copilot_enabled": copilot_enabled(cfg),
        "ollama": ollama_status(cfg),
    }


class AssistImproveIoRequest(BaseModel):
    candidate_id: str
    expected_input: str = ""
    expected_output: str = ""
    issues: list[dict[str, Any]] = []


@app.post("/api/assist/improve-io")
def api_assist_improve_io(body: AssistImproveIoRequest, job_id: str) -> dict[str, Any]:
    cfg = _cfg()
    prompt = assist_io_fill_prompt(
        candidate_id=body.candidate_id,
        expected_input=body.expected_input,
        expected_output=body.expected_output,
        issues=body.issues,
    )
    result = run_assist(cfg, prompt)
    return {"job_id": job_id, "candidate_id": body.candidate_id, **result}


@app.post("/api/review/workbench-row")
def api_review_workbench_row(body: WorkbookReviewUpdateRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    ai = bundle.setdefault("ai_assists", {})
    overlays = ai.setdefault("candidate_overlays", {})
    overlay = dict(overlays.get(body.candidate_id) or {})
    language = body.language.upper()
    lang_key = "jp" if language == "JP" else "en"
    lang_payload = dict(overlay.get(lang_key) or {})
    field_map = {
        "use_case": body.use_case,
        "operation": body.operation,
        "expected_input": body.expected_input,
        "expected_output": body.expected_output,
    }
    changed_fields = set(overlay.get("changed_fields") or [])
    for field_name, value in field_map.items():
        if value is None:
            continue
        lang_payload[field_name] = value
        changed_fields.add(
            {
                "use_case": "UseCase",
                "operation": "Operation",
                "expected_input": "ExpectedInput",
                "expected_output": "ExpectedOutput",
            }[field_name]
        )
    overlay[lang_key] = lang_payload
    overlay["provider"] = overlay.get("provider") or "engineer_review"
    overlay["changed_fields"] = sorted(changed_fields)
    if body.review_status is not None:
        overlay["review_status_override"] = body.review_status
    if body.engineer_confirmation_required is not None:
        overlay["review_required"] = str(body.engineer_confirmation_required).lower() in {"yes", "true", "1"}
    if body.open_questions is not None:
        overlay["open_questions"] = [q.strip() for q in str(body.open_questions).split(";") if q.strip()]
    overlays[body.candidate_id] = overlay

    for cand in bundle.get("test_candidates") or []:
        if cand.get("id") != body.candidate_id:
            continue
        if body.review_status is not None:
            cand["review_status"] = body.review_status
        if body.engineer_confirmation_required is not None:
            cand["review_required"] = str(body.engineer_confirmation_required).lower() in {"yes", "true", "1"}
        break
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "candidate_id": body.candidate_id, "overlay": overlay}


@app.get("/api/app-config")
def api_app_config() -> dict[str, Any]:
    return app_config(_cfg())


@app.post("/api/review/test-candidates")
def api_create_test_candidate(body: TestCandidateCreateRequest, job_id: str) -> dict[str, Any]:
    _require_feature("add_clone_tc")
    try:
        if body.logic_id:
            sanitize_id(body.logic_id, field="logic_id")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    bundle = _bundle_for_job(job_id)
    cand = create_blank_candidate(
        bundle,
        logic_id=body.logic_id or "",
        control_name=body.control_name or "",
    )
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "candidate": cand, "candidate_id": cand.get("id")}


@app.post("/api/review/test-candidates/clone")
def api_clone_test_candidate(body: TestCandidateCloneRequest, job_id: str) -> dict[str, Any]:
    _require_feature("add_clone_tc")
    try:
        bundle = _bundle_for_job(job_id)
        cand = clone_candidate(
            bundle,
            body.source_candidate_id,
            logic_id=body.logic_id or "",
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "candidate": cand, "candidate_id": cand.get("id")}


@app.delete("/api/review/test-candidates/{candidate_id}")
def api_delete_test_candidate(candidate_id: str, job_id: str) -> dict[str, Any]:
    _require_feature("add_clone_tc")
    try:
        sanitize_id(candidate_id, field="candidate_id")
        bundle = _bundle_for_job(job_id)
        cand = soft_delete_candidate(bundle, candidate_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "candidate_id": candidate_id, "status": cand.get("status")}


@app.get("/api/review/evidence-graph")
def api_review_evidence_graph(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return build_evidence_graph(b)


@app.get("/api/review/capability-summary")
def api_review_capability_summary(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return build_capability_summary(b)


@app.get("/api/review/definition-inbox")
def api_review_definition_inbox(job_id: str, logic_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    try:
        return build_definition_inbox(b, logic_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/review/definition-query")
def api_review_definition_query(body: DefinitionQueryRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    out_dir = OUTPUT / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    ai = bundle.setdefault("ai_assists", {})
    notes = dict(ai.get("engineer_notes") or {})
    if body.note.strip():
        stored_notes = ai.setdefault("engineer_notes", {})
        stored_notes[body.logic_id] = body.note.strip()
        engineer_defs = ai.setdefault("engineer_definitions", {})
        stale = [
            name
            for name, meta in engineer_defs.items()
            if str((meta or {}).get("logic_id") or "") == body.logic_id
        ]
        for name in stale:
            engineer_defs.pop(name, None)
        missing = _missing_definition_terms(bundle, body.logic_id)
        for name, meta in _extract_engineer_definitions(
            body.note, body.logic_id, body.term, missing_terms=missing
        ).items():
            engineer_defs[name] = meta
        _apply_engineer_knowledge(bundle, body.logic_id, body.note, _cfg())
        _save_bundle_to_job(job_id, bundle)
        notes = dict(ai.get("engineer_notes") or {})
    cfg = _cfg()
    if copilot_enabled(cfg):
        try:
            cmd = start_definition_query_command(
                output_dir=out_dir,
                bundle=bundle,
                logic_id=body.logic_id,
                term=body.term.strip(),
                question=body.question.strip(),
                engineer_note=notes.get(body.logic_id, ""),
                save_bundle=lambda updated_bundle: _save_bundle_to_job(job_id, updated_bundle),
            )
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {**_command_dict(cmd), "job_id": job_id, "provider": "copilot"}

    if llm_enabled_for_assist(cfg):
        result = resolve_definition_with_ollama(
            bundle,
            cfg,
            logic_id=body.logic_id,
            term=body.term.strip(),
            question=body.question.strip() or body.note.strip(),
        )
        if not result.get("ok"):
            raise HTTPException(
                503,
                result.get("error") or "Ollama is not reachable. Start Ollama and pull the model from config.yaml.",
            )
        _save_bundle_to_job(job_id, bundle)
        return {
            "job_id": job_id,
            "provider": "ollama",
            "status": "completed",
            "result": result.get("entry"),
        }

    raise HTTPException(
        400,
        "No AI provider available. Enable llm.enabled in config.yaml and run Ollama, or enable assist.copilot.",
    )


@app.post("/api/review/logic-clarification")
def api_logic_clarification(body: LogicClarificationRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    ai = bundle.setdefault("ai_assists", {})
    notes = ai.setdefault("engineer_notes", {})
    notes[body.logic_id] = body.note.strip()
    engineer_defs = ai.setdefault("engineer_definitions", {})
    stale = [
        name
        for name, meta in engineer_defs.items()
        if str((meta or {}).get("logic_id") or "") == body.logic_id
    ]
    for name in stale:
        engineer_defs.pop(name, None)
    missing = _missing_definition_terms(bundle, body.logic_id)
    extracted = _extract_engineer_definitions(
        body.note, body.logic_id, body.term, missing_terms=missing
    )
    for name, meta in extracted.items():
        engineer_defs[name] = meta
    applied = _apply_engineer_knowledge(bundle, body.logic_id, body.note, _cfg())
    _save_bundle_to_job(job_id, bundle)
    return {
        "ok": True,
        "logic_id": body.logic_id,
        "note": notes[body.logic_id],
        "engineer_definitions": extracted,
        "applied_terms": sorted(extracted.keys()),
        "candidates_updated": applied.get("candidates_updated", 0),
        "apply_provider": applied.get("provider"),
        "apply_error": applied.get("error"),
    }


@app.post("/api/review/logic-attachments")
async def api_logic_attachments(
    job_id: str,
    logic_id: str,
    files: list[UploadFile] = File(...),
) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    attach_dir = _attachment_dir(job_id, logic_id)
    attach_dir.mkdir(parents=True, exist_ok=True)
    ai = bundle.setdefault("ai_assists", {})
    by_logic = ai.setdefault("logic_attachments", {})
    defs_by_logic = ai.setdefault("supplemental_definitions", {})
    rows = list(by_logic.get(logic_id) or [])
    defs = list(defs_by_logic.get(logic_id) or [])
    saved = []
    for uf in files:
        name = Path(uf.filename or "attachment.bin").name
        dest = attach_dir / name
        dest.write_bytes(await uf.read())
        kind, preview = _build_attachment_preview(dest)
        extracted_defs = _extract_supplemental_definitions(dest, logic_id)
        row = {
            "name": name,
            "path": str(dest),
            "kind": kind,
            "preview": preview[:4000],
            "definition_count": len(extracted_defs),
            "resolved_terms": sorted({d.get("name", "") for d in extracted_defs if d.get("name")})[:12],
        }
        rows = [r for r in rows if r.get("name") != name]
        rows.append(row)
        defs = [d for d in defs if (d.get("source") or {}).get("file") != name]
        defs.extend(extracted_defs)
        saved.append(name)
    by_logic[logic_id] = rows
    defs_by_logic[logic_id] = defs
    _save_bundle_to_job(job_id, bundle)
    return {
        "ok": True,
        "logic_id": logic_id,
        "saved": saved,
        "attachments": rows,
        "supplemental_definitions": defs,
    }


@app.get("/api/review/spec-understanding")
def api_spec_understanding(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {
        "spec_understanding": b.get("spec_understanding", {}),
        "summary": b.get("summary", {}),
    }


@app.get("/api/review/evidence-registry")
def api_evidence_registry(job_id: str, kind: str | None = None) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    reg = b.get("evidence_registry") or {}
    items = list(reg.get("items") or [])
    if kind:
        items = [r for r in items if str(r.get("kind")) == kind]
    return {
        "evidence_registry": {**reg, "items": items, "total": len(items)},
        "summary": b.get("summary", {}),
    }


@app.get("/api/review/traceability-matrix")
def api_traceability_matrix(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {
        "traceability_matrix": b.get("traceability_matrix", []),
        "logic_path_coverage": b.get("logic_path_coverage", []),
    }


@app.get("/api/review/description-improvements")
def api_description_improvements(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {"description_improvements": b.get("description_improvements", [])}


@app.get("/api/issues")
def api_issues(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {
        "issues": b.get("issues", []),
        "unresolved_items": b.get("unresolved_items", []),
    }


@app.get("/api/test-candidates")
def api_test_candidates(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {"test_candidates": b.get("test_candidates", [])}


@app.get("/api/classification")
def api_classification(job_id: Optional[str] = None) -> dict[str, Any]:
    if job_id:
        b = _bundle_for_job(job_id)
        return {"classified_files": b.get("classified_files", [])}
    return {"classified_files": _classify_uploads()}


@app.post("/api/review/update-status")
def api_review_update(body: ReviewUpdateRequest) -> dict[str, Any]:
    key = f"{body.item_type}:{body.item_id}"
    _review_overrides[key] = {"review_status": body.review_status, "note": body.note}
    return {"ok": True, "key": key}


@app.post("/api/test-candidates/edit")
def api_candidate_edit(body: CandidateEditRequest, job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    bundle = _bundle_for_job(job_id)
    out_dir = (job.output_dir if job else None) or OUTPUT / job_id
    for c in bundle.get("test_candidates", []):
        if c.get("id") == body.candidate_id:
            c.update(body.fields)
            c["review_status"] = body.fields.get("review_status", c.get("review_status", "edited"))
            dump_yaml(out_dir / "ui_bundle.yaml", bundle)
            if job:
                update_job(job_id, bundle=bundle)
            return {"ok": True, "candidate": c}
    raise HTTPException(404, "Candidate not found")


@app.get("/api/settings")
def api_get_settings() -> dict[str, Any]:
    return load_yaml(CONFIG_PATH)


@app.post("/api/settings")
def api_save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    dump_yaml(CONFIG_PATH, settings)
    return {"ok": True}


@app.get("/api/copilot/status")
def api_copilot_status() -> dict[str, Any]:
    return probe_copilot_cli()


@app.post("/api/copilot/login")
def api_copilot_login() -> dict[str, Any]:
    cmd = start_login(ROOT)
    return {
        "command_id": cmd.command_id,
        "status": cmd.status,
        "error_message": cmd.error_message,
        "verify_url": cmd.verify_url,
        "one_time_code": cmd.one_time_code,
        "log": cmd.log[-20:],
    }


@app.get("/api/copilot/commands/{command_id}")
def api_copilot_command(command_id: str) -> dict[str, Any]:
    cmd = get_copilot_command(command_id)
    if not cmd:
        raise HTTPException(404, f"Copilot command not found: {command_id}")
    return _command_dict(cmd)


@app.post("/api/copilot/verify")
def api_copilot_verify(deep: bool = Query(False)) -> dict[str, Any]:
    return verify_copilot_access(ROOT, deep=deep)


@app.post("/api/copilot/assist")
def api_copilot_assist(body: CopilotAssistRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    out_dir = OUTPUT / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    ai = bundle.setdefault("ai_assists", {})
    notes = dict(ai.get("engineer_notes") or {})
    if body.logic_id and body.engineer_note is not None:
        notes[body.logic_id] = body.engineer_note.strip()
        ai["engineer_notes"] = notes
        _save_bundle_to_job(job_id, bundle)

    logic_items = bundle.get("logic_review_items") or []
    if body.mode == "all":
        logic_ids = [str(item.get("logic_id")) for item in logic_items if item.get("logic_id")]
    elif body.mode == "queued":
        logic_ids = build_ai_queue(bundle, language=body.language).get("run_logic_ids") or []
    elif body.logic_id:
        logic_ids = [body.logic_id]
    else:
        raise HTTPException(400, "logic_id is required for single assist mode")
    if not logic_ids:
        raise HTTPException(400, "No logic groups are currently ready for the AI queue. Resolve missing definitions first.")

    try:
        cmd = start_logic_assist_command(
            output_dir=out_dir,
            bundle=bundle,
            logic_ids=logic_ids,
            engineer_notes=notes,
            language=body.language,
            save_bundle=lambda updated_bundle: _save_bundle_to_job(job_id, updated_bundle),
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        **_command_dict(cmd),
        "job_id": job_id,
        "module_name": derive_module_name(bundle),
        "overlay_count": len((bundle.get("ai_assists") or {}).get("candidate_overlays") or {}),
    }


@app.get("/api/export")
@app.post("/api/export")
def api_export(job_id: str, mode: str = "approved") -> FileResponse:
    job = get_job(job_id)
    out_dir = (job.output_dir if job else None) or OUTPUT / job_id
    if not out_dir.exists():
        raise HTTPException(404, "Job output not found")
    b = _bundle_for_job(job_id)
    cases = b.get("test_candidates", [])
    if mode == "approved":
        cases = [c for c in cases if c.get("review_status") == "approved" and c.get("status") != "blocked"]
    export = {
        "version": "0.1-export",
        "export_mode": mode,
        "strict_mode": b.get("strict_mode"),
        "errors_unresolved": b.get("summary", {}).get("errors", 0),
        "test_cases": cases,
    }
    path = out_dir / f"export_{mode}.yaml"
    dump_yaml(path, export)
    return FileResponse(path, filename=path.name, media_type="application/x-yaml")


def _xlsx_for_job(job_id: str, filename: str) -> FileResponse:
    job = get_job(job_id)
    out_dir = (job.output_dir if job else None) or OUTPUT / job_id
    path = out_dir / filename
    if not path.exists():
        raise HTTPException(404, f"{filename} not found — run analysis first")
    return FileResponse(
        path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/export/test-spec-xlsx")
@app.post("/api/export/test-spec-xlsx")
def api_export_test_spec_xlsx(job_id: str) -> FileResponse:
    return _xlsx_for_job(job_id, "generated_test_spec.xlsx")


@app.get("/api/export/review-package-xlsx")
@app.post("/api/export/review-package-xlsx")
def api_export_review_package_xlsx(job_id: str) -> FileResponse:
    return _xlsx_for_job(job_id, "review_package.xlsx")


@app.get("/api/export/traceability-xlsx")
@app.post("/api/export/traceability-xlsx")
def api_export_traceability_xlsx(job_id: str) -> FileResponse:
    return _xlsx_for_job(job_id, "logic_traceability.xlsx")


@app.get("/api/export/issues-xlsx")
@app.post("/api/export/issues-xlsx")
def api_export_issues_xlsx(job_id: str) -> FileResponse:
    return _xlsx_for_job(job_id, "issue_list.xlsx")


@app.get("/api/export/customer-testspec-xlsx")
@app.post("/api/export/customer-testspec-xlsx")
def api_export_customer_testspec_xlsx(job_id: str, language: str = "EN") -> FileResponse:
    job = get_job(job_id)
    out_dir = Path(job.output_dir) if job and job.output_dir else OUTPUT / job_id
    if not out_dir.exists():
        raise HTTPException(404, "Job output not found")
    bundle = _bundle_for_job(job_id)
    try:
        path = export_customer_testspec(out_dir, bundle, language=language)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# Aliases for legacy / mistaken frontend paths
@app.get("/api/export/generated-test-spec-xlsx")
@app.post("/api/export/generated-test-spec-xlsx")
def api_export_generated_test_spec_xlsx_alias(job_id: str) -> FileResponse:
    return api_export_test_spec_xlsx(job_id)


@app.get("/api/export/logic-traceability-xlsx")
@app.post("/api/export/logic-traceability-xlsx")
def api_export_logic_traceability_xlsx_alias(job_id: str) -> FileResponse:
    return api_export_traceability_xlsx(job_id)


@app.get("/api/export/issue-list-xlsx")
@app.post("/api/export/issue-list-xlsx")
def api_export_issue_list_xlsx_alias(job_id: str) -> FileResponse:
    return api_export_issues_xlsx(job_id)


@app.get("/api/export/ui-bundle")
def api_export_ui_bundle(job_id: str) -> FileResponse:
    job = get_job(job_id)
    out_dir = (job.output_dir if job else None) or OUTPUT / job_id
    path = out_dir / "ui_bundle.yaml"
    if not path.exists():
        raise HTTPException(404, "ui_bundle.yaml not found — run analysis first")
    return FileResponse(path, filename="ui_bundle.yaml", media_type="application/x-yaml")


@app.get("/api/export/review-md")
def api_export_review_md(job_id: str) -> FileResponse:
    """Download review markdown zip folder as single file — first file for quick access."""
    job = get_job(job_id)
    out = Path(job.output_dir) if job and job.output_dir else OUTPUT / job_id
    review_dir = out / "review"
    if not review_dir.is_dir():
        raise HTTPException(404, "Review package not found — run analysis first")
    # Prefer logic blocks review if present
    for name in ("04b_logic_blocks.md", "04_condition_tree_review.md", "07_test_scenario_candidates.md"):
        p = review_dir / name
        if p.exists():
            return FileResponse(p, filename=p.name, media_type="text/markdown")
    first = next(review_dir.glob("*.md"), None)
    if not first:
        raise HTTPException(404, "No review markdown files")
    return FileResponse(first, filename=first.name, media_type="text/markdown")


@app.get("/api/jobs/{job_id}/summary")
def api_job_summary(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    workbench = build_workbench_summary(b, language="EN")
    return {
        "job_id": job_id,
        "summary": {
            **(b.get("summary", {})),
            **workbench,
        },
        "strict_mode": b.get("strict_mode"),
        "module_name": derive_module_name(b),
        "has_bundle": True,
    }


@app.get("/api/review/dashboard")
def api_review_dashboard(job_id: str) -> dict[str, Any]:
    """Single payload for the main Review screen."""
    b = _bundle_for_job(job_id)
    rep = b.get("spec_understanding", {})
    issues = b.get("issues") or []
    errors = [i for i in issues if i.get("severity") == "error"]
    workbench = build_workbench_summary(b, language="EN")
    evidence = build_evidence_graph(b)
    ai_queue = build_ai_queue(b, language="EN")
    capability = build_capability_summary(b)
    return {
        "job_id": job_id,
        "summary": {
            **(b.get("summary", {})),
            **workbench,
        },
        "module_name": derive_module_name(b),
        "spec_understanding": rep,
        "top_issues": errors[:8] + [i for i in issues if i.get("severity") != "error"][:4],
        "logic_review_count": len(b.get("logic_review_items") or []),
        "extracted": rep.get("extracted", {}),
        "copilot_overlay_count": len((b.get("ai_assists") or {}).get("candidate_overlays") or {}),
        "workbench": workbench,
        "evidence_summary": evidence.get("summary", {}),
        "ai_queue": ai_queue,
        "capability_summary": capability,
        "term_roles": b.get("term_roles") or {},
        "source_index": b.get("source_index") or {},
    }


@app.post("/api/load-sample")
def api_load_sample() -> dict[str, Any]:
    copied = []
    for sample in (
        ROOT.parent / "pm_sample_inputs" / "input",
        ROOT.parent / "pm_sample_inputs",
    ):
        if not sample.is_dir():
            continue
        for p in sample.iterdir():
            if p.is_file() and is_ingestible_file(p):
                shutil.copy2(p, UPLOADS / p.name)
                copied.append(p.name)
    return {
        "files": _classify_uploads(),
        "copied": copied,
        "message": "Sample files copied to uploads (lock files excluded)",
    }
