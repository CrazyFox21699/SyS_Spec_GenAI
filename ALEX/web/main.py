"""FastAPI web UI for ALEX."""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
import threading
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
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
from src.utils.config_path import get_config_path
from src.utils.yaml_utils import dump_yaml, load_yaml
from src.utils.feature_flags import app_config, feature_enabled
from web.bundle_helpers import bundle_path_for_job, ensure_enriched_bundle
from src.engine.understanding_loop import rebuild_understanding
from src.engine.incremental_ingest import extract_reference_file, merge_reference_extract
from src.engine.path_tc_matrix import build_path_tc_matrix
from src.engine.selective_tc_regen import build_path_regen_proposals
from web.candidate_mutations import (
    clone_candidate,
    create_blank_candidate,
    sanitize_id,
    soft_delete_candidate,
    update_candidate_identity,
)
from web.jobs import append_log, create_job, get_job, run_job_background, update_job
from src.engine.condition_resolver import resolve_condition
from src.engine.source_index import build_source_index
from src.engine.document_graph_builder import (
    add_user_edge as add_doc_user_edge,
    delete_user_edge as delete_doc_user_edge,
    node_detail as doc_node_detail,
    update_user_edge as update_doc_user_edge,
)
from src.library import (
    add_item as library_add_item,
    add_link as library_add_link,
    delete_item as library_delete_item,
    delete_link as library_delete_link,
    import_dropped_file as library_import_dropped_file,
    load_library,
    save_library,
    scan_folder_listing,
    browse_for_root,
    set_focus as library_set_focus,
    set_root as library_set_root,
    update_item as library_update_item,
    update_link as library_update_link,
    validate_inside_root as library_validate_inside_root,
)
from web import m365_auth
from web.security import TeamAuthMiddleware, get_current_user, parse_if_match_version
from web.team_auth import (
    SESSION_COOKIE,
    TeamUser,
    admin_set_password,
    authenticate,
    change_password,
    cookie_secure,
    create_session,
    create_user,
    delete_session,
    get_user_for_session,
    init_user_db,
    list_users,
    remember_session_hours,
    session_hours,
    session_remaining_hours,
    set_user_active,
    team_auth_enabled,
    touch_session,
    user_public_dict,
)
from web.copilot_orchestrator import (
    build_context,
    run_apply_preview,
    run_confirm,
    run_plan,
    run_write,
    update_plan,
)
from web.copilot_context_pack import get_copilot_session
from web.style_guide import save_style_samples
from web.ai_provider import (
    apply_knowledge,
    default_provider,
    export_m365_brief,
    import_knowledge_patches,
    improve_io,
    provider_status,
    resolve_definition,
)
from web.review_translate import translate_workbook_with_m365
from web.review_workbench import (
    build_ai_queue,
    build_capability_summary,
    build_definition_inbox,
    build_evidence_graph,
    build_workbench_summary,
    paginate_workbook_rows,
)
from web.reasoning_session import append_turn as append_reasoning_turn
from web.reasoning_session import append_hypothesis as append_reasoning_hypothesis
from web.reasoning_session import create_session as create_reasoning_session
from web.reasoning_session import load_session as load_reasoning_session
from web.knowledge_reconciliation import (
    confirm_pending_knowledge,
    get_knowledge_apply_payload,
    reject_pending_knowledge,
)
from web.copilot_code_context_pack import build_code_context_pack
from web.copilot_code_orchestrator import run_copilot_code_generate, run_copilot_code_generate_batch
from web.alex_storage import (
    code_style_samples_path,
    default_library_root,
    migrate_legacy_alex_data,
    normalize_library_root,
)
from web.code_style_samples import (
    export_library_code_samples,
    ingest_cpp_upload,
    load_code_style_samples,
    merge_samples_from_bundle,
    save_code_style_samples,
)
from web.project_memory import (
    export_library_memory,
    import_library_memory,
    library_memory_path,
    merge_project_memory,
    promote_shared_precondition,
    promote_verification_pattern,
    remember_io_from_text,
    save_bundle_memory,
)
from src.engine.verification_patterns import build_verification_matrix
from web.gtest_workspace import (
    build_workspace_payload,
    export_approved_bundle,
    export_library_preset,
    export_single_snippet,
    generate_draft_for_request,
    import_library_preset,
    library_preset_path,
    load_gtest_state,
    save_draft,
    save_gtest_state,
    suggest_map_for_request,
    sync_gtest_to_bundle,
)
from web.structured_knowledge import (
    compile_accepted_constraints,
    overlay_payload,
    save_constraints,
)
from src.engine.boundary_tc_proposals import propose_boundary_testcases
from src.engine.golden_spec_scoreboard import build_spec_scoreboard, discover_golden_fixtures, evaluate_scoreboard
from src.engine.issue_prioritizer import build_overview_dashboard, prioritize_issues
from src.engine.logic_path_simulator import collect_simulation_signals, simulate_logic_path
from src.engine.structured_overlay import add_diagram_link

ROOT = Path(__file__).resolve().parent.parent
WEB_DATA = ROOT / "web_data"
UPLOADS = WEB_DATA / "uploads"
OUTPUT = WEB_DATA / "output"
STATIC = Path(__file__).resolve().parent / "static"
CONFIG_PATH = get_config_path()

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

    cfg = load_yaml(CONFIG_PATH) if CONFIG_PATH.exists() else {}
    init_db(WEB_DATA, production=_deployment_mode() == "production")
    if team_auth_enabled(cfg):
        init_user_db(WEB_DATA)
    _repair_library_state()


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

app.add_middleware(TeamAuthMiddleware, cfg=_prod_cfg)

if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

# Session state: file registry + user overrides
_file_registry: dict[str, dict[str, Any]] = {}
_review_overrides: dict[str, dict[str, Any]] = {}
_job_write_locks: dict[str, threading.Lock] = {}
_job_lock_registry = threading.Lock()
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


class LoginRequest(BaseModel):
    username: str
    password: str
    remember: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AdminCreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "engineer"


class AdminResetPasswordRequest(BaseModel):
    new_password: str


class AdminUserActiveRequest(BaseModel):
    active: bool = True


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
    force_ollama: bool = False
    local_only: bool = False
    provider: str = "auto"
    compile_constraints_first: bool = True


class StructuredOverlayRequest(BaseModel):
    logic_id: str
    constraints: list[dict[str, Any]] = []


class CompileConstraintsRequest(BaseModel):
    logic_id: str


class LogicSimulateRequest(BaseModel):
    logic_id: str
    assignments: dict[str, Any] = {}


class DiagramLinkRequest(BaseModel):
    logic_id: str
    from_state: str = ""
    to_state: str = ""
    event: str = ""
    conditions: list[str] = []
    edge_key: str = ""
    note: str = ""


class StyleSamplesRequest(BaseModel):
    samples: list[dict[str, Any]] = []


class CopilotPlanRequest(BaseModel):
    logic_id: str
    note: str = ""
    term: str = ""


class CopilotPlanPatchRequest(BaseModel):
    logic_id: str
    plan: dict[str, Any]


class CopilotWriteRequest(BaseModel):
    logic_id: str


class CopilotConfirmRequest(BaseModel):
    logic_id: str
    draft_indices: list[int] = []


class ImportKnowledgeRequest(BaseModel):
    logic_id: str
    payload: str


class M365SetupRequest(BaseModel):
    client_id: str
    tenant_id: str = "organizations"


class M365ConnectRequest(BaseModel):
    display_name: str = "M365 manual workflow"


class DefinitionQueryRequest(BaseModel):
    logic_id: str
    term: str = ""
    question: str
    note: str = ""


class ReasoningSessionRequest(BaseModel):
    logic_id: str
    note: str = ""
    provider: str = "auto"


class ReasoningTurnRequest(BaseModel):
    logic_id: str
    role: str = "engineer"
    content: str
    provider: str = "auto"
    metadata: dict[str, Any] = {}


class ReasoningHypothesisRequest(BaseModel):
    logic_id: str
    provider: str = "auto"
    hypothesis: dict[str, Any]


class KnowledgeApplyConfirmRequest(BaseModel):
    logic_id: str
    patch_indices: list[int] = []


class ReasoningAcceptClaimsRequest(BaseModel):
    logic_id: str
    claim_indices: list[int] = []
    hypothesis_index: int = -1


class WorkbookReviewUpdateRequest(BaseModel):
    candidate_id: str
    new_candidate_id: Optional[str] = None
    test_function: Optional[str] = None
    event: Optional[str] = None
    use_case: Optional[str] = None
    operation: Optional[str] = None
    expected_input: Optional[str] = None
    expected_output: Optional[str] = None
    review_status: Optional[str] = None
    engineer_confirmation_required: Optional[str] = None
    open_questions: Optional[str] = None
    remember_io_mapping: bool = False
    language: str = "EN"


class CandidateIdentityUpdateRequest(BaseModel):
    new_candidate_id: Optional[str] = None
    test_function: Optional[str] = None
    event: Optional[str] = None


class ProjectMemoryUpdateRequest(BaseModel):
    io_variable_map: Optional[dict[str, str]] = None
    signal_roles: Optional[dict[str, str]] = None
    shared_preconditions: Optional[list[dict[str, Any]]] = None
    verification_patterns: Optional[list[dict[str, Any]]] = None


class CopilotCodeGenerateRequest(BaseModel):
    candidate_id: str
    use_baseline: bool = True
    engineer_note: str = ""
    reference_test_name: str = ""
    language: str = "EN"


class CopilotCodeBatchRequest(BaseModel):
    candidate_ids: list[str] = []
    logic_id: str = ""
    engineer_note: str = ""
    reference_test_name: str = ""
    persist_drafts: bool = False
    language: str = "EN"


class CodeStyleSampleRow(BaseModel):
    label: str = ""
    test_name: str = ""
    fixture_class: str = ""
    source_file: str = ""
    snippet: str = ""


class CodeStyleSamplesRequest(BaseModel):
    samples: list[CodeStyleSampleRow] = []
    replace: bool = False


class PromoteVerificationPatternRequest(BaseModel):
    logic_id: str
    given_fingerprint: str
    then_signals: list[str] = []
    candidate_ids: list[str] = []
    label: str = ""


class PromotePreconditionRequest(BaseModel):
    logic_id: str = ""
    label: str
    expected_input: str


class TestCandidateCreateRequest(BaseModel):
    logic_id: Optional[str] = None
    control_name: Optional[str] = None
    template: str = "blank"


class TestCandidateCloneRequest(BaseModel):
    source_candidate_id: str
    logic_id: Optional[str] = None


class DocumentEdgeCreateRequest(BaseModel):
    source_id: str
    target_id: str
    label: Optional[str] = ""
    kind: Optional[str] = "user_defined"
    note: Optional[str] = ""


class DocumentEdgeUpdateRequest(BaseModel):
    label: Optional[str] = None
    kind: Optional[str] = None
    note: Optional[str] = None


class LibraryRootRequest(BaseModel):
    path: str


class LibraryItemCreateRequest(BaseModel):
    file: Optional[str] = None


class LibraryItemUpdateRequest(BaseModel):
    file: Optional[str] = None


class LibraryFocusRequest(BaseModel):
    item_id: str


class LibraryLinkCreateRequest(BaseModel):
    label: str
    source_id: Optional[str] = None
    target_id: Optional[str] = None


class LibraryLinkUpdateRequest(BaseModel):
    label: Optional[str] = None


class GTestGenerateRequest(BaseModel):
    candidate_id: Optional[str] = None
    logic_id: Optional[str] = None
    variable_map: Optional[dict[str, str]] = None
    language: Optional[str] = "EN"


class GTestSuggestMapRequest(BaseModel):
    candidate_id: Optional[str] = None
    language: Optional[str] = "EN"


class GTestDraftSaveRequest(BaseModel):
    draft_key: str
    spec_comment_block: str = ""
    code_body: str = ""
    full_snippet: str = ""
    source_kind: str = "candidate"
    test_name: str = ""
    engineer_edited: bool = True


class GTestVariableMapRequest(BaseModel):
    code_variable_map: dict[str, str]


class GTestHarnessRequest(BaseModel):
    harness: dict[str, Any]


class GTestLibraryPresetRequest(BaseModel):
    job_id: Optional[str] = None
    preset: Optional[dict[str, Any]] = None


def _cfg() -> dict[str, Any]:
    return load_yaml(CONFIG_PATH) if CONFIG_PATH.exists() else {}


def _require_feature(name: str) -> None:
    if not feature_enabled(_cfg(), name, default=False):
        raise HTTPException(403, f"Feature '{name}' is disabled in config.yaml")


def _team_auth_on() -> bool:
    return team_auth_enabled(_cfg())


def _current_team_user() -> TeamUser | None:
    user = get_current_user()
    return user if isinstance(user, TeamUser) else None


def _require_admin() -> TeamUser:
    user = _current_team_user()
    if not user:
        raise HTTPException(401, "Not authenticated")
    if user.role != "admin":
        raise HTTPException(403, "Admin only")
    return user


def _uploads_dir() -> Path:
    user = _current_team_user()
    if _team_auth_on() and user:
        root = WEB_DATA / "uploads" / user.username
    else:
        root = UPLOADS
    root.mkdir(parents=True, exist_ok=True)
    return root


def _output_root() -> Path:
    user = _current_team_user()
    if _team_auth_on() and user:
        root = WEB_DATA / "output" / user.username
    else:
        root = OUTPUT
    root.mkdir(parents=True, exist_ok=True)
    return root


def _job_output_dir(job_id: str) -> Path:
    job = get_job(job_id)
    if job and job.output_dir:
        return Path(job.output_dir)
    return _output_root() / job_id


def _load_job_gtest_state(job_id: str) -> dict[str, Any]:
    return load_gtest_state(_job_output_dir(job_id), _cfg())


def _persist_job_gtest_state(job_id: str, gtest_state: dict[str, Any]) -> dict[str, Any]:
    save_gtest_state(_job_output_dir(job_id), gtest_state)
    bundle = _bundle_for_job(job_id)
    sync_gtest_to_bundle(bundle, gtest_state)
    _save_bundle_to_job(job_id, bundle)
    return gtest_state


def _job_owner(job_id: str) -> str | None:
    if _deployment_mode() == "production":
        try:
            from web.job_store import get_job_record

            rec = get_job_record(job_id)
            if rec:
                return rec.created_by or "system"
        except RuntimeError:
            pass
    users_root = WEB_DATA / "output"
    if users_root.is_dir():
        for user_dir in users_root.iterdir():
            if user_dir.is_dir() and (user_dir / job_id).is_dir():
                return user_dir.name
    if (OUTPUT / job_id).is_dir():
        return "system"
    return None


def _assert_job_access(job_id: str) -> None:
    if not _team_auth_on():
        return
    user = _current_team_user()
    if not user:
        raise HTTPException(401, "Not authenticated")
    if user.role == "admin":
        return
    owner = _job_owner(job_id)
    if owner and owner != user.username:
        raise HTTPException(403, "Access denied")


def _m365_user_id() -> str | None:
    user = _current_team_user()
    return user.username if user else None


def _job_write_lock(job_id: str) -> threading.Lock:
    with _job_lock_registry:
        if job_id not in _job_write_locks:
            _job_write_locks[job_id] = threading.Lock()
        return _job_write_locks[job_id]


def _get_bundle_version(job_id: str) -> int:
    job = get_job(job_id)
    if job and job.bundle_version:
        return int(job.bundle_version)
    out_dir = _job_output_dir(job_id)
    manifest = out_dir / "bundle" / "manifest.json"
    if manifest.exists():
        try:
            return int(json.loads(manifest.read_text(encoding="utf-8")).get("version", 0))
        except (json.JSONDecodeError, ValueError, OSError):
            pass
    return 0


def _list_uploaded_files() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    uploads = _uploads_dir()
    for p in sorted(uploads.iterdir()):
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
    uploads = _uploads_dir()
    for p in uploads.iterdir():
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


def _persist_repaired_bundle(job_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    """Write auto-repaired logic blocks back to disk and in-memory job cache."""
    cleaned = dict(bundle)
    cleaned.pop("_logic_repaired", None)
    out_dir = _job_output_dir(job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    dump_yaml(out_dir / "ui_bundle.yaml", cleaned)
    job = get_job(job_id)
    if job:
        update_job(job_id, bundle=cleaned, output_dir=out_dir)
    return cleaned


def _bundle_for_job(job_id: str) -> dict[str, Any]:
    _assert_job_access(job_id)
    job = get_job(job_id)

    def _finalize(bundle: dict[str, Any]) -> dict[str, Any]:
        enriched = ensure_enriched_bundle(bundle)
        if enriched.get("_logic_repaired"):
            enriched = _persist_repaired_bundle(job_id, enriched)
            enriched = ensure_enriched_bundle(enriched)
        return enriched

    if job and job.bundle:
        return _finalize(job.bundle)
    if job and job.output_dir:
        from web.bundle_store import load_split_bundle

        split = load_split_bundle(Path(job.output_dir))
        if split:
            return _finalize(split)
        path = Path(job.output_dir) / "ui_bundle.yaml"
        if path.exists():
            return _finalize(load_yaml(path))
    if _deployment_mode() == "production":
        try:
            from web.job_store import get_job_record

            rec = get_job_record(job_id)
            if rec and rec.output_dir:
                rec_dir = Path(rec.output_dir)
                from web.bundle_store import load_split_bundle

                split = load_split_bundle(rec_dir)
                if split:
                    return _finalize(split)
                rec_yaml = rec_dir / "ui_bundle.yaml"
                if rec_yaml.exists():
                    return _finalize(load_yaml(rec_yaml))
        except RuntimeError:
            pass
    disk = bundle_path_for_job(_output_root(), job_id)
    if not disk:
        disk = bundle_path_for_job(OUTPUT, job_id)
    if disk:
        return _finalize(load_yaml(disk))
    if job and job.output_dir:
        path = Path(job.output_dir) / "ui_bundle.yaml"
        if path.exists():
            return _finalize(load_yaml(path))
    out_path = _job_output_dir(job_id) / "ui_bundle.yaml"
    if out_path.exists():
        return _finalize(load_yaml(out_path))
    if job:
        raise HTTPException(404, "No analysis bundle yet — wait for review to finish")
    raise HTTPException(404, f"Job not found: {job_id}")


def _rebuild_understanding(
    bundle: dict[str, Any],
    *,
    logic_id: str | None = None,
    trigger: str,
) -> dict[str, Any]:
    logic_ids = [logic_id] if logic_id else None
    return rebuild_understanding(bundle, logic_ids=logic_ids, trigger=trigger)


def _save_bundle_to_job(job_id: str, bundle: dict[str, Any], *, expected_version: int | None = None) -> int:
    if expected_version is None:
        expected_version = parse_if_match_version()
    with _job_write_lock(job_id):
        current = _get_bundle_version(job_id)
        if expected_version is not None and expected_version != current:
            raise HTTPException(
                409,
                "Someone else saved — refresh the page and try again.",
            )
        bundle = ensure_enriched_bundle(bundle)
        job = get_job(job_id)
        out_dir = _job_output_dir(job_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        dump_yaml(out_dir / "ui_bundle.yaml", bundle)
        new_version = current + 1
        manifest_path = out_dir / "bundle" / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["version"] = new_version
                manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            except (json.JSONDecodeError, OSError, ValueError):
                pass
        if job:
            update_job(job_id, bundle=bundle, bundle_version=new_version, output_dir=out_dir)
        return new_version


def _library_root() -> Path | None:
    try:
        state = load_library(WEB_DATA)
    except Exception:  # noqa: BLE001
        return None
    root = normalize_library_root((state or {}).get("root") or "")
    if not root:
        return default_library_root()
    try:
        return Path(root).expanduser().resolve()
    except OSError:
        return default_library_root()


def _repair_library_state() -> None:
    """Fix stale pm_test_spec_assistant paths; migrate .alex data into ALEX/web_data/.alex."""
    try:
        state = load_library(WEB_DATA)
    except Exception:  # noqa: BLE001
        return
    raw = str(state.get("root") or "")
    fixed = normalize_library_root(raw)
    changed = fixed != raw
    legacy_root = None
    if raw and raw != fixed:
        try:
            legacy_root = Path(raw).expanduser().resolve()
        except OSError:
            legacy_root = None
    if legacy_root:
        migrate_legacy_alex_data(legacy_root)
    if changed:
        state["root"] = fixed
        save_library(WEB_DATA, state)
    elif legacy_root:
        migrate_legacy_alex_data(legacy_root)
    else:
        migrate_legacy_alex_data(_library_root())


def _safe_file_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser().resolve()
    allowed_roots = [ROOT.resolve(), UPLOADS.resolve(), OUTPUT.resolve(), _uploads_dir().resolve(), _output_root().resolve()]
    library_root = _library_root()
    if library_root and library_root.exists():
        allowed_roots.append(library_root)
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

    from src.engine.signal_constraint_parser import extract_signal_constraints_from_text

    for sig, definition in extract_signal_constraints_from_text(text, focus_term=focus).items():
        add_def(sig, definition)

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
    return _job_output_dir(job_id) / "logic_attachments" / logic_id


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


@app.get("/", response_class=HTMLResponse, response_model=None)
def index(request: Request):
    return _serve_spa_shell(request)


def _serve_spa_shell(request: Request) -> HTMLResponse:
    cfg = _cfg()
    if team_auth_enabled(cfg):
        session_id = request.cookies.get(SESSION_COOKIE, "")
        if not get_user_for_session(session_id):
            return RedirectResponse(url="/login", status_code=302)
    html_path = STATIC / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>ALEX</h1><p>static/index.html missing</p>")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


for _spa_slug in ("review", "logic", "diagram", "library", "export", "test-code", "guide"):
    app.add_api_route(
        f"/{_spa_slug}",
        _serve_spa_shell,
        methods=["GET"],
        response_class=HTMLResponse,
        response_model=None,
    )


@app.get("/login", response_class=HTMLResponse)
def login_page() -> HTMLResponse:
    html_path = STATIC / "login.html"
    if not html_path.exists():
        raise HTTPException(404, "login.html missing")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/admin", response_class=HTMLResponse, response_model=None)
def admin_page(request: Request):
    """Hidden team admin console — not linked from main UI. IT bookmark only."""
    if not team_auth_enabled(_cfg()):
        raise HTTPException(404, "Not found")
    session_id = request.cookies.get(SESSION_COOKIE, "")
    user = get_user_for_session(session_id) if session_id else None
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.role != "admin":
        raise HTTPException(404, "Not found")
    html_path = STATIC / "admin.html"
    if not html_path.exists():
        raise HTTPException(404, "admin.html missing")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/auth/login")
def api_auth_login(body: LoginRequest, response: Response) -> dict[str, Any]:
    cfg = _cfg()
    if not team_auth_enabled(cfg):
        raise HTTPException(400, "Team auth is disabled")
    user = authenticate(body.username, body.password)
    if not user:
        raise HTTPException(401, "Invalid username or password")
    hours = remember_session_hours(cfg) if body.remember else session_hours(cfg)
    session_id = create_session(user.user_id, hours=hours)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        secure=cookie_secure(cfg),
        samesite="lax",
        max_age=hours * 3600,
        path="/",
    )
    return {"ok": True, **user_public_dict(user)}


@app.post("/api/auth/logout")
def api_auth_logout(request: Request, response: Response) -> dict[str, Any]:
    session_id = request.cookies.get(SESSION_COOKIE, "")
    delete_session(session_id)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


def _refresh_session_cookie(request: Request, response: Response, cfg: dict[str, Any]) -> None:
    session_id = request.cookies.get(SESSION_COOKIE, "")
    if not session_id:
        return
    remaining = session_remaining_hours(session_id)
    if remaining is None:
        return
    hours = remember_session_hours(cfg) if remaining > 24 else session_hours(cfg)
    touch_session(session_id, hours=hours)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        secure=cookie_secure(cfg),
        samesite="lax",
        max_age=hours * 3600,
        path="/",
    )


@app.get("/api/auth/me")
def api_auth_me(request: Request, response: Response) -> dict[str, Any]:
    cfg = _cfg()
    if not team_auth_enabled(cfg):
        return {"enabled": False, "username": "system", "role": "admin"}
    user = _current_team_user()
    if not user:
        raise HTTPException(401, "Not authenticated")
    _refresh_session_cookie(request, response, cfg)
    return {"enabled": True, **user_public_dict(user)}


@app.post("/api/auth/change-password")
def api_auth_change_password(body: ChangePasswordRequest) -> dict[str, Any]:
    user = _current_team_user()
    if not user:
        raise HTTPException(401, "Not authenticated")
    try:
        change_password(user.username, body.current_password, body.new_password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.get("/api/admin/users")
def api_admin_list_users() -> dict[str, Any]:
    _require_admin()
    return {"ok": True, "users": list_users()}


@app.post("/api/admin/users")
def api_admin_create_user(body: AdminCreateUserRequest) -> dict[str, Any]:
    _require_admin()
    try:
        user = create_user(body.username, body.password, role=body.role)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, **user_public_dict(user)}


@app.post("/api/admin/users/{username}/reset-password")
def api_admin_reset_password(username: str, body: AdminResetPasswordRequest) -> dict[str, Any]:
    admin = _require_admin()
    if username.lower() == admin.username.lower() and len(body.new_password or "") < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    try:
        admin_set_password(username, body.new_password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "username": username}


@app.post("/api/admin/users/{username}/active")
def api_admin_set_user_active(username: str, body: AdminUserActiveRequest) -> dict[str, Any]:
    _require_admin()
    try:
        set_user_active(username, active=body.active)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "username": username, "active": body.active}


@app.get("/api/projects")
def api_projects() -> dict[str, Any]:
    default = get_config_path()
    cfg = load_yaml(default) if default.exists() else {}
    sample = ROOT / "sample_inputs" / "input"
    return {
        "projects": [
            {"id": "uploads", "label": "Uploaded files", "path": str(_uploads_dir())},
            {"id": "sample", "label": "Sample inputs", "path": str(sample) if sample.is_dir() else None},
        ],
        "default_input": cfg.get("ui", {}).get("default_input_dir"),
    }


@app.post("/api/upload")
async def api_upload(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    saved = []
    replaced = []
    rejected = []
    uploads = _uploads_dir()
    for uf in files:
        name = Path(uf.filename or "upload.bin").name
        dest = uploads / name
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
    uploads = _uploads_dir()
    for p in uploads.iterdir():
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
    uploads = _uploads_dir()
    for p in list(uploads.iterdir()):
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
    user = _current_team_user()
    created_by = None if (user and user.role == "admin") else (user.username if user else None)
    if _deployment_mode() == "production":
        try:
            from web.job_store import list_jobs

            for rec in list_jobs(limit=20, created_by=created_by):
                jobs.append(
                    {
                        "job_id": rec.job_id,
                        "status": rec.status,
                        "progress": rec.progress,
                        "created": rec.created_at,
                        "created_by": rec.created_by,
                    }
                )
        except RuntimeError:
            pass
    scan_root = _output_root()
    if scan_root.is_dir():
        for d in sorted(scan_root.iterdir(), reverse=True):
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
    input_dir = Path(body.input_dir) if body.input_dir else _uploads_dir()
    if not input_dir.is_dir():
        raise HTTPException(400, f"Input directory not found: {input_dir}")

    ingestible = [p for p in input_dir.iterdir() if p.is_file() and is_ingestible_file(p)]
    if not ingestible:
        raise HTTPException(
            400,
            "No ingestible files in uploads. Use Load sample package or upload .docx/.xlsx (not Word lock files ~$).",
        )

    user = _current_team_user()
    created_by = user.username if user else "system"
    job = create_job(created_by=created_by)
    out_dir = _job_output_dir(job.job_id)
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
    _assert_job_access(job_id)
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
    disk = bundle_path_for_job(_output_root(), job_id) or bundle_path_for_job(OUTPUT, job_id)
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
        "state_machines": b.get("state_machines") or [],
        "retention_rules": b.get("retention_rules") or [],
        "review_annotations": b.get("review_annotations") or [],
        "spec_profiles": b.get("spec_profiles") or [],
        "signals": b.get("signals") or [],
    }


@app.post("/api/review/logic-simulate")
def api_logic_simulate(body: LogicSimulateRequest, job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    item = next(
        (row for row in (b.get("logic_review_items") or []) if row.get("logic_id") == body.logic_id),
        None,
    )
    if not item:
        raise HTTPException(404, "Logic group not found")
    tree = item.get("tree_model") or {}
    result = simulate_logic_path(tree, body.assignments)
    return {"ok": True, "job_id": job_id, "logic_id": body.logic_id, **result}


@app.post("/api/review/rebuild-understanding")
def api_rebuild_understanding(job_id: str, logic_id: str = "") -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    loop_result = _rebuild_understanding(
        bundle,
        logic_id=logic_id or None,
        trigger="manual_rebuild",
    )
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "job_id": job_id, "understanding_loop": loop_result}


@app.get("/api/review/footnote-materializations")
def api_footnote_materializations(job_id: str, logic_id: str = "") -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    meta = bundle.get("footnote_materializations") or {}
    attachments = list(meta.get("attachments") or [])
    if logic_id:
        attachments = [a for a in attachments if str(a.get("source_logic_id") or "") == logic_id]
    by_logic: dict[str, list[dict[str, Any]]] = {}
    for lb in bundle.get("logic_blocks") or []:
        lid = str(lb.get("id") or "")
        attached = lb.get("attached_logic") or []
        if attached:
            by_logic[lid] = attached
    if logic_id:
        by_logic = {logic_id: by_logic.get(logic_id, [])}
    return {
        "ok": True,
        "job_id": job_id,
        "logic_id": logic_id or None,
        "count": len(attachments),
        "attachments": attachments,
        "by_logic": by_logic,
        "cross_file_resolution": bundle.get("cross_file_resolution") or {},
    }


@app.post("/api/review/attach-reference-file")
async def api_attach_reference_file(
    job_id: str,
    logic_id: str,
    files: list[UploadFile] = File(...),
) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    if not logic_id:
        raise HTTPException(400, "logic_id is required")
    attach_dir = _attachment_dir(job_id, logic_id) / "reference_files"
    attach_dir.mkdir(parents=True, exist_ok=True)
    merged_total: dict[str, int] = {
        "merged_definitions": 0,
        "merged_logic_blocks": 0,
        "merged_footnotes": 0,
        "materialized_count": 0,
    }
    saved: list[str] = []
    for uf in files:
        name = Path(uf.filename or "reference.bin").name
        dest = attach_dir / name
        dest.write_bytes(await uf.read())
        extracted = extract_reference_file(dest)
        result = merge_reference_extract(bundle, extracted, source_logic_id=logic_id, file_name=name)
        if not result.get("ok"):
            raise HTTPException(400, result.get("reason", "Failed to merge reference file"))
        saved.append(name)
        for key in merged_total:
            merged_total[key] += int(result.get(key) or 0)
    loop_result = _rebuild_understanding(bundle, logic_id=logic_id, trigger="attach_reference_file")
    _save_bundle_to_job(job_id, bundle)
    return {
        "ok": True,
        "job_id": job_id,
        "logic_id": logic_id,
        "saved": saved,
        "merge": merged_total,
        "understanding_loop": loop_result,
    }


@app.get("/api/review/path-tc-matrix")
def api_path_tc_matrix(job_id: str, logic_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    if not logic_id:
        raise HTTPException(400, "logic_id is required")
    matrix = build_path_tc_matrix(bundle, logic_id)
    return {"ok": True, "job_id": job_id, "matrix": matrix}


@app.post("/api/review/path-tc-propose")
def api_path_tc_propose(job_id: str, logic_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    if not logic_id:
        raise HTTPException(400, "logic_id is required")
    proposal = build_path_regen_proposals(bundle, logic_id)
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "job_id": job_id, **proposal}


@app.get("/api/review/overview")
def api_review_overview(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    capability = build_capability_summary(b)
    overview = build_overview_dashboard(b, capability)
    return {
        "job_id": job_id,
        "capability_summary": capability,
        "overview": overview,
        "prioritized_issues": prioritize_issues(
            b.get("issues") or [],
            logic_items=b.get("logic_review_items") or [],
            limit=20,
        ),
    }


@app.post("/api/review/diagram-link")
def api_diagram_link(body: DiagramLinkRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    if not body.logic_id:
        raise HTTPException(400, "logic_id is required")
    link = add_diagram_link(
        bundle,
        body.logic_id,
        {
            "from_state": body.from_state,
            "to_state": body.to_state,
            "event": body.event,
            "conditions": body.conditions,
            "edge_key": body.edge_key,
            "note": body.note,
            "review_status": "accepted",
            "source": "diagram_graph",
        },
    )
    loop_result = _rebuild_understanding(bundle, logic_id=body.logic_id, trigger="diagram_link")
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "job_id": job_id, "link": link, "understanding_loop": loop_result, **overlay_payload(bundle, body.logic_id)}


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
        "bundle_version": _get_bundle_version(job_id),
    }


@app.get("/api/review/source-index")
def api_review_source_index(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    idx = b.get("source_index") or build_source_index(b)
    return {"job_id": job_id, "source_index": idx}


@app.get("/api/review/document-graph")
def api_document_graph(job_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    graph = b.get("document_graph") or {}
    return {
        "job_id": job_id,
        "document_graph": graph,
        "feature_enabled": feature_enabled(_cfg(), "document_map", default=True),
    }


@app.get("/api/review/document-graph/node/{node_id}")
def api_document_graph_node(job_id: str, node_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    graph = b.get("document_graph") or {}
    try:
        detail = doc_node_detail(b, graph, node_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    return {"job_id": job_id, "node_id": node_id, "detail": detail}


@app.post("/api/review/document-graph/edges")
def api_document_graph_add_edge(job_id: str, req: DocumentEdgeCreateRequest) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    graph = b.get("document_graph") or {}
    try:
        edge = add_doc_user_edge(
            graph,
            source_id=req.source_id,
            target_id=req.target_id,
            label=req.label or "",
            kind=req.kind or "user_defined",
            note=req.note or "",
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    b["document_graph"] = graph
    _save_bundle_to_job(job_id, b)
    return {"job_id": job_id, "edge": edge, "user_edge_count": graph["summary"]["user_edge_count"]}


@app.patch("/api/review/document-graph/edges/{edge_id}")
def api_document_graph_update_edge(
    job_id: str, edge_id: str, req: DocumentEdgeUpdateRequest
) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    graph = b.get("document_graph") or {}
    try:
        edge = update_doc_user_edge(
            graph, edge_id, label=req.label, kind=req.kind, note=req.note,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    b["document_graph"] = graph
    _save_bundle_to_job(job_id, b)
    return {"job_id": job_id, "edge": edge}


@app.delete("/api/review/document-graph/edges/{edge_id}")
def api_document_graph_delete_edge(job_id: str, edge_id: str) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    graph = b.get("document_graph") or {}
    try:
        delete_doc_user_edge(graph, edge_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    b["document_graph"] = graph
    _save_bundle_to_job(job_id, b)
    return {"job_id": job_id, "deleted": edge_id, "user_edge_count": graph["summary"]["user_edge_count"]}


def _require_library_feature() -> None:
    if not feature_enabled(_cfg(), "library_map", default=True):
        raise HTTPException(403, "Library Map is disabled in config.yaml")


def _library_state_payload(state: dict[str, Any]) -> dict[str, Any]:
    root = state.get("root") or ""
    root_exists = bool(root) and Path(root).expanduser().resolve().is_dir()
    return {
        "version": state.get("version", "3"),
        "root": root,
        "root_exists": root_exists,
        "focus_id": state.get("focus_id", ""),
        "items": list(state.get("items", [])),
        "links": list(state.get("links", [])),
    }


@app.get("/api/library")
def api_library_get() -> dict[str, Any]:
    _require_library_feature()
    state = load_library(WEB_DATA)
    return _library_state_payload(state)


@app.post("/api/library/root")
def api_library_set_root(req: LibraryRootRequest) -> dict[str, Any]:
    _require_library_feature()
    state = load_library(WEB_DATA)
    try:
        library_set_root(state, req.path)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    save_library(WEB_DATA, state)
    return _library_state_payload(state)


@app.get("/api/library/browse-root")
def api_library_browse_root(path: Optional[str] = None) -> dict[str, Any]:
    _require_library_feature()
    try:
        return browse_for_root(path)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/library/browse")
def api_library_browse(path: Optional[str] = None) -> dict[str, Any]:
    _require_library_feature()
    state = load_library(WEB_DATA)
    try:
        return scan_folder_listing(state, path)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/library/items")
def api_library_add_item(req: LibraryItemCreateRequest) -> dict[str, Any]:
    _require_library_feature()
    state = load_library(WEB_DATA)
    try:
        item = library_add_item(state, file_path=req.file or None)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    save_library(WEB_DATA, state)
    return {"item": item, "state": _library_state_payload(state)}


@app.patch("/api/library/items/{item_id}")
def api_library_update_item(item_id: str, req: LibraryItemUpdateRequest) -> dict[str, Any]:
    _require_library_feature()
    state = load_library(WEB_DATA)
    try:
        item = library_update_item(state, item_id, file_path=req.file)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    save_library(WEB_DATA, state)
    return {"item": item, "state": _library_state_payload(state)}


@app.delete("/api/library/items/{item_id}")
def api_library_delete_item(item_id: str) -> dict[str, Any]:
    _require_library_feature()
    state = load_library(WEB_DATA)
    try:
        removed_links = library_delete_item(state, item_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    save_library(WEB_DATA, state)
    return {
        "deleted": item_id,
        "removed_link_count": removed_links,
        "state": _library_state_payload(state),
    }


@app.post("/api/library/focus")
def api_library_set_focus(req: LibraryFocusRequest) -> dict[str, Any]:
    _require_library_feature()
    state = load_library(WEB_DATA)
    try:
        library_set_focus(state, req.item_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    save_library(WEB_DATA, state)
    return _library_state_payload(state)


@app.post("/api/library/links")
def api_library_add_link(req: LibraryLinkCreateRequest) -> dict[str, Any]:
    _require_library_feature()
    state = load_library(WEB_DATA)
    source_id = req.source_id or state.get("focus_id") or ""
    if not source_id:
        # No focus yet → create one to act as anchor.
        anchor = library_add_item(state)
        source_id = anchor["id"]
    try:
        link = library_add_link(
            state,
            source_id=source_id,
            target_id=req.target_id,
            label=req.label,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc))
    save_library(WEB_DATA, state)
    return {"link": link, "state": _library_state_payload(state)}


@app.patch("/api/library/links/{link_id}")
def api_library_update_link(link_id: str, req: LibraryLinkUpdateRequest) -> dict[str, Any]:
    _require_library_feature()
    state = load_library(WEB_DATA)
    try:
        link = library_update_link(state, link_id, label=req.label)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    save_library(WEB_DATA, state)
    return {"link": link, "state": _library_state_payload(state)}


@app.delete("/api/library/links/{link_id}")
def api_library_delete_link(link_id: str) -> dict[str, Any]:
    _require_library_feature()
    state = load_library(WEB_DATA)
    try:
        result = library_delete_link(state, link_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    save_library(WEB_DATA, state)
    return {
        "deleted": link_id,
        "removed_item": result.get("removed_item"),
        "state": _library_state_payload(state),
    }


@app.post("/api/library/upload")
async def api_library_upload(
    item_id: Optional[str] = Query(None),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Receive a file dragged from the OS, copy it into the library root, and
    optionally attach it to an existing slot.
    """
    _require_library_feature()
    state = load_library(WEB_DATA)
    if not state.get("root"):
        raise HTTPException(400, "Set a library root before uploading files.")
    # Persist the upload into a temp file first, then hand off to the helper.
    import tempfile

    suffix = Path(file.filename or "drop.bin").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            tmp.write(chunk)
        tmp_path = Path(tmp.name)
    try:
        dest = library_import_dropped_file(state, tmp_path, original_name=file.filename)
    except ValueError as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(400, str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)
    if item_id:
        try:
            library_update_item(state, item_id, file_path=str(dest))
        except KeyError as exc:
            raise HTTPException(404, str(exc))
    else:
        new_item = library_add_item(state, file_path=str(dest))
        item_id = new_item["id"]
    save_library(WEB_DATA, state)
    return {
        "item_id": item_id,
        "stored_path": str(dest),
        "state": _library_state_payload(state),
    }


@app.get("/api/review/condition-resolve")
def api_review_condition_resolve(
    job_id: str,
    term: str,
    logic_id: str = "",
) -> dict[str, Any]:
    b = _bundle_for_job(job_id)
    return {"job_id": job_id, **resolve_condition(b, term, logic_id=logic_id)}


@app.get("/api/llm/status")
def api_llm_status(light: bool = Query(False)) -> dict[str, Any]:
    cfg = _cfg()
    st = provider_status(cfg, light=light)
    return {
        **st,
        "enabled": llm_enabled_for_assist(cfg),
        "copilot_enabled": copilot_enabled(cfg),
    }


@app.get("/api/m365/status")
def api_m365_status() -> dict[str, Any]:
    return m365_auth.m365_status(_cfg(), user_id=_m365_user_id())


@app.post("/api/m365/setup")
def api_m365_setup(body: M365SetupRequest) -> dict[str, Any]:
    try:
        return m365_auth.save_local_registration(
            _cfg(),
            client_id=body.client_id.strip(),
            tenant_id=body.tenant_id.strip() or "common",
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/m365/setup/reset")
def api_m365_setup_reset() -> dict[str, Any]:
    return m365_auth.clear_local_registration(_cfg(), user_id=_m365_user_id())


@app.post("/api/m365/login/start")
def api_m365_login_start() -> dict[str, Any]:
    try:
        return m365_auth.start_device_login(_cfg(), user_id=_m365_user_id())
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/m365/login/poll")
def api_m365_login_poll() -> dict[str, Any]:
    try:
        return m365_auth.poll_device_login(_cfg(), user_id=_m365_user_id())
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/m365/login/cancel")
def api_m365_login_cancel() -> dict[str, Any]:
    m365_auth.cancel_device_login(user_id=_m365_user_id())
    return {"ok": True, **m365_auth.m365_status(_cfg(), user_id=_m365_user_id())}


@app.post("/api/m365/disconnect")
def api_m365_disconnect() -> dict[str, Any]:
    return m365_auth.disconnect(user_id=_m365_user_id())


class AssistImproveIoRequest(BaseModel):
    candidate_id: str
    expected_input: str = ""
    expected_output: str = ""
    issues: list[dict[str, Any]] = []


@app.post("/api/assist/improve-io")
def api_assist_improve_io(body: AssistImproveIoRequest, job_id: str) -> dict[str, Any]:
    cfg = _cfg()
    result = improve_io(
        cfg,
        candidate_id=body.candidate_id,
        expected_input=body.expected_input,
        expected_output=body.expected_output,
        issues=body.issues,
    )
    return {"job_id": job_id, "candidate_id": body.candidate_id, **result}


@app.post("/api/review/translate-workbook")
def api_translate_workbook(job_id: str, target_language: str = "JP") -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    result = translate_workbook_with_m365(bundle, _cfg(), target_language=target_language)
    if result.get("ok"):
        _save_bundle_to_job(job_id, bundle)
    return {"job_id": job_id, **result}


@app.post("/api/review/workbench-row")
def api_review_workbench_row(body: WorkbookReviewUpdateRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    effective_id = body.candidate_id
    try:
        if body.new_candidate_id or body.test_function is not None or body.event is not None:
            identity = update_candidate_identity(
                bundle,
                body.candidate_id,
                new_candidate_id=body.new_candidate_id,
                test_function=body.test_function,
                event=body.event,
                gtest_state=gtest_state,
            )
            effective_id = identity["candidate_id"]
            if identity.get("renamed_from"):
                _persist_job_gtest_state(job_id, gtest_state)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc

    ai = bundle.setdefault("ai_assists", {})
    overlays = ai.setdefault("candidate_overlays", {})
    overlay = dict(overlays.get(effective_id) or overlays.get(body.candidate_id) or {})
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
    overlays[effective_id] = overlay
    if effective_id != body.candidate_id and body.candidate_id in overlays:
        del overlays[body.candidate_id]

    for cand in bundle.get("test_candidates") or []:
        if cand.get("id") != effective_id:
            continue
        if body.review_status is not None:
            cand["review_status"] = body.review_status
        if body.engineer_confirmation_required is not None:
            cand["review_required"] = str(body.engineer_confirmation_required).lower() in {"yes", "true", "1"}
        if body.use_case is not None:
            cand["use_case_description"] = body.use_case
        break

    if body.remember_io_mapping and (body.expected_input is not None or body.expected_output is not None):
        memory = merge_project_memory(library_root=_library_root(), bundle=bundle, gtest_state=gtest_state)
        harness = gtest_state.get("harness") or {}
        io_map = remember_io_from_text(
            memory,
            expected_input=body.expected_input or "",
            expected_output=body.expected_output or "",
            harness_inputs=str(harness.get("inputs_member") or "in"),
            harness_outputs=str(harness.get("outputs_member") or "out"),
        )
        gtest_state["code_variable_map"] = {**(gtest_state.get("code_variable_map") or {}), **io_map}
        save_bundle_memory(bundle, {**memory, "io_variable_map": io_map})
        _persist_job_gtest_state(job_id, gtest_state)

    _save_bundle_to_job(job_id, bundle)
    return {
        "ok": True,
        "candidate_id": effective_id,
        "overlay": overlay,
        "bundle_version": _get_bundle_version(job_id),
    }


@app.patch("/api/review/test-candidates/{candidate_id}/identity")
def api_update_candidate_identity(
    candidate_id: str,
    body: CandidateIdentityUpdateRequest,
    job_id: str,
) -> dict[str, Any]:
    try:
        sanitize_id(candidate_id, field="candidate_id")
        bundle = _bundle_for_job(job_id)
        gtest_state = _load_job_gtest_state(job_id)
        result = update_candidate_identity(
            bundle,
            candidate_id,
            new_candidate_id=body.new_candidate_id,
            test_function=body.test_function,
            event=body.event,
            gtest_state=gtest_state,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    if result.get("renamed_from"):
        _persist_job_gtest_state(job_id, gtest_state)
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, **result, "bundle_version": _get_bundle_version(job_id)}


@app.get("/api/review/project-memory")
def api_get_project_memory(job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    memory = merge_project_memory(library_root=_library_root(), bundle=bundle, gtest_state=gtest_state)
    return {"ok": True, "job_id": job_id, "project_memory": memory}


@app.put("/api/review/project-memory")
def api_put_project_memory(job_id: str, body: ProjectMemoryUpdateRequest) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    memory = merge_project_memory(library_root=_library_root(), bundle=bundle)
    if body.io_variable_map is not None:
        memory["io_variable_map"] = dict(body.io_variable_map)
    if body.signal_roles is not None:
        memory["signal_roles"] = dict(body.signal_roles)
    if body.shared_preconditions is not None:
        memory["shared_preconditions"] = list(body.shared_preconditions)
    if body.verification_patterns is not None:
        memory["verification_patterns"] = list(body.verification_patterns)
    saved = save_bundle_memory(bundle, memory)
    gtest_state = _load_job_gtest_state(job_id)
    if body.io_variable_map is not None:
        gtest_state["code_variable_map"] = dict(body.io_variable_map)
        _persist_job_gtest_state(job_id, gtest_state)
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "project_memory": saved}


@app.get("/api/review/verification-matrix")
def api_verification_matrix(job_id: str, logic_id: str, language: str = "EN") -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    matrix = build_verification_matrix(bundle, logic_id, language=language)
    memory = merge_project_memory(library_root=_library_root(), bundle=bundle)
    return {
        "ok": True,
        "job_id": job_id,
        **matrix,
        "saved_patterns": [
            p
            for p in (memory.get("verification_patterns") or [])
            if str(p.get("logic_id") or "") in ("", logic_id)
        ],
    }


@app.post("/api/review/promote-verification-pattern")
def api_promote_verification_pattern(job_id: str, body: PromoteVerificationPatternRequest) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    memory = merge_project_memory(library_root=_library_root(), bundle=bundle)
    try:
        row = promote_verification_pattern(
            memory,
            logic_id=body.logic_id,
            given_fingerprint=body.given_fingerprint,
            then_signals=body.then_signals,
            candidate_ids=body.candidate_ids,
            label=body.label,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    save_bundle_memory(bundle, memory)
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "pattern": row, "project_memory": memory}


@app.post("/api/review/promote-precondition")
def api_promote_precondition(job_id: str, body: PromotePreconditionRequest) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    memory = merge_project_memory(library_root=_library_root(), bundle=bundle)
    try:
        row = promote_shared_precondition(
            memory,
            label=body.label,
            expected_input=body.expected_input,
            logic_id=body.logic_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    save_bundle_memory(bundle, memory)
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "precondition": row, "project_memory": memory}


def _library_code_samples(_library_root: Path | None = None) -> list[dict[str, Any]]:
    del _library_root
    path = code_style_samples_path()
    if not path.exists():
        return []
    try:
        data = load_yaml(path)
    except (OSError, ValueError, TypeError):
        return []
    if isinstance(data, dict):
        rows = data.get("samples") or []
        return [r for r in rows if isinstance(r, dict)]
    return []


def _ensure_gtest_workspace_imports(
    bundle: dict[str, Any],
    gtest_state: dict[str, Any],
    *,
    library_root: Path | None,
) -> tuple[dict[str, Any], bool, bool]:
    """One-time library/sample imports. Returns (gtest_state, bundle_dirty, gtest_dirty)."""
    if gtest_state.get("_workspace_imports_done"):
        return gtest_state, False, False

    bundle_dirty = False
    gtest_dirty = False

    _, samples_changed = merge_samples_from_bundle(bundle)
    bundle_dirty = bundle_dirty or samples_changed

    lib_samples = _library_code_samples()
    if lib_samples and not load_code_style_samples(bundle):
        save_code_style_samples(bundle, lib_samples)
        bundle_dirty = True

    preset_path = library_preset_path()
    if preset_path.exists() and not gtest_state.get("harness"):
        try:
            preset = load_yaml(preset_path)
            before_h = json.dumps(gtest_state.get("harness") or {}, sort_keys=True)
            before_m = json.dumps(gtest_state.get("code_variable_map") or {}, sort_keys=True)
            gtest_state = import_library_preset(gtest_state, preset, bundle=bundle)
            after_h = json.dumps(gtest_state.get("harness") or {}, sort_keys=True)
            after_m = json.dumps(gtest_state.get("code_variable_map") or {}, sort_keys=True)
            if before_h != after_h or before_m != after_m:
                gtest_dirty = True
        except (OSError, ValueError, TypeError):
            pass

    gtest_state["_workspace_imports_done"] = True
    return gtest_state, bundle_dirty, gtest_dirty


@app.get("/api/review/code-style-samples")
def api_get_code_style_samples(job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    merge_samples_from_bundle(bundle)
    return {
        "ok": True,
        "job_id": job_id,
        "samples": load_code_style_samples(bundle),
        "code_references_count": len(bundle.get("code_references") or []),
    }


@app.post("/api/review/code-style-samples")
def api_post_code_style_samples(job_id: str, body: CodeStyleSamplesRequest) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    rows = [s.model_dump() for s in body.samples]
    if body.replace:
        saved = save_code_style_samples(bundle, rows)
    else:
        existing = load_code_style_samples(bundle)
        saved = save_code_style_samples(bundle, existing + rows)
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "samples": saved}


@app.post("/api/review/code-style-samples/upload")
async def api_upload_code_style_sample(
    job_id: str,
    file: UploadFile = File(...),
    replace: bool = False,
) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    filename = file.filename or "upload.cpp"
    result = ingest_cpp_upload(
        bundle,
        gtest_state,
        content=text,
        filename=filename,
        replace=replace,
    )
    _persist_job_gtest_state(job_id, gtest_state)
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "job_id": job_id, **result}


@app.get("/api/review/copilot/code/context")
def api_copilot_code_context(job_id: str, candidate_id: str, language: str = "EN") -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    try:
        pack = build_code_context_pack(
            bundle,
            gtest_state,
            candidate_id=candidate_id,
            library_root=_library_root(),
            language=language,
            cfg=_cfg(),
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"ok": True, "job_id": job_id, "context_pack": pack}


@app.post("/api/review/copilot/code/generate")
def api_copilot_code_generate(job_id: str, body: CopilotCodeGenerateRequest) -> dict[str, Any]:
    cfg = _cfg()
    if not m365_auth.is_api_ready(cfg):
        raise HTTPException(403, "Sign in to Microsoft 365 Copilot first.")
    if not m365_auth.is_copilot_chat_entitled():
        raise HTTPException(403, "Microsoft 365 Copilot Chat API is not available for this account.")
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    result = run_copilot_code_generate(
        bundle,
        gtest_state,
        candidate_id=body.candidate_id,
        cfg=cfg,
        library_root=_library_root(),
        engineer_note=body.engineer_note,
        use_baseline=body.use_baseline,
        language=body.language,
        reference_test_name=body.reference_test_name,
        library_code_samples=_library_code_samples(_library_root()),
    )
    return {"job_id": job_id, **result}


@app.post("/api/review/copilot/code/generate-batch")
def api_copilot_code_generate_batch(job_id: str, body: CopilotCodeBatchRequest) -> dict[str, Any]:
    cfg = _cfg()
    if not m365_auth.is_api_ready(cfg):
        raise HTTPException(403, "Sign in to Microsoft 365 Copilot first.")
    if not m365_auth.is_copilot_chat_entitled():
        raise HTTPException(403, "Microsoft 365 Copilot Chat API is not available for this account.")
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    merge_samples_from_bundle(bundle)

    candidate_ids = list(body.candidate_ids or [])
    if not candidate_ids and body.logic_id:
        preview = build_customer_testspec_preview(bundle, language=body.language or "EN")
        candidate_ids = [
            str(r.get("candidate_id") or "")
            for r in preview.get("rows") or []
            if str(r.get("logic_id") or "") == body.logic_id
        ]
    if not candidate_ids:
        preview = build_customer_testspec_preview(bundle, language=body.language or "EN")
        candidate_ids = [str(r.get("candidate_id") or "") for r in preview.get("rows") or []]
    candidate_ids = [c for c in candidate_ids if c]

    result = run_copilot_code_generate_batch(
        bundle,
        gtest_state,
        candidate_ids=candidate_ids,
        cfg=cfg,
        library_root=_library_root(),
        engineer_note=body.engineer_note,
        language=body.language,
        reference_test_name=body.reference_test_name,
        library_code_samples=_library_code_samples(_library_root()),
        persist_drafts=body.persist_drafts,
    )
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.get("/api/review/gtest-workspace")
def api_gtest_workspace(job_id: str, language: str = "EN") -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    bundle_version = _get_bundle_version(job_id)
    gtest_state, bundle_dirty, gtest_dirty = _ensure_gtest_workspace_imports(
        bundle,
        gtest_state,
        library_root=_library_root(),
    )
    if gtest_dirty:
        _persist_job_gtest_state(job_id, gtest_state)
    if bundle_dirty:
        bundle_version = _save_bundle_to_job(job_id, bundle)
    payload = build_workspace_payload(
        bundle,
        gtest_state,
        language=language,
        job_id=job_id,
        bundle_version=bundle_version,
    )
    return {"job_id": job_id, **payload, "bundle_version": bundle_version}


@app.post("/api/review/gtest-generate")
def api_gtest_generate(job_id: str, body: GTestGenerateRequest) -> dict[str, Any]:
    if not body.candidate_id and not body.logic_id:
        raise HTTPException(400, "candidate_id or logic_id required")
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    draft = generate_draft_for_request(
        bundle,
        gtest_state,
        candidate_id=body.candidate_id,
        logic_id=body.logic_id,
        variable_map=body.variable_map,
        language=body.language or "EN",
    )
    return {"ok": True, "job_id": job_id, "draft": draft}


@app.post("/api/review/gtest-suggest-map")
def api_gtest_suggest_map(job_id: str, body: GTestSuggestMapRequest) -> dict[str, Any]:
    if not body.candidate_id:
        raise HTTPException(400, "candidate_id required")
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    code_map = suggest_map_for_request(
        bundle,
        gtest_state,
        candidate_id=body.candidate_id,
        language=body.language or "EN",
    )
    return {"ok": True, "code_variable_map": code_map}


@app.put("/api/review/gtest-draft")
def api_gtest_draft_save(job_id: str, body: GTestDraftSaveRequest) -> dict[str, Any]:
    gtest_state = _load_job_gtest_state(job_id)
    gtest_state = save_draft(
        gtest_state,
        draft_key=body.draft_key,
        draft={
            "source_kind": body.source_kind,
            "test_name": body.test_name,
            "spec_comment_block": body.spec_comment_block,
            "code_body": body.code_body,
            "full_snippet": body.full_snippet,
        },
        engineer_edited=body.engineer_edited,
    )
    _persist_job_gtest_state(job_id, gtest_state)
    return {"ok": True, "job_id": job_id, "draft_key": body.draft_key}


@app.put("/api/review/code-variable-map")
def api_code_variable_map(job_id: str, body: GTestVariableMapRequest) -> dict[str, Any]:
    gtest_state = _load_job_gtest_state(job_id)
    gtest_state["code_variable_map"] = dict(body.code_variable_map)
    _persist_job_gtest_state(job_id, gtest_state)
    return {"ok": True, "code_variable_map": gtest_state["code_variable_map"]}


@app.put("/api/review/gtest-harness")
def api_gtest_harness(job_id: str, body: GTestHarnessRequest) -> dict[str, Any]:
    gtest_state = _load_job_gtest_state(job_id)
    gtest_state["harness"] = {**(gtest_state.get("harness") or {}), **body.harness}
    _persist_job_gtest_state(job_id, gtest_state)
    return {"ok": True, "harness": gtest_state["harness"]}


@app.get("/api/export/gtest-cpp")
def api_export_gtest_cpp(job_id: str, candidate_id: str) -> Response:
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    content = export_single_snippet(bundle, gtest_state, candidate_id)
    filename = f"{candidate_id}.cpp"
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/export/gtest-cpp-bundle")
def api_export_gtest_cpp_bundle(job_id: str) -> Response:
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    content = export_approved_bundle(bundle, gtest_state)
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="alex_generated_tests.cpp"'},
    )


@app.get("/api/library/gtest-preset")
def api_library_gtest_preset_export(job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    memory = merge_project_memory(library_root=_library_root(), bundle=bundle, gtest_state=gtest_state)
    return {
        "ok": True,
        "preset": export_library_preset(
            gtest_state,
            project_memory=memory,
            code_style_samples=load_code_style_samples(bundle),
        ),
    }


@app.post("/api/library/gtest-preset")
def api_library_gtest_preset_import(job_id: str, body: GTestLibraryPresetRequest) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    if body.preset:
        gtest_state.pop("_workspace_imports_done", None)
        gtest_state = import_library_preset(gtest_state, body.preset, bundle=bundle)
        if body.preset.get("project_memory"):
            save_bundle_memory(bundle, import_library_memory(body.preset))
    _persist_job_gtest_state(job_id, gtest_state)
    from web.alex_storage import ensure_alex_data_dir

    ensure_alex_data_dir()
    preset_path = library_preset_path()
    memory = merge_project_memory(library_root=_library_root(), bundle=bundle, gtest_state=gtest_state)
    samples = load_code_style_samples(bundle)
    dump_yaml(
        preset_path,
        export_library_preset(gtest_state, project_memory=memory, code_style_samples=samples),
    )
    dump_yaml(library_memory_path(), export_library_memory(memory))
    if samples:
        dump_yaml(code_style_samples_path(), export_library_code_samples(bundle))
    _save_bundle_to_job(job_id, bundle)
    return {
        "ok": True,
        "harness": gtest_state.get("harness"),
        "code_variable_map": gtest_state.get("code_variable_map"),
        "code_style_samples": load_code_style_samples(bundle),
    }


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
    out_dir = _job_output_dir(job_id)
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
        apply_knowledge(bundle, body.logic_id, body.note, _cfg())
        _save_bundle_to_job(job_id, bundle)
        notes = dict(ai.get("engineer_notes") or {})
    cfg = _cfg()
    result = resolve_definition(
        bundle,
        cfg,
        logic_id=body.logic_id,
        term=body.term.strip(),
        question=body.question.strip() or body.note.strip(),
    )
    if not result.get("ok"):
        raise HTTPException(
            503,
            result.get("error") or "Sign in to Microsoft 365 Copilot on the Review tab.",
        )
    _save_bundle_to_job(job_id, bundle)
    return {
        "job_id": job_id,
        "provider": "m365",
        "status": "completed",
        "result": result.get("result"),
    }


@app.post("/api/review/logic-clarification")
def api_logic_clarification(body: LogicClarificationRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    ai = bundle.setdefault("ai_assists", {})
    notes = ai.setdefault("engineer_notes", {})
    notes[body.logic_id] = body.note.strip()
    engineer_defs = ai.setdefault("engineer_definitions", {})
    missing = _missing_definition_terms(bundle, body.logic_id)
    extracted = _extract_engineer_definitions(
        body.note, body.logic_id, body.term, missing_terms=missing
    )
    for name, meta in extracted.items():
        engineer_defs[name] = meta
    from src.engine.definition_apply import apply_engineer_definitions_to_candidates

    defs_applied = apply_engineer_definitions_to_candidates(bundle, body.logic_id)
    if body.local_only:
        applied = {
            "ok": bool(extracted),
            "provider": "local",
            "preview": False,
            "candidates_updated": defs_applied,
            "failures_remaining": 0,
        }
        if not extracted:
            applied["error"] = (
                "No basic constraint detected. Use patterns like SIG=1, SIG >= 1, < 5, or SIG 1-5."
            )
            applied["ok"] = False
    else:
        applied = apply_knowledge(
            bundle,
            body.logic_id,
            body.note,
            _cfg(),
            provider=body.provider or "m365",
            compile_constraints_first=body.compile_constraints_first,
            preview_only=True,
        )
        if extracted:
            defs_applied += apply_engineer_definitions_to_candidates(bundle, body.logic_id)
    reasoning_session = create_reasoning_session(
        _job_output_dir(job_id),
        bundle,
        logic_id=body.logic_id,
        engineer_note=body.note.strip(),
        provider=body.provider,
    )
    knowledge_apply = get_knowledge_apply_payload(bundle, body.logic_id)
    loop_result = _rebuild_understanding(bundle, logic_id=body.logic_id, trigger="logic_clarification")
    _save_bundle_to_job(job_id, bundle)
    overlay = overlay_payload(bundle, body.logic_id)
    return {
        "ok": True,
        "logic_id": body.logic_id,
        "note": notes[body.logic_id],
        "engineer_definitions": extracted,
        "applied_terms": sorted(extracted.keys()),
        "definitions_applied_to_candidates": defs_applied,
        "candidates_updated": applied.get("candidates_updated", 0),
        "apply_provider": applied.get("provider"),
        "apply_ok": bool(applied.get("ok")),
        "apply_preview": bool(applied.get("preview")),
        "pending_patches": applied.get("pending_patches", 0),
        "reconciliation": applied.get("reconciliation") or knowledge_apply.get("reconciliation"),
        "knowledge_apply_status": knowledge_apply.get("status"),
        "providers_tried": applied.get("providers_tried"),
        "apply_error": applied.get("error"),
        "apply_hint": applied.get("hint"),
        "apply_reason": applied.get("reason"),
        "activation_guide": applied.get("activation_guide"),
        "failures_remaining": applied.get("failures_remaining", 0),
        "retries_used": applied.get("retries_used", 0),
        "reasoning_session": reasoning_session,
        "structured_overlay": overlay.get("overlay"),
        "constraints_accepted": overlay.get("accepted_count", 0),
        "understanding_loop": loop_result,
    }


@app.get("/api/review/structured-overlay")
def api_get_structured_overlay(job_id: str, logic_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    return {"ok": True, **overlay_payload(bundle, logic_id)}


@app.put("/api/review/structured-overlay")
def api_put_structured_overlay(body: StructuredOverlayRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    try:
        out = save_constraints(bundle, body.logic_id, body.constraints)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, **out}


@app.post("/api/review/compile-constraints")
def api_compile_constraints(body: CompileConstraintsRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    applied = compile_accepted_constraints(bundle, body.logic_id, _cfg())
    loop_result = _rebuild_understanding(bundle, logic_id=body.logic_id, trigger="compile_constraints")
    _save_bundle_to_job(job_id, bundle)
    return {"ok": bool(applied.get("ok")), **applied, "logic_id": body.logic_id, "understanding_loop": loop_result}


@app.post("/api/reasoning/start")
def api_reasoning_start(body: ReasoningSessionRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    out_dir = _job_output_dir(job_id)
    session = create_reasoning_session(
        out_dir,
        bundle,
        logic_id=body.logic_id,
        engineer_note=body.note,
        provider=body.provider,
    )
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "job_id": job_id, "session": session}


@app.post("/api/reasoning/continue")
def api_reasoning_continue(body: ReasoningTurnRequest, job_id: str) -> dict[str, Any]:
    out_dir = _job_output_dir(job_id)
    session = append_reasoning_turn(
        out_dir,
        logic_id=body.logic_id,
        role=body.role,
        content=body.content,
        provider=body.provider,
        metadata=body.metadata,
    )
    return {"ok": True, "job_id": job_id, "session": session}


@app.post("/api/reasoning/hypothesis")
def api_reasoning_hypothesis(body: ReasoningHypothesisRequest, job_id: str) -> dict[str, Any]:
    session = append_reasoning_hypothesis(
        _job_output_dir(job_id),
        logic_id=body.logic_id,
        hypothesis=body.hypothesis,
        provider=body.provider,
    )
    latest = (session.get("hypotheses") or [])[-1] if session.get("hypotheses") else {}
    return {
        "ok": bool((latest.get("validation") or {}).get("ok")),
        "job_id": job_id,
        "session": session,
        "validation": latest.get("validation") or {},
    }


@app.get("/api/reasoning/{logic_id}")
def api_reasoning_get(logic_id: str, job_id: str) -> dict[str, Any]:
    session = load_reasoning_session(_job_output_dir(job_id), logic_id)
    if not session:
        raise HTTPException(404, "No reasoning session for this logic group.")
    return {"ok": True, "job_id": job_id, "session": session}


@app.post("/api/reasoning/accept-claims")
def api_reasoning_accept_claims(body: ReasoningAcceptClaimsRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    session = load_reasoning_session(_job_output_dir(job_id), body.logic_id)
    if not session:
        raise HTTPException(404, "No reasoning session for this logic group.")
    hypotheses = session.get("hypotheses") or []
    if not hypotheses:
        raise HTTPException(400, "No hypotheses in session.")
    idx = body.hypothesis_index if body.hypothesis_index >= 0 else len(hypotheses) - 1
    if idx >= len(hypotheses):
        raise HTTPException(400, "Invalid hypothesis_index.")
    hypothesis = (hypotheses[idx].get("hypothesis") or {}) if isinstance(hypotheses[idx], dict) else {}
    result = accept_hypothesis_claims(
        bundle,
        body.logic_id,
        hypothesis,
        claim_indices=body.claim_indices,
    )
    loop_result = _rebuild_understanding(bundle, logic_id=body.logic_id, trigger="hypothesis_accept")
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "job_id": job_id, "logic_id": body.logic_id, "understanding_loop": loop_result, **result}


@app.get("/api/review/knowledge-apply")
def api_get_knowledge_apply(job_id: str, logic_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    payload = get_knowledge_apply_payload(bundle, logic_id)
    return {"ok": True, "job_id": job_id, **payload}


@app.post("/api/review/knowledge-apply/confirm")
def api_confirm_knowledge_apply(body: KnowledgeApplyConfirmRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    from src.engine.definition_apply import apply_engineer_definitions_to_candidates

    result = confirm_pending_knowledge(
        bundle,
        body.logic_id,
        body.patch_indices,
        _cfg(),
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "Failed to apply patches.")
    defs_applied = apply_engineer_definitions_to_candidates(bundle, body.logic_id)
    loop_result = _rebuild_understanding(bundle, logic_id=body.logic_id, trigger="knowledge_apply_confirm")
    _save_bundle_to_job(job_id, bundle)
    return {
        "ok": True,
        "job_id": job_id,
        "logic_id": body.logic_id,
        "definitions_applied_to_candidates": defs_applied,
        "understanding_loop": loop_result,
        **result,
    }


@app.post("/api/review/knowledge-apply/reject")
def api_reject_knowledge_apply(body: KnowledgeApplyConfirmRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    result = reject_pending_knowledge(bundle, body.logic_id)
    _save_bundle_to_job(job_id, bundle)
    return {"ok": True, "job_id": job_id, **result}


@app.get("/api/review/boundary-proposals")
def api_boundary_proposals(job_id: str, logic_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    proposals = propose_boundary_testcases(bundle, logic_id)
    return {"ok": True, "job_id": job_id, "logic_id": logic_id, "proposals": proposals}


@app.get("/api/review/audit-log")
def api_audit_log(job_id: str, logic_id: str | None = None) -> dict[str, Any]:
    """Export engineer/AI actions for compliance review."""
    bundle = _bundle_for_job(job_id)
    ai = bundle.get("ai_assists") or {}
    knowledge = ai.get("knowledge_apply") or {}
    entries = []
    for lid, row in knowledge.items():
        if logic_id and lid != logic_id:
            continue
        entries.append(
            {
                "logic_id": lid,
                "provider": row.get("provider"),
                "status": row.get("status"),
                "source": row.get("source"),
                "candidates_updated": row.get("candidates_updated", 0),
                "patch_count": len(row.get("patches") or []),
                "reconciliation_summary": (row.get("reconciliation") or {}).get("summary"),
            }
        )
    reasoning_sessions = []
    reasoning_dir = _job_output_dir(job_id) / "reasoning"
    if reasoning_dir.exists():
        for path in sorted(reasoning_dir.glob("*/session.json")):
            if logic_id and logic_id not in path.parts:
                continue
            try:
                import json

                session = json.loads(path.read_text(encoding="utf-8"))
                reasoning_sessions.append(
                    {
                        "logic_id": session.get("logic_id"),
                        "status": session.get("status"),
                        "hypothesis_count": len(session.get("hypotheses") or []),
                        "turn_count": len(session.get("turns") or []),
                        "updated_at": session.get("updated_at"),
                    }
                )
            except (OSError, json.JSONDecodeError):
                continue
    user = _current_team_user()
    return {
        "ok": True,
        "job_id": job_id,
        "username": user.username if user else "system",
        "knowledge_apply": entries,
        "reasoning_sessions": reasoning_sessions,
        "engineer_notes": ai.get("engineer_notes") or {},
    }


@app.get("/api/review/m365-brief")
def api_review_m365_brief(job_id: str, logic_id: str) -> dict[str, Any]:
    from web.brief_readiness import validate_brief_readiness

    bundle = _bundle_for_job(job_id)
    ai = bundle.get("ai_assists") or {}
    note = str((ai.get("engineer_notes") or {}).get(logic_id) or "")
    out = export_m365_brief(bundle, logic_id, note)
    out_dir = _job_output_dir(job_id) / "m365_brief" / logic_id
    out_dir.mkdir(parents=True, exist_ok=True)
    brief_path = out_dir / "brief.md"
    brief_path.write_text(out["brief"], encoding="utf-8")
    session = load_reasoning_session(_job_output_dir(job_id), logic_id)
    if not session:
        session = create_reasoning_session(_job_output_dir(job_id), bundle, logic_id=logic_id, engineer_note=note)
    brief_hash = str(session.get("brief_hash") or "")
    evidence_hash = str(session.get("evidence_hash") or "")
    brief_with_header = (
        f"<!-- ALEX job={job_id} logic={logic_id} brief_id={brief_hash[:12]} -->\n\n{out['brief']}"
    )
    readiness = validate_brief_readiness(bundle, logic_id, note, brief_text=brief_with_header)
    return {
        "job_id": job_id,
        "brief_path": str(brief_path),
        "brief_hash": brief_hash,
        "brief_hash_short": brief_hash[:12],
        "evidence_hash": evidence_hash,
        "evidence_hash_short": evidence_hash[:12],
        "brief_with_header": brief_with_header,
        "readiness": readiness,
        **out,
        "brief": brief_with_header,
    }


@app.get("/api/review/copilot/context")
def api_copilot_context(job_id: str, logic_id: str, note: str = "", term: str = "") -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    result = build_context(
        bundle,
        logic_id,
        engineer_note=note,
        focus_term=term,
        cfg=_cfg(),
    )
    _save_bundle_to_job(job_id, bundle)
    return {"job_id": job_id, **result}


@app.post("/api/review/copilot/plan")
def api_copilot_plan(body: CopilotPlanRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    if body.note.strip():
        ai = bundle.setdefault("ai_assists", {})
        ai.setdefault("engineer_notes", {})[body.logic_id] = body.note.strip()
    result = run_plan(
        bundle,
        body.logic_id,
        _cfg(),
        engineer_note=body.note,
        focus_term=body.term,
    )
    if result.get("ok"):
        _save_bundle_to_job(job_id, bundle)
    return {"job_id": job_id, **result}


@app.patch("/api/review/copilot/plan")
def api_copilot_plan_patch(body: CopilotPlanPatchRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    result = update_plan(bundle, body.logic_id, body.plan)
    _save_bundle_to_job(job_id, bundle)
    return {"job_id": job_id, **result}


@app.post("/api/review/copilot/write")
def api_copilot_write(body: CopilotWriteRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    result = run_write(bundle, body.logic_id, _cfg())
    if result.get("ok"):
        _save_bundle_to_job(job_id, bundle)
    return {"job_id": job_id, **result}


@app.post("/api/review/copilot/apply")
def api_copilot_apply_preview(body: CopilotWriteRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    result = run_apply_preview(bundle, body.logic_id)
    return {"job_id": job_id, **result}


@app.post("/api/review/copilot/confirm")
def api_copilot_confirm(body: CopilotConfirmRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    result = run_confirm(bundle, body.logic_id, draft_indices=body.draft_indices)
    if result.get("ok"):
        loop_result = _rebuild_understanding(bundle, logic_id=body.logic_id, trigger="copilot_confirm")
        result["understanding_loop"] = loop_result
        _save_bundle_to_job(job_id, bundle)
    return {"job_id": job_id, **result}


@app.get("/api/review/copilot/session")
def api_copilot_session(job_id: str, logic_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    session = get_copilot_session(bundle, logic_id)
    return {"job_id": job_id, "logic_id": logic_id, "session": session}


@app.post("/api/review/style-samples")
def api_style_samples(body: StyleSamplesRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    saved = save_style_samples(bundle, body.samples)
    _save_bundle_to_job(job_id, bundle)
    return {"job_id": job_id, "ok": True, "samples": saved, "count": len(saved)}


@app.post("/api/review/import-knowledge-patches")
def api_import_knowledge_patches(body: ImportKnowledgeRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    cfg = _cfg()
    try:
        result = import_knowledge_patches(bundle, body.logic_id, body.payload, cfg, preview_only=True)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if result.get("ok"):
        _save_bundle_to_job(job_id, bundle)
    return {"job_id": job_id, "logic_id": body.logic_id, **result}


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
    loop_result = _rebuild_understanding(bundle, logic_id=logic_id, trigger="logic_attachment")
    _save_bundle_to_job(job_id, bundle)
    return {
        "ok": True,
        "logic_id": logic_id,
        "saved": saved,
        "attachments": rows,
        "supplemental_definitions": defs,
        "understanding_loop": loop_result,
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
    out_dir = _job_output_dir(job_id)
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
    if not copilot_enabled(_cfg()):
        return {
            "installed": False,
            "enabled": False,
            "trust_state": "disabled",
            "trust_reason": "GitHub Copilot CLI is disabled in config (assist.copilot.enabled: false).",
        }
    return probe_copilot_cli()


def _copilot_disabled() -> None:
    if not copilot_enabled(_cfg()):
        raise HTTPException(403, "GitHub Copilot CLI is disabled. Set assist.copilot.enabled: true only when approved.")


@app.post("/api/copilot/login")
def api_copilot_login() -> dict[str, Any]:
    _copilot_disabled()
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
    _copilot_disabled()
    cmd = get_copilot_command(command_id)
    if not cmd:
        raise HTTPException(404, f"Copilot command not found: {command_id}")
    return _command_dict(cmd)


@app.post("/api/copilot/verify")
def api_copilot_verify(deep: bool = Query(False)) -> dict[str, Any]:
    _copilot_disabled()
    return verify_copilot_access(ROOT, deep=deep)


@app.post("/api/copilot/assist")
def api_copilot_assist(body: CopilotAssistRequest, job_id: str) -> dict[str, Any]:
    _copilot_disabled()
    bundle = _bundle_for_job(job_id)
    out_dir = _job_output_dir(job_id)
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
    out_dir = _job_output_dir(job_id)
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
    out_dir = _job_output_dir(job_id)
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
    out_dir = _job_output_dir(job_id)
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
    out_dir = _job_output_dir(job_id)
    path = out_dir / "ui_bundle.yaml"
    if not path.exists():
        raise HTTPException(404, "ui_bundle.yaml not found — run analysis first")
    return FileResponse(path, filename="ui_bundle.yaml", media_type="application/x-yaml")


@app.get("/api/export/review-md")
def api_export_review_md(job_id: str) -> FileResponse:
    """Download review markdown zip folder as single file — first file for quick access."""
    job = get_job(job_id)
    out = _job_output_dir(job_id)
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
        "bundle_version": _get_bundle_version(job_id),
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
    overview = build_overview_dashboard(b, capability)
    prioritized = prioritize_issues(issues, logic_items=b.get("logic_review_items") or [], limit=20)
    return {
        "job_id": job_id,
        "summary": {
            **(b.get("summary", {})),
            **workbench,
        },
        "module_name": derive_module_name(b),
        "spec_understanding": rep,
        "top_issues": prioritized[:8],
        "prioritized_issues": prioritized,
        "overview": overview,
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
        ROOT / "sample_inputs" / "input",
        ROOT / "sample_inputs",
    ):
        if not sample.is_dir():
            continue
        for p in sample.iterdir():
            if p.is_file() and is_ingestible_file(p):
                shutil.copy2(p, _uploads_dir() / p.name)
                copied.append(p.name)
    return {
        "files": _classify_uploads(),
        "copied": copied,
        "message": "Sample files copied to uploads (lock files excluded)",
    }
