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

import yaml

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
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
from web.copilot_errors import classify_copilot_error, enrich_error_response
from web.copilot_row_assist import apply_row_draft, preview_row_draft, write_from_row_via_copilot
from src.importers.job_bootstrap import bootstrap_from_bundle_dict, bootstrap_from_testspec_xlsx
from src.importers.customer_testspec_importer import preview_testspec_workbook
from web.job_diagnostic import diagnose_job_bundle, load_bundle_for_diagnostic
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
    bulk_delete_code,
    bulk_regen_comments,
    classify_sync_status,
    export_approved_bundle,
    export_library_preset,
    export_single_snippet,
    generate_draft_for_request,
    import_library_preset,
    library_preset_path,
    load_gtest_state,
    regen_comment_only_draft,
    save_draft,
    save_gtest_state,
    suggest_map_for_request,
    sync_gtest_to_bundle,
    _structured_io_for_candidate,
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
    # Mark any RUNNING generation run from before this server start as PAUSED
    # so the UI can offer Resume remaining after a restart.
    try:
        from web.generation_runs import scan_and_mark_stale
        scan_and_mark_stale(WEB_DATA / "jobs")
    except Exception:  # noqa: BLE001
        pass


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


class ImportTestSpecRequest(BaseModel):
    language: str = "EN"
    module_name: str = ""
    label: str = ""


class ImportBundleRequest(BaseModel):
    label: str = ""


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


class CopilotRowRequest(BaseModel):
    candidate_id: str
    engineer_note: str = ""
    language: str = "EN"


class CopilotApplyRowRequest(BaseModel):
    candidate_id: str
    draft: dict[str, Any]
    language: str = "EN"


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
    copilot_prompt_override: str = ""
    reference_test_name: str = ""
    language: str = "EN"
    from_testcase_only: bool | None = None
    reuse_conversation: bool = False


class CopilotFollowUpRequest(BaseModel):
    logic_id: str = ""
    message: str
    reuse_conversation: bool = True


class CopilotCodeBatchRequest(BaseModel):
    candidate_ids: list[str] = []
    logic_id: str = ""
    engineer_note: str = ""
    copilot_prompt_override: str = ""
    reference_test_name: str = ""
    persist_drafts: bool = False
    language: str = "EN"


class GTestTextReplaceRequest(BaseModel):
    request: str = ""
    from_text: str = ""
    to_text: str = ""
    candidate_id: str = ""
    candidate_ids: list[str] = []
    current_snippet: str = ""
    persist: bool = True
    preview: bool = False


class GTestBulkRequest(BaseModel):
    action: str
    candidate_ids: list[str] = []
    language: str = "EN"
    from_text: str = ""
    to_text: str = ""
    stale_only: bool = False
    persist: bool = True


class CopilotCodeRefineRequest(BaseModel):
    candidate_id: str
    existing_code: str
    instruction: str
    reuse_conversation: bool = True


class M365CopilotTaskRequest(BaseModel):
    kind: str
    payload: dict[str, Any] = {}
    label: str = ""
    logic_id: str = ""
    candidate_id: str = ""
    target_page: str = ""


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


class LogicGenerateRowsRequest(BaseModel):
    logic_id: str
    language: str = "EN"
    ai_branches: list[dict[str, Any]] | None = None
    ai_test_function: str | None = None
    ai_test_group: str | None = None
    clean_obsolete: bool = True


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
    code_status: Optional[str] = None
    generation_source: Optional[str] = None
    quality_results: Optional[list[dict[str, Any]]] = None
    quality_summary: Optional[str] = None
    review_reason: Optional[str] = None
    force_merge: bool = False


class ProjectCodeConfigSaveRequest(BaseModel):
    filename: str
    content: str = ""


class MappingCoverageRequest(BaseModel):
    language: str = "EN"


class LocalTemplateGenerateRequest(BaseModel):
    candidate_ids: Optional[list[str]] = None
    language: str = "EN"


class AiBatchReviewPackRequest(BaseModel):
    candidate_ids: Optional[list[str]] = None
    change_request: str = ""
    language: str = "EN"
    filter: str = "selected"


class GTestQualityCheckRequest(BaseModel):
    candidate_id: str
    full_snippet: str = ""
    language: str = "EN"


class ConfigBundleTextRequest(BaseModel):
    """Accept bundle paste under several JSON keys (Copilot / UI variants)."""

    bundle: str = ""
    text: str = ""
    content: str = ""
    bundle_markdown: str = ""


class ConfigBundleProposeRequest(ConfigBundleTextRequest):
    pass


class ConfigBundleApplyImportRequest(ConfigBundleTextRequest):
    selected_sections: Optional[list[str]] = None


class ConfigBundleApplyRequest(BaseModel):
    mode: str = "apply_selected"
    selected_ids: Optional[list[str]] = None
    allow_removals: bool = False


class AnalyzeProjectContextRequest(BaseModel):
    language: str = "EN"
    force: bool = False
    extra_snippets: Optional[list[str]] = None


class AcceptProposedMappingsRequest(BaseModel):
    items: list[dict[str, Any]] = []
    use_project_override: bool = False


class SmartGenerateCodeRequest(BaseModel):
    language: str = "EN"
    candidate_ids: Optional[list[str]] = None
    auto_accept_high_confidence: bool = True
    analyze_if_sparse: bool = True
    use_api_for_hard: bool = False


class MarkCodeExemplarRequest(BaseModel):
    candidate_id: str
    language: str = "EN"


class ExemplarBatchPromptRequest(BaseModel):
    language: str = "EN"
    candidate_ids: Optional[list[str]] = None
    engineer_note: str = ""
    scope: str = "filter"
    group_key: str = ""
    group_field: str = "test_group"


class ExemplarBatchImportRequest(BaseModel):
    content: str
    language: str = "EN"
    candidate_ids: Optional[list[str]] = None
    scope: str = "filter"
    group_key: str = ""
    group_field: str = "test_group"


class ExemplarBatchApiRequest(BaseModel):
    language: str = "EN"
    candidate_ids: Optional[list[str]] = None
    engineer_note: str = ""
    scope: str = "filter"
    group_key: str = ""
    group_field: str = "test_group"


class CopilotBatchPromptRequest(BaseModel):
    language: str = "EN"
    candidate_ids: Optional[list[str]] = None
    engineer_note: str = ""
    batch_size: int = 1
    skip_saved: bool = False
    scope: str = "filter"
    group_key: str = ""
    group_field: str = "test_group"
    allow_missing_sample: bool = False
    slim_prompt: bool = True
    prompt_budget: int = 5000


class CopilotBatchImportRequest(BaseModel):
    content: str
    language: str = "EN"
    candidate_ids: Optional[list[str]] = None
    scope: str = "filter"
    group_key: str = ""
    group_field: str = "test_group"


class CopilotBatchApiRequest(BaseModel):
    language: str = "EN"
    candidate_ids: Optional[list[str]] = None
    engineer_note: str = ""
    clarification_note: str = ""
    batch_size: int = 1
    skip_saved: bool = False
    scope: str = "filter"
    group_key: str = ""
    group_field: str = "test_group"
    allow_missing_sample: bool = True
    slim_prompt: bool = True
    prompt_budget: int = 5000


class TestCodeApprovalRequest(BaseModel):
    candidate_ids: Optional[list[str]] = None
    language: str = "EN"


class LearnedMappingRequest(BaseModel):
    term: str
    code: str
    use_project_override: bool = False


class LearnedRuleRequest(BaseModel):
    rule_text: str
    context: str = ""


class ConfigVersionRollbackRequest(BaseModel):
    config_version_id: str


class ConfigImprovementPromptRequest(BaseModel):
    change_request: str = ""
    language: str = "EN"


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


def _m365_copilot_gate() -> dict[str, Any]:
    cfg = _cfg()
    uid = _m365_effective_user_id(cfg)
    return m365_auth.m365_status(cfg, user_id=uid)


def _copilot_gate_response(
    *,
    m365_st: dict[str, Any] | None = None,
    bundle: dict[str, Any] | None = None,
    logic_id: str = "",
    has_context: bool = True,
    has_plan: bool = True,
    raw_error: str = "",
    http_status: int | None = None,
) -> dict[str, Any] | None:
    st = m365_st if m365_st is not None else _m365_copilot_gate()
    if not st.get("api_ready"):
        return classify_copilot_error(m365_ready=False)
    if st.get("copilot_chat_entitled") is False:
        return classify_copilot_error(m365_ready=True, copilot_entitled=False)
    if bundle is not None:
        has_candidates = bool(bundle.get("test_candidates"))
        if not has_candidates:
            return classify_copilot_error(
                m365_ready=True,
                copilot_entitled=True,
                has_bundle=True,
                has_candidates=False,
            )
        if logic_id and not has_context:
            has_logic = any(
                str(b.get("id") or "") == logic_id for b in bundle.get("logic_blocks") or []
            )
            return classify_copilot_error(
                m365_ready=True,
                copilot_entitled=True,
                has_bundle=True,
                has_candidates=has_candidates,
                has_logic_id=has_logic,
                has_context_pack=False,
            )
    if raw_error:
        return classify_copilot_error(
            m365_ready=True,
            copilot_entitled=True,
            has_bundle=True,
            has_context_pack=has_context,
            has_plan=has_plan,
            raw_error=raw_error,
            http_status=http_status,
        )
    return None


def _load_job_gtest_state(job_id: str) -> dict[str, Any]:
    return load_gtest_state(_job_output_dir(job_id), _cfg())


def _persist_job_gtest_state(job_id: str, gtest_state: dict[str, Any]) -> dict[str, Any]:
    save_gtest_state(_job_output_dir(job_id), gtest_state)
    bundle = _bundle_for_job(job_id)
    sync_gtest_to_bundle(bundle, gtest_state)
    _save_bundle_to_job(job_id, bundle)
    return gtest_state


def _smart_workflow_run_report_payload(
    job_id: str,
    gtest_state: dict[str, Any],
    bundle: dict[str, Any],
    *,
    event: str | None = None,
    event_data: dict[str, Any] | None = None,
    language: str = "EN",
) -> dict[str, Any]:
    from web.test_code_smart_workflow import (
        build_smart_workflow_run_report,
        format_smart_workflow_run_report_markdown,
        record_smart_workflow_run,
    )

    if event:
        record_smart_workflow_run(gtest_state, event, event_data or {})
    report = build_smart_workflow_run_report(
        bundle, gtest_state, _job_output_dir(job_id), language=language
    )
    return {
        "run_report": report,
        "run_report_markdown": format_smart_workflow_run_report_markdown(report, job_id=job_id),
    }


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


def _m365_effective_user_id(cfg: dict[str, Any] | None = None) -> str | None:
    """Prefer signed-in team user, but use legacy default M365 session if that is the only valid token."""
    uid = _m365_user_id()
    if not uid:
        return None
    c = cfg or _cfg()
    try:
        if m365_auth.is_api_ready(c, user_id=uid):
            return uid
        if m365_auth.is_api_ready(c, user_id=None):
            return None
    except Exception:
        return uid
    return uid


def _m365_api_error(exc: Exception) -> HTTPException:
    """Never leak raw 500 for known M365 login/network failures."""
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, ValueError):
        return HTTPException(400, str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(400, str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(403, str(exc))
    if isinstance(exc, OSError):
        return HTTPException(
            500,
            f"Server cannot write M365 session files. Check web_data permissions. Detail: {exc}",
        )
    return HTTPException(500, f"M365 error ({type(exc).__name__}): {exc}")


def _llm_enabled_for_assist(cfg: dict[str, Any]) -> bool:
    return feature_enabled(cfg, "ollama_assist", default=False) or bool(cfg.get("llm", {}).get("enabled"))


def _github_copilot_cli_enabled(cfg: dict[str, Any]) -> bool:
    assist = cfg.get("assist") if isinstance(cfg.get("assist"), dict) else {}
    copilot = assist.get("copilot") if isinstance(assist.get("copilot"), dict) else {}
    return bool(copilot.get("enabled", False))


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


def _save_bundle_to_job(job_id: str, bundle: dict[str, Any], *, expected_version: int | None = None, force: bool = False) -> int:
    if not force:
        if expected_version is None:
            expected_version = parse_if_match_version()
    with _job_write_lock(job_id):
        current = _get_bundle_version(job_id)
        if not force and expected_version is not None and expected_version != current:
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


def _finalize_import_job(job_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    """Persist imported bundle and mark job ready."""
    from web.bundle_store import save_split_bundle

    bundle = ensure_enriched_bundle(bundle)
    out_dir = _job_output_dir(job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    dump_yaml(out_dir / "ui_bundle.yaml", bundle)
    ver = save_split_bundle(out_dir, bundle)
    summary = bundle.get("summary") or {}
    update_job(
        job_id,
        status="done",
        progress=100,
        current_step="Imported — ready for edit",
        bundle=bundle,
        output_dir=out_dir,
        bundle_version=ver,
        warnings=summary.get("warnings", 0),
        errors=summary.get("errors", 0),
    )
    append_log(job_id, f"Import complete: {summary.get('test_candidates', 0)} test case(s)")
    return {"job_id": job_id, "status": "completed", "bundle_version": ver, "summary": summary}


def _infer_import_language(preview: dict[str, Any]) -> str:
    """Detect JP team template from header row text."""
    jp_markers = ("機能テスト", "手順", "入力に対する期待値", "ユーザケース", "テストグループ")
    for sheet in preview.get("sheets") or []:
        blob = " ".join(sheet.get("headers_found") or [])
        if any(m in blob for m in jp_markers):
            return "JP"
    return "EN"


@app.post("/api/jobs/import-testspec")
async def api_import_testspec(
    file: UploadFile = File(...),
    language: str = Query(""),
    module_name: str = Query(""),
    label: str = Query(""),
) -> dict[str, Any]:
    """Bootstrap a job from an existing Final TestSpec xlsx without full analyze."""
    name = (file.filename or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Upload a .xlsx or .xlsm TestSpec workbook.")
    user = _current_team_user()
    created_by = user.username if user else "system"
    job = create_job(created_by=created_by)
    out_dir = _job_output_dir(job.job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    update_job(job.job_id, output_dir=out_dir, status="running", current_step="Importing TestSpec…")
    dest = out_dir / "import" / (file.filename or "TestSpec.xlsx")
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    dest.write_bytes(content)
    preview = preview_testspec_workbook(dest)
    if not preview.get("ok"):
        update_job(job.job_id, status="error", error_message="TestSpec header mismatch", current_step="Import failed")
        raise HTTPException(
            400,
            detail={
                "error": "TestSpec column headers not recognized (EN export or JP 機能テスト template).",
                "preview": preview,
            },
        )
    lang = (language or "").strip().upper() or _infer_import_language(preview)
    try:
        bundle = bootstrap_from_testspec_xlsx(
            dest,
            language=lang,
            module_name=module_name or label,
        )
    except Exception as exc:  # noqa: BLE001
        update_job(job.job_id, status="error", error_message=str(exc), current_step="Import failed")
        raise HTTPException(400, f"Could not import TestSpec: {exc}") from exc
    if not bundle.get("test_candidates"):
        update_job(job.job_id, status="error", error_message="No test rows imported", current_step="Import failed")
        raise HTTPException(
            400,
            detail={
                "error": "No test case rows found. Check sheet has data under Test Function / UseCase columns.",
                "preview": preview,
                "sheet_summary": (bundle.get("excel_import") or {}).get("sheets") or [],
            },
        )
    result = _finalize_import_job(job.job_id, bundle)
    result["bootstrap_source"] = "imported_testspec"
    result["sheet_summary"] = (bundle.get("excel_import") or {}).get("sheets") or []
    result["export_language"] = bundle.get("export_language") or lang
    result["import_language"] = lang
    return result


@app.post("/api/jobs/import-bundle")
async def api_import_bundle(
    file: UploadFile = File(...),
    label: str = Query(""),
) -> dict[str, Any]:
    """Bootstrap a job from ui_bundle.yaml without full analyze."""
    name = (file.filename or "").lower()
    if not name.endswith((".yaml", ".yml")):
        raise HTTPException(400, "Upload ui_bundle.yaml or .yml file.")
    user = _current_team_user()
    created_by = user.username if user else "system"
    job = create_job(created_by=created_by)
    out_dir = _job_output_dir(job.job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    update_job(job.job_id, output_dir=out_dir, status="running", current_step="Importing bundle…")
    raw = await file.read()
    try:
        imported = yaml.safe_load(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        update_job(job.job_id, status="error", error_message=str(exc))
        raise HTTPException(400, f"Invalid YAML: {exc}") from exc
    if not isinstance(imported, dict):
        raise HTTPException(400, "Bundle YAML must be a mapping/object.")
    bundle = bootstrap_from_bundle_dict(imported, source="imported_yaml", label=label or name)
    result = _finalize_import_job(job.job_id, bundle)
    result["bootstrap_source"] = "imported_yaml"
    return result


@app.get("/api/jobs/{job_id}/diagnostic")
def api_job_diagnostic(job_id: str) -> dict[str, Any]:
    _assert_job_access(job_id)
    out_dir = _job_output_dir(job_id)
    bundle = load_bundle_for_diagnostic(out_dir)
    if not bundle:
        raise HTTPException(404, "No bundle for this job.")
    return {"job_id": job_id, "diagnostic": diagnose_job_bundle(bundle, uploads_dir=_uploads_dir())}


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


@app.get("/api/review/logic-coverage")
def api_logic_coverage(job_id: str, logic_id: str = "") -> dict[str, Any]:
    from src.engine.logic_coverage import build_logic_coverage_item, build_logic_coverage_list

    bundle = _bundle_for_job(job_id)
    items = bundle.get("logic_review_items") or []

    dedup_diag: dict[str, Any] = {}
    if logic_id:
        item = next(
            (i for i in items if str(i.get("logic_id") or "") == logic_id), None
        )
        if not item:
            raise HTTPException(404, f"Logic group not found: {logic_id}")
        coverage = [build_logic_coverage_item(item)]
    else:
        coverage = build_logic_coverage_list(bundle, dedup_diag)

    default_id = str(items[0].get("logic_id") or "") if items else ""
    total_branches = sum(c["branch_count"] for c in coverage)
    auto_gen = sum(
        sum(1 for b in c["branches"] if b.get("auto_generatable"))
        for c in coverage
    )
    unresolved_groups = sum(1 for c in coverage if c["unresolved_count"] > 0)

    return {
        "ok": True,
        "job_id": job_id,
        "logic_coverage": coverage,
        "selected_logic_id": logic_id or default_id,
        "diagnostics": {
            "group_count": len(coverage),
            "total_branches": total_branches,
            "auto_generatable_branches": auto_gen,
            "groups_with_unresolved": unresolved_groups,
            **dedup_diag,
        },
    }


_AUTO_SOURCE_VALUES = frozenset(
    {"logic_branch_generator", "ai_branch_generator", "auto", "generated", "logic_coverage"}
)
_OBSOLETE_ID_RE = re.compile(r"^TC_(BRANCH|PM)_\d+$", re.IGNORECASE)
_GENERATED_ID_RE = re.compile(r"^TC_[A-Z0-9_]+_[NAB]\d{2,3}$", re.IGNORECASE)


def _is_safe_to_archive(cand: dict[str, Any], overlays: dict[str, Any]) -> bool:
    """Return True only if this candidate is safe to remove as obsolete generated row.

    Safety rules (all must hold):
    - status is not approved/confirmed
    - no user notes / manual edits
    - no exported flag
    - source is an auto-generator or candidate_id matches old generated patterns
    - not linked to Test Code
    """
    status = str(cand.get("status") or "")
    if status in ("approved", "confirmed", "removed"):
        return False
    # Do not remove manually confirmed review status
    review_status = str(cand.get("review_status") or "")
    if review_status in ("approved", "confirmed", "blocked"):
        return False
    # Do not remove if user has added notes
    if cand.get("user_notes") or cand.get("notes"):
        return False
    # Do not remove if exported
    if cand.get("exported_at") or cand.get("exported"):
        return False
    # Do not remove if linked to Test Code
    if cand.get("test_code_ref") or cand.get("gtest_ref"):
        return False
    # Do not remove if marked as manually edited
    if cand.get("manually_edited") or cand.get("last_edited_by"):
        return False
    cid = str(cand.get("id") or "")
    source = str(cand.get("source") or "")
    overlay = overlays.get(cid) or {}
    ov_source = str(overlay.get("provider") or "")
    is_auto_source = source in _AUTO_SOURCE_VALUES or ov_source in _AUTO_SOURCE_VALUES
    is_old_id = bool(_OBSOLETE_ID_RE.match(cid)) or bool(_GENERATED_ID_RE.match(cid))
    return is_auto_source or is_old_id


def _find_existing_logic_row(
    bundle: dict[str, Any],
    logic_id: str,
    branch_id: str,
    candidate_id: str,
    event: str,
) -> dict[str, Any] | None:
    """Return an existing non-removed candidate that matches this branch, or None."""
    overlays = (bundle.get("ai_assists") or {}).get("candidate_overlays") or {}
    event_lower = event.lower()
    branch_lower = branch_id.lower()
    for cand in bundle.get("test_candidates") or []:
        if str(cand.get("status") or "") == "removed":
            continue
        cid = str(cand.get("id") or "")
        overlay = overlays.get(cid) or {}
        trace = cand.get("traceability") or {}
        ov_logic = str(overlay.get("logic_id") or trace.get("logic_id") or "")
        if ov_logic != logic_id:
            continue
        if candidate_id and cid == candidate_id:
            return cand
        cand_event = str(cand.get("event") or "").lower()
        if branch_lower and branch_lower in cand_event:
            return cand
        if event_lower and cand_event == event_lower:
            return cand
    return None


@app.post("/api/review/logic-coverage/generate-rows")
def api_logic_generate_rows(body: LogicGenerateRowsRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    items = bundle.get("logic_review_items") or []
    logic_id = str(body.logic_id or "").strip()
    if not logic_id:
        raise HTTPException(400, "logic_id is required")

    item = next((i for i in items if str(i.get("logic_id") or "") == logic_id), None)
    if not item:
        raise HTTPException(404, f"Logic group not found: {logic_id!r}")

    control_name = str(item.get("control_name") or logic_id)
    ctrl_slug = re.sub(r"[^A-Z0-9]", "_", control_name.upper())[:15].strip("_")

    overlays = bundle.setdefault("ai_assists", {}).setdefault("candidate_overlays", {})
    candidates: list[dict[str, Any]] = bundle.setdefault("test_candidates", [])

    # ── Part E: clean obsolete generated rows for this logic group ───────────
    removed_obsolete = 0
    kept_manual = 0
    kept_confirmed = 0
    kept_unknown_source = 0

    if body.clean_obsolete:
        linked_ids: set[str] = set()
        for cand in candidates:
            cid = str(cand.get("id") or "")
            ov = overlays.get(cid) or {}
            trace = cand.get("traceability") or {}
            ov_logic = str(ov.get("logic_id") or trace.get("logic_id") or "")
            if ov_logic == logic_id:
                linked_ids.add(cid)

        new_candidates: list[dict[str, Any]] = []
        for cand in candidates:
            cid = str(cand.get("id") or "")
            if cid not in linked_ids:
                new_candidates.append(cand)
                continue
            if _is_safe_to_archive(cand, overlays):
                # Mark as removed rather than hard-delete
                cand_copy = dict(cand)
                cand_copy["status"] = "removed"
                cand_copy["archive_reason"] = "obsolete_generated"
                new_candidates.append(cand_copy)
                overlays.pop(cid, None)
                removed_obsolete += 1
            else:
                new_candidates.append(cand)
                st = str(cand.get("status") or "")
                rs = str(cand.get("review_status") or "")
                if rs in ("approved", "confirmed") or st in ("approved", "confirmed"):
                    kept_confirmed += 1
                elif cand.get("manually_edited") or cand.get("last_edited_by") or cand.get("user_notes"):
                    kept_manual += 1
                else:
                    kept_unknown_source += 1

        bundle["test_candidates"] = new_candidates
        candidates = new_candidates

    existing_ids = {str(c.get("id") or "") for c in candidates if str(c.get("status") or "") != "removed"}

    generated = 0
    skipped_existing = 0
    skipped_unresolved = 0
    skipped_no_suggestion = 0

    if body.ai_branches is not None:
        # ── AI branch path ──────────────────────────────────────────────────
        test_fn = str(body.ai_test_function or control_name)
        test_grp = str(body.ai_test_group or control_name)

        for branch in body.ai_branches:
            auto_gen = bool(branch.get("auto_generatable", True))
            unresolved = branch.get("unresolved_terms") or []
            if not auto_gen or unresolved:
                skipped_unresolved += 1
                continue

            branch_id = str(branch.get("branch_id") or "")
            event_raw = str(branch.get("event") or "")
            event = f"{branch_id} - {event_raw}" if branch_id and event_raw else (event_raw or branch_id)
            expected_input = str(branch.get("expected_input") or "")
            expected_output = str(branch.get("expected_output") or "")
            path_summary = str(branch.get("path_summary") or "")

            if _find_existing_logic_row(bundle, logic_id, branch_id, "", event):
                skipped_existing += 1
                continue

            n = 1
            while f"TC_{ctrl_slug}_B{n:02d}" in existing_ids:
                n += 1
            cid = f"TC_{ctrl_slug}_B{n:02d}"

            candidates.append({
                "id": cid,
                "status": "candidate",
                "source": "ai_branch_generator",
                "test_function": test_fn,
                "event": event,
                "use_case_description": "Branch coverage",
                "precondition": [],
                "operation": {"given": [], "when": []},
                "expectation": [],
                "traceability": {
                    "logic_id": logic_id,
                    "control_name": control_name,
                    "logic_branch": branch_id,
                },
                "why_recommended": [f"AI: {path_summary[:120]}"] if path_summary else [f"Generated from AI branch {branch_id}"],
                "confidence": "medium",
                "review_required": True,
                "review_status": "pending",
                "engineer_confirmation_required": "no",
            })
            overlays[cid] = {
                "provider": "ai_branch_generator",
                "logic_id": logic_id,
                "control_name": control_name,
                "en": {
                    "use_case": "Branch coverage",
                    "operation": "",
                    "expected_input": expected_input,
                    "expected_output": expected_output,
                },
                "changed_fields": ["UseCase", "ExpectedInput", "ExpectedOutput"],
                "review_status_override": "pending",
                "test_group": test_grp,
            }
            existing_ids.add(cid)
            generated += 1
    else:
        # ── Deterministic branch path ────────────────────────────────────────
        from src.engine.logic_coverage import build_logic_coverage_item

        coverage = build_logic_coverage_item(item)
        control_name = coverage["control_name"]
        branches = coverage.get("branches") or []

        for branch in branches:
            if not branch.get("auto_generatable"):
                skipped_unresolved += 1
                continue
            tc = branch.get("suggested_testcase")
            if not tc:
                skipped_no_suggestion += 1
                continue

            branch_id = str(branch.get("branch_id") or "")
            cid = str(tc.get("candidate_id") or "").strip()
            event = str(tc.get("event") or "")

            if _find_existing_logic_row(bundle, logic_id, branch_id, cid, event) or (cid and cid in existing_ids):
                skipped_existing += 1
                continue

            if not cid or not re.match(r"^[A-Za-z0-9_.-]+$", cid) or cid in existing_ids:
                n = 1
                while f"TC_{ctrl_slug}_B{n:02d}" in existing_ids:
                    n += 1
                cid = f"TC_{ctrl_slug}_B{n:02d}"

            candidates.append({
                "id": cid,
                "status": "candidate",
                "source": "logic_branch_generator",
                "test_function": str(tc.get("test_function") or control_name),
                "event": event,
                "use_case_description": str(tc.get("use_case") or "Branch coverage"),
                "precondition": [],
                "operation": {"given": [], "when": []},
                "expectation": [],
                "traceability": {
                    "logic_id": logic_id,
                    "control_name": control_name,
                    "logic_branch": branch_id,
                },
                "why_recommended": [f"Generated from branch {branch_id}"],
                "confidence": "medium",
                "review_required": True,
                "review_status": "pending",
            })
            overlays[cid] = {
                "provider": "logic_branch_generator",
                "logic_id": logic_id,
                "control_name": control_name,
                "en": {
                    "use_case": str(tc.get("use_case") or "Branch coverage"),
                    "operation": "",
                    "expected_input": str(tc.get("expected_input") or ""),
                    "expected_output": str(tc.get("expected_output") or ""),
                },
                "changed_fields": ["UseCase", "ExpectedInput", "ExpectedOutput"],
                "review_status_override": "pending",
            }
            existing_ids.add(cid)
            generated += 1

    if generated:
        _save_bundle_to_job(job_id, bundle)

    return {
        "ok": True,
        "generated": generated,
        "skipped_existing": skipped_existing,
        "skipped_unresolved": skipped_unresolved,
        "skipped_no_suggestion": skipped_no_suggestion,
        "removed_obsolete_generated": removed_obsolete,
        "kept_manual": kept_manual,
        "kept_confirmed": kept_confirmed,
        "kept_unknown_source": kept_unknown_source,
    }


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
        "enabled": _llm_enabled_for_assist(cfg),
        "copilot_enabled": _github_copilot_cli_enabled(cfg),
    }


@app.get("/api/m365/status")
def api_m365_status() -> dict[str, Any]:
    try:
        cfg = _cfg()
        return m365_auth.m365_status(cfg, user_id=_m365_effective_user_id(cfg))
    except Exception as exc:
        raise _m365_api_error(exc) from exc


@app.post("/api/m365/copilot-probe")
def api_m365_copilot_probe() -> dict[str, Any]:
    """Verify Graph Copilot conversation + chat works for the signed-in account."""
    from web.m365_copilot import probe_copilot_api

    cfg = _cfg()
    uid = _m365_effective_user_id(cfg)
    st = m365_auth.m365_status(cfg, user_id=uid)
    if not st.get("api_ready"):
        return {"ok": False, **classify_copilot_error(m365_ready=False)}
    result = probe_copilot_api(cfg, user_id=uid)
    status = m365_auth.m365_status(cfg, user_id=uid)
    if not result.get("ok"):
        enriched = enrich_error_response(
            result,
            m365_ready=True,
            copilot_entitled=bool(status.get("copilot_chat_entitled")),
            raw_error=str(result.get("error") or result.get("entitlement_hint") or ""),
            http_status=int(result.get("graph_status") or 0) or None,
        )
        return {**enriched, **status}
    return {**result, **status}


@app.get("/api/m365/connectivity")
def api_m365_connectivity() -> dict[str, Any]:
    """Ping Microsoft HTTPS — diagnose SSL/firewall on Ubuntu."""
    return m365_auth.probe_microsoft_connectivity()


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
        return m365_auth.start_device_login(_cfg(), user_id=_m365_user_id(), include_copilot_scopes=True)
    except Exception as exc:
        raise _m365_api_error(exc) from exc


@app.post("/api/m365/login/copilot-start")
def api_m365_login_copilot_start() -> dict[str, Any]:
    """Device login with Graph Copilot delegated scopes (requires IT admin consent)."""
    try:
        return m365_auth.start_copilot_device_login(_cfg(), user_id=_m365_user_id())
    except Exception as exc:
        raise _m365_api_error(exc) from exc


@app.post("/api/m365/login/poll")
def api_m365_login_poll() -> dict[str, Any]:
    try:
        return m365_auth.poll_device_login(_cfg(), user_id=_m365_user_id())
    except Exception as exc:
        raise _m365_api_error(exc) from exc


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
    m365_st = _m365_copilot_gate()
    if not m365_st.get("api_ready"):
        return {"job_id": job_id, **classify_copilot_error(m365_ready=False)}
    if m365_st.get("copilot_chat_entitled") is False:
        return {"job_id": job_id, **classify_copilot_error(m365_ready=True, copilot_entitled=False)}
    if m365_st.get("copilot_api_probe_ok") is not True:
        return {
            "job_id": job_id,
            "ok": False,
            "error_category": "m365_missing_scopes" if m365_st.get("copilot_scopes_granted") is False else "m365_not_ready",
            "error": str(m365_st.get("copilot_api_probe_error") or "Copilot API is not authorized or has not passed probe."),
            "user_action": "Open Review tab, Authorize Copilot API, then Test Copilot API before Generate selected.",
        }
    cfg = _cfg()
    result = improve_io(
        cfg,
        candidate_id=body.candidate_id,
        expected_input=body.expected_input,
        expected_output=body.expected_output,
        issues=body.issues,
    )
    if not result.get("ok"):
        result = enrich_error_response(
            result,
            m365_ready=True,
            copilot_entitled=True,
            raw_error=str(result.get("error") or ""),
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

    # Mark generated code stale if testcase I/O changed
    stale_cids: list[str] = []
    if lang_payload.get("expected_input") is not None or lang_payload.get("expected_output") is not None:
        try:
            from src.importers.customer_testspec_importer import compute_spec_hash, build_structured_io
            from web.gtest_workspace import _workbench_row_for_candidate

            gtest_state = _load_job_gtest_state(job_id)
            draft = (gtest_state.get("drafts") or {}).get(effective_id) or {}
            if draft.get("spec_hash"):
                wb = _workbench_row_for_candidate(bundle, effective_id, language=language)
                if wb:
                    structured = build_structured_io(
                        no=str(wb.get("no") or ""),
                        operation=str(wb.get("operation") or ""),
                        expected_input=str(wb.get("expected_input") or ""),
                        expected_output=str(wb.get("expected_output") or ""),
                        remarks="",
                    )
                    new_hash = compute_spec_hash(structured)
                    if new_hash != str(draft.get("spec_hash") or ""):
                        # Testcase I/O changed after code was generated → mark draft stale
                        from web.gtest_workspace import save_draft as _save_draft
                        _save_draft(
                            gtest_state,
                            draft_key=effective_id,
                            draft={
                                **draft,
                                "code_status": "NEEDS_REVIEW" if draft.get("code_status") == "SAVED" else draft.get("code_status", "NEEDS_REVIEW"),
                                "issue_reason": "testcase_changed_after_generation",
                                "review_reason": "Testcase content changed after code generation. Regenerate or review.",
                            },
                            engineer_edited=False,
                            wrap_markers=False,
                        )
                        _persist_job_gtest_state(job_id, gtest_state)
                        stale_cids.append(effective_id)
        except Exception:
            pass  # stale detection is best-effort

    return {
        "ok": True,
        "candidate_id": effective_id,
        "overlay": overlay,
        "bundle_version": _get_bundle_version(job_id),
        "stale_testcode_cids": stale_cids,
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


# ---------------------------------------------------------------------------
# Multi-file project context endpoints
# ---------------------------------------------------------------------------

@app.post("/api/review/project-context-files/upload")
async def api_upload_project_context_files(
    job_id: str,
    files: list[UploadFile] = File(...),
) -> dict[str, Any]:
    """Upload project context files and automatically extract + apply memory.

    Returns HTTP 200 always. If conflicts are detected, status is
    'partial_applied_with_conflicts'; non-conflicting bullets are still applied.
    """
    from web.project_context_files import (
        build_memory_sections_from_files,
        compute_extraction_summary,
        is_accepted_extension,
        process_file,
    )
    from web.project_testcode_memory import (
        load_memory_for_job,
        merge_with_conflict_check,
        save_memory_for_job,
    )

    gtest_state = _load_job_gtest_state(job_id)
    results: list[dict[str, Any]] = []
    skipped: list[str] = []

    for file in files:
        filename = file.filename or "unknown"
        if not is_accepted_extension(filename):
            skipped.append(filename)
            continue
        raw = await file.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        desc = process_file(filename, text)
        desc["content"] = text[:8000]
        results.append(desc)

    # Persist file descriptors + content
    stored = gtest_state.setdefault("project_context_files", [])
    for desc in results:
        stored = [f for f in stored if f.get("filename") != desc["filename"]]
        stored.append({k: v for k, v in desc.items() if k != "content"})
    content_store = gtest_state.setdefault("project_context_content", {})
    for desc in results:
        content_store[desc["filename"]] = desc.get("content", "")
    gtest_state["project_context_files"] = stored

    # Auto-extract + apply memory from all stored files
    extraction_result: dict[str, Any] = {
        "applied_count": 0, "duplicate_count": 0, "conflict_count": 0,
        "conflicts": [], "status": "no_files",
        "extraction_summary": {}, "memory_content": "",
    }
    all_descs = []
    for fd in stored:
        full_fd = dict(fd)
        full_fd["content"] = content_store.get(fd["filename"], "")
        all_descs.append(full_fd)

    if all_descs:
        proposed = build_memory_sections_from_files(all_descs)
        existing = load_memory_for_job(_job_output_dir(job_id))
        merge_result = merge_with_conflict_check(existing, proposed)
        merged_content = merge_result["merged"]

        # Save merged (non-conflicting) memory immediately
        save_memory_for_job(_job_output_dir(job_id), merged_content)
        gtest_state.setdefault("project_code_config_cache", {})["project_testcode_memory.md"] = merged_content

        extraction_result = {
            "applied_count": merge_result.get("conflict_count", 0) == 0
                and len([l for l in merged_content.splitlines() if l.strip().startswith("-")]) or 0,
            "duplicate_count": merge_result["duplicate_count"],
            "conflict_count": merge_result["conflict_count"],
            "conflicts": merge_result["conflicts"],
            "status": (
                "partial_applied_with_conflicts" if merge_result["conflict_count"] > 0
                else "applied"
            ),
            "extraction_summary": compute_extraction_summary(all_descs),
            "memory_content": merged_content,
        }

    _persist_job_gtest_state(job_id, gtest_state)
    return {
        "ok": True,
        "job_id": job_id,
        "uploaded": len(results),
        "skipped": skipped,
        "files": [{k: v for k, v in d.items() if k != "content"} for d in results],
        **extraction_result,
    }


@app.get("/api/review/project-context-files")
def api_get_project_context_files(job_id: str) -> dict[str, Any]:
    gtest_state = _load_job_gtest_state(job_id)
    files = gtest_state.get("project_context_files") or []
    return {"ok": True, "job_id": job_id, "files": files}


@app.post("/api/review/project-context-files/extract-memory")
def api_extract_memory_from_context_files(job_id: str) -> dict[str, Any]:
    """Manual extract-and-apply endpoint (kept for Advanced/Fallback use).

    Always returns HTTP 200. Conflicts are non-blocking — returns
    status: 'partial_applied_with_conflicts' with non-conflicting bullets applied.
    """
    from web.project_context_files import (
        build_memory_sections_from_files,
        compute_extraction_summary,
    )
    from web.project_testcode_memory import (
        load_memory_for_job,
        merge_with_conflict_check,
        save_memory_for_job,
    )

    gtest_state = _load_job_gtest_state(job_id)
    file_descs = gtest_state.get("project_context_files") or []
    content_store = gtest_state.get("project_context_content") or {}

    full_descs = []
    for fd in file_descs:
        full_fd = dict(fd)
        full_fd["content"] = content_store.get(fd["filename"], "")
        full_descs.append(full_fd)

    if not full_descs:
        return {"ok": False, "error": "No project context files loaded. Upload files first."}

    proposed = build_memory_sections_from_files(full_descs)
    existing = load_memory_for_job(_job_output_dir(job_id))
    result = merge_with_conflict_check(existing, proposed)
    merged_content = result["merged"]

    # Always save the merged (non-conflicting) result
    save_memory_for_job(_job_output_dir(job_id), merged_content)
    gtest_state.setdefault("project_code_config_cache", {})["project_testcode_memory.md"] = merged_content
    _persist_job_gtest_state(job_id, gtest_state)

    return {
        "ok": True,
        "job_id": job_id,
        "proposed": proposed,
        "merged": merged_content,
        "memory_content": merged_content,
        "conflicts": result["conflicts"],
        "conflict_count": result["conflict_count"],
        "duplicate_count": result["duplicate_count"],
        "status": "partial_applied_with_conflicts" if result["conflict_count"] > 0 else "applied",
        "extraction_summary": compute_extraction_summary(full_descs),
    }


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
            library_code_samples=_library_code_samples(_library_root()),
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"ok": True, "job_id": job_id, "context_pack": pack}


@app.get("/api/review/copilot/code/prompt")
def api_copilot_code_prompt(
    job_id: str,
    candidate_id: str,
    language: str = "EN",
    code_rule: str = "",
    existing_code: str = "",
    prompt_mode: str = "full",
    slim: bool = True,
) -> dict[str, Any]:
    from web.copilot_code_writer import (
        build_gtest_context_summary,
        build_gtest_copilot_prompt,
        build_gtest_copilot_prompt_followup,
    )

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    config = _sync_project_code_config_cache(job_id, gtest_state)
    files = config.get("files") or {}
    project_instruction = str((files.get("project_instruction.md") or {}).get("content") or "").strip()
    merged_code_rule = "\n\n".join(part for part in (project_instruction, str(code_rule or "").strip()) if part)
    merge_samples_from_bundle(bundle)
    try:
        pack = build_code_context_pack(
            bundle,
            gtest_state,
            candidate_id=candidate_id,
            library_root=_library_root(),
            language=language,
            cfg=_cfg(),
            library_code_samples=_library_code_samples(_library_root()),
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    samples = (pack.get("code_style_reference") or {}).get("samples") or []
    first_sample = samples[0] if samples else {}
    sample_label = str(first_sample.get("label") or first_sample.get("source_file") or "")
    mode = str(prompt_mode or "full").strip().lower()
    if mode == "followup":
        prompt = build_gtest_copilot_prompt_followup(pack, code_rule=merged_code_rule)
    else:
        prompt = build_gtest_copilot_prompt(
            pack,
            code_rule=merged_code_rule,
            existing_code=existing_code,
            slim=bool(slim),
        )
    summary = build_gtest_context_summary(pack, code_rule=merged_code_rule, sample_label=sample_label)
    return {
        "ok": True,
        "job_id": job_id,
        "candidate_id": candidate_id,
        "prompt": prompt,
        "prompt_mode": mode,
        "context_summary": summary,
    }


@app.post("/api/review/copilot/code/generate")
def api_copilot_code_generate(job_id: str, body: CopilotCodeGenerateRequest) -> dict[str, Any]:
    m365_st = _m365_copilot_gate()
    if not m365_st.get("api_ready"):
        return {"job_id": job_id, **classify_copilot_error(m365_ready=False)}
    if m365_st.get("copilot_chat_entitled") is False:
        return {"job_id": job_id, **classify_copilot_error(m365_ready=True, copilot_entitled=False)}
    bundle = _bundle_for_job(job_id)
    if not bundle.get("test_candidates"):
        return {"job_id": job_id, **classify_copilot_error(has_candidates=False)}
    gtest_state = _load_job_gtest_state(job_id)
    result = run_copilot_code_generate(
        bundle,
        gtest_state,
        candidate_id=body.candidate_id,
        cfg=_cfg(),
        library_root=_library_root(),
        engineer_note=body.engineer_note,
        copilot_prompt_override=body.copilot_prompt_override,
        use_baseline=body.use_baseline,
        language=body.language,
        reference_test_name=body.reference_test_name,
        library_code_samples=_library_code_samples(_library_root()),
        from_testcase_only=body.from_testcase_only,
        reuse_conversation=body.reuse_conversation,
    )
    if not result.get("ok"):
        result = enrich_error_response(
            result,
            m365_ready=True,
            copilot_entitled=True,
            has_bundle=True,
            has_candidates=True,
            raw_error=str(result.get("error") or ""),
        )
    return {"job_id": job_id, **result}


@app.post("/api/review/copilot/code/generate-batch")
def api_copilot_code_generate_batch(job_id: str, body: CopilotCodeBatchRequest) -> dict[str, Any]:
    cfg = _cfg()
    uid = _m365_effective_user_id(cfg)
    m365_st = m365_auth.m365_status(cfg, user_id=uid)
    if not m365_st.get("api_ready"):
        return {"job_id": job_id, **classify_copilot_error(m365_ready=False)}
    if m365_st.get("copilot_chat_entitled") is False:
        return {"job_id": job_id, **classify_copilot_error(m365_ready=True, copilot_entitled=False)}
    bundle = _bundle_for_job(job_id)
    if not bundle.get("test_candidates"):
        return {"job_id": job_id, **classify_copilot_error(has_candidates=False)}
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
        copilot_prompt_override=body.copilot_prompt_override,
        language=body.language,
        reference_test_name=body.reference_test_name,
        library_code_samples=_library_code_samples(_library_root()),
        persist_drafts=body.persist_drafts,
    )
    _persist_job_gtest_state(job_id, gtest_state)
    if not result.get("ok"):
        result = enrich_error_response(
            result,
            m365_ready=True,
            copilot_entitled=True,
            has_bundle=True,
            has_candidates=True,
            raw_error=str(result.get("error") or ""),
        )
    return {"job_id": job_id, **result}


@app.post("/api/review/gtest-text-replace")
def api_gtest_text_replace(job_id: str, body: GTestTextReplaceRequest) -> dict[str, Any]:
    from web.code_text_transform import (
        apply_replace_to_bundle,
        apply_replace_to_gtest_state,
        preview_replace,
    )

    src = body.from_text.strip()
    dst = body.to_text.strip()
    if not src or not dst:
        return {
            "job_id": job_id,
            "ok": False,
            "error": "from_text and to_text are required (explicit mechanical replace only).",
            "error_category": "not_simple_replace",
        }

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    candidate_ids = [c for c in (body.candidate_ids or []) if c]
    if not candidate_ids and body.candidate_id:
        candidate_ids = [body.candidate_id]

    if body.preview:
        return {
            "job_id": job_id,
            **preview_replace(
                bundle,
                gtest_state,
                src=src,
                dst=dst,
                candidate_ids=candidate_ids or None,
                current_snippet=body.current_snippet,
                current_candidate_id=body.candidate_id,
            ),
        }

    io_result = apply_replace_to_bundle(
        bundle,
        src=src,
        dst=dst,
        candidate_ids=candidate_ids or None,
    )
    result = apply_replace_to_gtest_state(
        gtest_state,
        src=src,
        dst=dst,
        candidate_ids=candidate_ids or None,
        current_snippet=body.current_snippet,
        current_candidate_id=body.candidate_id,
    )
    result["io_touched"] = io_result.get("touched", 0)
    result["io_replacements"] = io_result.get("total_replacements", 0)
    if body.persist:
        _save_bundle_to_job(job_id, bundle)
        _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.get("/api/review/gtest-sync-status")
def api_gtest_sync_status(job_id: str, language: str = "EN") -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    result = classify_sync_status(bundle, gtest_state, language=language or "EN")
    return {"job_id": job_id, **result}


@app.post("/api/review/gtest-bulk")
def api_gtest_bulk(job_id: str, body: GTestBulkRequest) -> dict[str, Any]:
    from web.code_text_transform import apply_replace_to_bundle, apply_replace_to_gtest_state, merge_drafts_to_monolith

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    lang = body.language or "EN"
    action = str(body.action or "").strip().lower()
    cids = [c for c in (body.candidate_ids or []) if c]

    if action == "delete_code":
        if not cids:
            sync = classify_sync_status(bundle, gtest_state, language=lang)
            cids = [r["candidate_id"] for r in sync.get("rows") or [] if r.get("status") == "orphan_code"]
        result = bulk_delete_code(gtest_state, cids)
    elif action == "regen_comment":
        result = bulk_regen_comments(bundle, gtest_state, cids, language=lang, stale_only=False)
    elif action == "regen_comment_stale":
        result = bulk_regen_comments(bundle, gtest_state, cids, language=lang, stale_only=True)
    elif action == "replace":
        src = body.from_text.strip()
        dst = body.to_text.strip()
        if not src or not dst:
            return {"job_id": job_id, "ok": False, "error": "from_text and to_text required"}
        apply_replace_to_bundle(bundle, src=src, dst=dst, candidate_ids=cids or None)
        result = apply_replace_to_gtest_state(
            gtest_state, src=src, dst=dst, candidate_ids=cids or None
        )
    elif action == "merge_export":
        content = merge_drafts_to_monolith(gtest_state, bundle, candidate_ids=cids or None, language=lang)
        return {"job_id": job_id, "ok": True, "content": content, "action": action}
    else:
        return {"job_id": job_id, "ok": False, "error": f"Unknown action: {action}"}

    if body.persist:
        _save_bundle_to_job(job_id, bundle)
        _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, "action": action, **result}


@app.post("/api/review/gtest-monolith-import")
async def api_gtest_monolith_import(job_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    from web.code_text_transform import import_monolith_to_drafts

    raw = await file.read()
    text = raw.decode("utf-8", errors="replace")
    gtest_state = _load_job_gtest_state(job_id)
    result = import_monolith_to_drafts(gtest_state, text)
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.get("/api/export/gtest-cpp-marked")
def api_export_gtest_cpp_marked(job_id: str, language: str = "EN") -> Response:
    from web.code_text_transform import merge_drafts_to_monolith

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    content = merge_drafts_to_monolith(gtest_state, bundle, language=language or "EN")
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="alex_marked_tests.cc"'},
    )


@app.post("/api/review/copilot/code/refine")
def api_copilot_code_refine(job_id: str, body: CopilotCodeRefineRequest) -> dict[str, Any]:
    from web.copilot_code_writer import run_code_refine

    m365_st = _m365_copilot_gate()
    if not m365_st.get("api_ready"):
        return {"job_id": job_id, **classify_copilot_error(m365_ready=False)}
    if m365_st.get("copilot_chat_entitled") is False:
        return {"job_id": job_id, **classify_copilot_error(m365_ready=True, copilot_entitled=False)}

    code = str(body.existing_code or "").strip()
    instruction = str(body.instruction or "").strip()
    if not code or not instruction:
        return {"job_id": job_id, "ok": False, "error": "existing_code and instruction are required."}

    result = run_code_refine(
        code,
        instruction,
        _cfg(),
        test_name=body.candidate_id,
        reuse_conversation=body.reuse_conversation,
    )
    if not result.get("ok"):
        result = enrich_error_response(
            result,
            m365_ready=True,
            copilot_entitled=True,
            raw_error=str(result.get("error") or ""),
        )
        return {"job_id": job_id, **result}
    return {
        "job_id": job_id,
        "ok": True,
        "copilot_draft": result.get("draft") or {},
        "validation": result.get("validation") or {},
        "provider": result.get("provider"),
        "raw_preview": result.get("raw_preview"),
    }


def _start_m365_copilot_task(job_id: str, body: M365CopilotTaskRequest) -> dict[str, Any]:
    from web.m365_copilot_task_runners import run_task_kind
    from web.m365_copilot_tasks import start_task

    m365_st = _m365_copilot_gate()
    if not m365_st.get("api_ready"):
        return {"job_id": job_id, **classify_copilot_error(m365_ready=False)}
    if m365_st.get("copilot_chat_entitled") is False:
        return {"job_id": job_id, **classify_copilot_error(m365_ready=True, copilot_entitled=False)}

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    # Ensure project code config cache (incl. test code memory) is populated before
    # the runner executes. Without this, raw_memory is empty and no relevant rules are
    # injected into the prompt, causing Copilot to return MISSING_CONTEXT.
    _sync_project_code_config_cache(job_id, gtest_state)
    cfg = _cfg()
    out_dir = _job_output_dir(job_id)
    bundle_version = _get_bundle_version(job_id)
    payload = dict(body.payload or {})
    payload.setdefault("bundle_version", bundle_version)
    payload.setdefault("m365_user_id", _m365_effective_user_id(cfg))

    def save_bundle(updated: dict[str, Any]) -> None:
        _save_bundle_to_job(job_id, updated)

    def persist_gtest(state: dict[str, Any]) -> None:
        _persist_job_gtest_state(job_id, state)

    def runner(task: dict[str, Any], progress: Any) -> dict[str, Any]:
        return run_task_kind(
            body.kind,
            job_id=job_id,
            payload=payload,
            task=task,
            progress=progress,
            bundle=bundle,
            gtest_state=gtest_state,
            cfg=cfg,
            library_root=_library_root(),
            library_code_samples=_library_code_samples(_library_root()),
            save_bundle=save_bundle,
            persist_gtest=persist_gtest,
            job_output=out_dir,
        )

    try:
        task = start_task(
            job_id,
            out_dir,
            kind=body.kind,
            payload=payload,
            label=body.label or body.kind,
            logic_id=body.logic_id,
            candidate_id=body.candidate_id,
            target_page=body.target_page,
            runner=runner,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    # For batch generation: create a persistent generation run record so the UI
    # can reattach after browser reload or server restart.
    if body.kind == "code_copilot_batch":
        from web.generation_runs import create_run as _create_gen_run
        gen_run = _create_gen_run(
            job_id, out_dir,
            candidate_ids=[c for c in (payload.get("candidate_ids") or []) if c],
            task_id=task["task_id"],
            language=str(payload.get("language") or "EN"),
            engineer_note=str(payload.get("engineer_note") or ""),
            batch_size=int(payload.get("batch_size") or 10),
            scope=str(payload.get("scope") or "filter"),
            group_key=str(payload.get("group_key") or ""),
            group_field=str(payload.get("group_field") or "test_group"),
        )
        return {"job_id": job_id, "ok": True, **task, "generation_run_id": gen_run["run_id"]}

    return {"job_id": job_id, "ok": True, **task}


@app.post("/api/review/copilot/m365-tasks", status_code=202)
def api_m365_copilot_task_start(job_id: str, body: M365CopilotTaskRequest) -> dict[str, Any]:
    return _start_m365_copilot_task(job_id, body)


@app.get("/api/review/copilot/m365-tasks/{task_id}")
def api_m365_copilot_task_status(job_id: str, task_id: str) -> dict[str, Any]:
    from web.m365_copilot_tasks import get_task_status, list_tasks

    out_dir = _job_output_dir(job_id)
    task = get_task_status(job_id, task_id, out_dir)
    if not task:
        known = list_tasks(job_id, out_dir)
        return {
            "ok": False,
            "status": "MISSING",
            "error_category": "task_not_found",
            "task_id": task_id,
            "job_id": job_id,
            "message": "Task not found or expired.",
            "known_task_count": len(known),
            "reason": "expired_or_restarted",
        }
    return {"job_id": job_id, "ok": True, **task}


@app.get("/api/review/copilot/m365-tasks")
def api_m365_copilot_task_list(job_id: str) -> dict[str, Any]:
    from web.m365_copilot_tasks import list_tasks

    out_dir = _job_output_dir(job_id)
    return {"job_id": job_id, "ok": True, "tasks": list_tasks(job_id, out_dir)}


@app.delete("/api/review/copilot/m365-tasks/{task_id}")
def api_m365_copilot_task_cancel(job_id: str, task_id: str) -> dict[str, Any]:
    from web.m365_copilot_tasks import cancel_task

    out_dir = _job_output_dir(job_id)
    task = cancel_task(job_id, task_id, out_dir)
    if not task:
        raise HTTPException(404, f"Task not found: {task_id}")
    return {"job_id": job_id, "ok": True, **task}


# ---------------------------------------------------------------------------
# Generation run endpoints — resilient batch generation tracking
# ---------------------------------------------------------------------------

@app.get("/api/review/generation-run")
def api_generation_run_status(job_id: str) -> dict[str, Any]:
    """Return the active generation run for this job with live diagnostics.

    Returns 200 with active_run=null when no run exists.
    Resolves stale RUNNING runs (server restarted) as PAUSED automatically.
    """
    from web.generation_runs import compute_run_diagnostics, get_active_run
    from web.m365_copilot_tasks import list_tasks

    out_dir = _job_output_dir(job_id)
    tasks = list_tasks(job_id, out_dir)
    task_status_by_id = {str(t.get("task_id") or ""): str(t.get("status") or "") for t in tasks}
    run = get_active_run(out_dir, task_status_by_id=task_status_by_id)
    if not run:
        return {"job_id": job_id, "ok": True, "active_run": None, "has_active_run": False}
    gtest_state = _load_job_gtest_state(job_id)
    task_status = task_status_by_id.get(str(run.get("task_id") or ""), "")
    diag = compute_run_diagnostics(run, gtest_state, task_status=task_status)
    return {"job_id": job_id, "ok": True, "active_run": run, "has_active_run": True, **diag}


@app.post("/api/review/generation-run/resume")
def api_generation_run_resume(job_id: str) -> dict[str, Any]:
    """Resume a PAUSED generation run, skipping already confirmed/saved testcases."""
    from web.generation_runs import create_run as _create_gen_run
    from web.generation_runs import get_active_run
    from web.m365_copilot_task_runners import run_task_kind
    from web.m365_copilot_tasks import list_tasks, start_task

    out_dir = _job_output_dir(job_id)
    tasks = list_tasks(job_id, out_dir)
    task_status_by_id = {str(t.get("task_id") or ""): str(t.get("status") or "") for t in tasks}
    run = get_active_run(out_dir, task_status_by_id=task_status_by_id)
    if not run:
        raise HTTPException(404, "No active generation run for this job")
    if run["status"] not in ("PAUSED", "FAILED"):
        return {"job_id": job_id, "ok": False, "error": "run_not_paused",
                "status": run["status"], "run_id": run.get("run_id")}

    m365_st = _m365_copilot_gate()
    if not m365_st.get("api_ready"):
        return {"job_id": job_id, **classify_copilot_error(m365_ready=False)}

    # Collect candidate IDs that still need generation
    gtest_state = _load_job_gtest_state(job_id)
    drafts = gtest_state.get("drafts") or {}
    remaining_ids: list[str] = []
    for cid in run.get("candidate_ids") or []:
        d = drafts.get(cid) or {}
        cs = str(d.get("code_status") or "").upper()
        is_done = (
            bool(d.get("exportable"))
            or str(d.get("approval_status") or "").upper() in ("CONFIRMED", "APPROVED")
            or cs == "SAVED"
        )
        if not is_done:
            remaining_ids.append(cid)

    if not remaining_ids:
        return {"job_id": job_id, "ok": True, "resumed": False,
                "message": "all_completed", "remaining_count": 0}

    _sync_project_code_config_cache(job_id, gtest_state)
    cfg = _cfg()
    bundle = _bundle_for_job(job_id)
    payload: dict[str, Any] = {
        "candidate_ids": remaining_ids,
        "language": str(run.get("language") or "EN"),
        "engineer_note": str(run.get("engineer_note") or ""),
        "batch_size": int(run.get("batch_size") or 10),
        "scope": "selected",
        "group_key": str(run.get("group_key") or ""),
        "group_field": str(run.get("group_field") or "test_group"),
        "skip_saved": True,
        "allow_missing_sample": True,
        "slim_prompt": True,
        "m365_user_id": _m365_effective_user_id(cfg),
    }

    def _save_bundle(b: dict[str, Any]) -> None:
        _save_bundle_to_job(job_id, b)

    def _persist(s: dict[str, Any]) -> None:
        _persist_job_gtest_state(job_id, s)

    def runner(task: dict[str, Any], progress: Any) -> dict[str, Any]:
        return run_task_kind(
            "code_copilot_batch",
            job_id=job_id, payload=payload, task=task, progress=progress,
            bundle=bundle, gtest_state=gtest_state, cfg=cfg,
            library_root=_library_root(), library_code_samples=_library_code_samples(_library_root()),
            save_bundle=_save_bundle, persist_gtest=_persist,
            job_output=out_dir,
        )

    task = start_task(job_id, out_dir, kind="code_copilot_batch", payload=payload,
                      label=f"Resume ({len(remaining_ids)} remaining)", runner=runner)
    new_run = _create_gen_run(
        job_id, out_dir,
        candidate_ids=remaining_ids, task_id=task["task_id"],
        language=payload["language"], engineer_note=payload["engineer_note"],
        batch_size=int(payload["batch_size"]), scope="selected",
    )
    return {
        "job_id": job_id, "ok": True, "resumed": True,
        "generation_run_id": new_run["run_id"],
        "task_id": task["task_id"],
        "remaining_count": len(remaining_ids),
        **task,
    }


@app.post("/api/review/generation-run/cancel")
def api_generation_run_cancel(job_id: str) -> dict[str, Any]:
    """Cancel the active generation run. Completed drafts are preserved."""
    from web.generation_runs import get_active_run, update_run
    from web.m365_copilot_tasks import cancel_task, list_tasks

    out_dir = _job_output_dir(job_id)
    tasks = list_tasks(job_id, out_dir)
    task_status_by_id = {str(t.get("task_id") or ""): str(t.get("status") or "") for t in tasks}
    run = get_active_run(out_dir, task_status_by_id=task_status_by_id)
    if not run:
        return {"job_id": job_id, "ok": False, "error": "no_active_run"}
    task_id = str(run.get("task_id") or "")
    if task_id:
        cancel_task(job_id, task_id, out_dir)
    update_run(out_dir, run["run_id"], status="CANCELLED")
    return {"job_id": job_id, "ok": True, "cancelled_run_id": run["run_id"], "task_id": task_id}


@app.get("/api/review/generation-runs")
def api_generation_run_list(job_id: str) -> dict[str, Any]:
    from web.generation_runs import list_runs
    return {"job_id": job_id, "ok": True, "runs": list_runs(_job_output_dir(job_id))}


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
    if not gtest_state.get("project_code_config_cache"):
        _sync_project_code_config_cache(job_id, gtest_state)
        _persist_job_gtest_state(job_id, gtest_state)
    payload = build_workspace_payload(
        bundle,
        gtest_state,
        language=language,
        job_id=job_id,
        bundle_version=bundle_version,
        job_output_dir=_job_output_dir(job_id),
    )
    if payload.get("group_mapping"):
        try:
            from web.testcase_group_mapping import save_group_mapping
            save_group_mapping(_job_output_dir(job_id), payload["group_mapping"])
        except Exception:
            pass
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
    from datetime import datetime, timezone

    from src.importers.customer_testspec_importer import compute_body_hash, compute_spec_hash
    from web.code_quality_gate import quality_to_code_status, run_quality_gate
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    structured = _structured_io_for_candidate(bundle, body.draft_key, language="EN")
    spec_hash = compute_spec_hash(structured)
    body_hash = compute_body_hash(structured)
    code_status = str(body.code_status or "SAVED").strip().upper() or "SAVED"
    generation_source = str(body.generation_source or "MANUAL").strip().upper() or "MANUAL"
    last_saved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if code_status == "SAVED" else None
    quality_results = body.quality_results
    quality_summary = body.quality_summary
    review_reason = body.review_reason
    if code_status == "SAVED" and body.full_snippet:
        try:
            from web.gtest_workspace import _workbench_row_for_candidate
            cfg_cache = gtest_state.get("project_code_config_cache") or {}
            wb = _workbench_row_for_candidate(bundle, body.draft_key, language="EN") or {}
            samples = load_code_style_samples(bundle)
            sample_snippet = str((samples[0] or {}).get("snippet") or "") if samples else ""
            qg = run_quality_gate(
                body.full_snippet,
                candidate_id=body.draft_key,
                structured_io=structured,
                code_rules_md=str(cfg_cache.get("code_rules.md") or ""),
                api_catalog_yaml=str(cfg_cache.get("api_catalog.yaml") or ""),
                sample_snippet=sample_snippet,
                expected_input=str(wb.get("expected_input") or ""),
                expected_output=str(wb.get("expected_output") or ""),
            )
            quality_results = qg.get("checks") or []
            quality_summary = qg.get("summary")
            gate_status = quality_to_code_status(quality_summary or "FAIL")
            if gate_status != "SAVED":
                code_status = gate_status
                last_saved_at = None
                review_reason = "; ".join(
                    c["message"] for c in quality_results if c.get("severity") in ("WARNING", "FAIL")
                )[:500]
        except Exception as _qg_exc:
            return {
                "ok": False,
                "error": f"quality gate error: {_qg_exc}",
                "draft_key": body.draft_key,
                "code_status": "NEEDS_REVIEW",
            }
    draft_payload: dict[str, Any] = {
        "source_kind": body.source_kind,
        "test_name": body.test_name,
        "spec_comment_block": body.spec_comment_block,
        "code_body": body.code_body,
        "full_snippet": body.full_snippet,
        "spec_hash": spec_hash,
        "body_hash": body_hash,
        "code_status": code_status,
        "generation_source": generation_source,
        "last_saved_at": last_saved_at,
    }
    if quality_results is not None:
        draft_payload["quality_results"] = quality_results
    if quality_summary:
        draft_payload["quality_summary"] = quality_summary
    if review_reason:
        draft_payload["review_reason"] = review_reason
    gtest_state = save_draft(
        gtest_state,
        draft_key=body.draft_key,
        draft=draft_payload,
        engineer_edited=body.engineer_edited,
    )
    _force_merge_used = False
    if body.force_merge:
        # Explicit Confirm action after a 409: reload the freshest bundle (picks up any
        # concurrent saves on other TCs), merge only this draft, and bypass the If-Match
        # version check so a stale bundleVersion on the client never blocks the user.
        _fresh_bundle = _bundle_for_job(job_id)
        sync_gtest_to_bundle(_fresh_bundle, gtest_state)
        save_gtest_state(_job_output_dir(job_id), gtest_state)
        _save_bundle_to_job(job_id, _fresh_bundle, force=True)
        _force_merge_used = True
    else:
        _persist_job_gtest_state(job_id, gtest_state)
    saved = (gtest_state.get("drafts") or {}).get(body.draft_key) or {}
    return {
        "ok": True,
        "job_id": job_id,
        "draft_key": body.draft_key,
        "spec_hash": spec_hash,
        "code_status": saved.get("code_status") or code_status,
        "generation_source": saved.get("generation_source") or generation_source,
        "last_saved_at": saved.get("last_saved_at") or last_saved_at,
        "quality_summary": saved.get("quality_summary") or quality_summary,
        "review_reason": saved.get("review_reason") or review_reason,
        "quality_results": saved.get("quality_results") or quality_results,
        "bundle_version": _get_bundle_version(job_id),
        "force_merge_used": _force_merge_used,
        "conflict_retry_used": body.force_merge,
        "same_testcase_changed": False,
        "save_success": True,
    }


def _sync_project_code_config_cache(job_id: str, gtest_state: dict[str, Any]) -> dict[str, Any]:
    from datetime import datetime, timezone

    from web.project_code_config import effective_instruction_for_job, load_project_code_config
    from web.project_testcode_memory import copy_global_to_job, load_memory_for_job, _job_memory_path

    config = load_project_code_config(_job_output_dir(job_id))
    cache = {name: str((meta or {}).get("content") or "") for name, meta in (config.get("files") or {}).items()}

    # Auto-load testcode memory: copy global → job if no local copy
    mem_content = copy_global_to_job(_job_output_dir(job_id))
    cache["project_testcode_memory.md"] = mem_content

    # Determine source labels for UI
    mem_source = "job_override" if _job_memory_path(_job_output_dir(job_id)).exists() else "global"
    _, instr_source = effective_instruction_for_job(_job_output_dir(job_id))

    gtest_state["project_code_config_cache"] = cache
    gtest_state["project_code_config_meta"] = {
        "loaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": list(cache.keys()),
        "current_version_id": config.get("current_version_id"),
        "current_version": config.get("current_version"),
        "layers": config.get("layers"),
        "pending_proposal": config.get("pending_proposal"),
        "memory_source": mem_source,
        "instruction_source": instr_source,
    }
    return config


@app.get("/api/review/project-code-config")
def api_get_project_code_config(job_id: str) -> dict[str, Any]:
    gtest_state = _load_job_gtest_state(job_id)
    config = _sync_project_code_config_cache(job_id, gtest_state)
    _persist_job_gtest_state(job_id, gtest_state)
    meta = gtest_state.get("project_code_config_meta") or {}
    return {
        "job_id": job_id,
        **config,
        "memory_source": meta.get("memory_source", "global"),
        "instruction_source": meta.get("instruction_source", "builtin_default"),
    }


@app.get("/api/review/project-code-config/diagnostics")
def api_project_code_config_diagnostics(job_id: str) -> dict[str, Any]:
    from web.project_code_config import diagnose_project_code_config_files, load_project_code_config

    config = load_project_code_config(_job_output_dir(job_id))
    files = config.get("files") or {}
    sm = str((files.get("signal_mapping.yaml") or {}).get("content") or "")
    api = str((files.get("api_catalog.yaml") or {}).get("content") or "")
    diag = diagnose_project_code_config_files(sm, api)
    return {"job_id": job_id, **diag}


@app.put("/api/review/project-code-config")
def api_put_project_code_config(job_id: str, body: ProjectCodeConfigSaveRequest) -> dict[str, Any]:
    from web.project_code_config import save_project_code_config_file

    result = save_project_code_config_file(_job_output_dir(job_id), body.filename, body.content)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "save failed")
    # Use save_gtest_state (not _persist_job_gtest_state) to avoid the bundle version check.
    # The frontend api() helper always sends If-Match:<version>, which _save_bundle_to_job
    # would reject with 409 whenever the version is stale — config saves must never be blocked.
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    save_gtest_state(_job_output_dir(job_id), gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/project-code-config/save-as-global")
def api_save_project_instruction_as_global(job_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Save current project_instruction.md to global library (web_data/.alex/project_instruction.md)."""
    from web.project_code_config import effective_instruction_for_job, save_global_instruction

    content = str((body or {}).get("content") or "").strip()
    if not content:
        # Load current effective instruction
        content, _ = effective_instruction_for_job(_job_output_dir(job_id))
    if not content:
        return {"job_id": job_id, "ok": False, "error": "No instruction content to save globally."}
    path = save_global_instruction(content)
    # Sync cache without bundle version bump — same reason as api_put_project_code_config.
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    save_gtest_state(_job_output_dir(job_id), gtest_state)
    return {"job_id": job_id, "ok": True, "path": str(path), "instruction_source": "global"}


@app.get("/api/review/project-code-config/global-instruction")
def api_get_global_instruction() -> dict[str, Any]:
    from web.project_code_config import load_global_instruction
    content = load_global_instruction()
    return {"ok": True, "exists": content is not None, "content": content or ""}


@app.post("/api/review/project-code-config/reload-global-instruction")
def api_reload_global_instruction(job_id: str) -> dict[str, Any]:
    """Replace job instruction with global instruction (if global exists)."""
    from web.project_code_config import (
        load_global_instruction,
        save_project_code_config_file,
        effective_instruction_for_job,
    )
    global_content = load_global_instruction()
    if not global_content:
        return {"job_id": job_id, "ok": False, "error": "No global instruction saved yet. Save as Global first."}
    result = save_project_code_config_file(_job_output_dir(job_id), "project_instruction.md", global_content)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "save failed")
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    save_gtest_state(_job_output_dir(job_id), gtest_state)
    _, source = effective_instruction_for_job(_job_output_dir(job_id))
    return {"job_id": job_id, "ok": True, "content": global_content, "instruction_source": source}


@app.post("/api/review/testcode-api-debug")
def api_testcode_api_debug(job_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Debug single-TC API generation end-to-end with full trace.

    Sends the smallest possible prompt for one testcase and returns:
    - auth/health status
    - prompt text (full)
    - request timing
    - raw response summary
    - parse result
    - final code_status
    """
    import time
    from web.m365_copilot import _chat_timeout, probe_copilot_api, run_copilot_chat_result
    from web.copilot_batch_codegen import (
        _extract_generation_critical_map,
        build_style_example_block,
        pick_representative_style_example,
        _style_example_score,
        collect_copilot_project_context,
        parse_copilot_batch_response,
        _clip,
    )
    from web.gtest_workspace import _workbench_row_for_candidate

    cfg = _cfg()
    uid = _m365_effective_user_id(cfg)

    # --- Auth health check ---
    m365_st = m365_auth.m365_status(cfg, user_id=uid)
    if not m365_st.get("api_ready"):
        return {
            "ok": False,
            "root_cause": "API_AUTH_PROBLEM",
            "auth_status": m365_st,
            "detail": "M365 API not ready. Sign in and authorize Copilot API first.",
        }
    if m365_st.get("copilot_chat_entitled") is False:
        return {
            "ok": False,
            "root_cause": "API_AUTH_PROBLEM",
            "auth_status": m365_st,
            "detail": "M365 Copilot not entitled for this account.",
        }

    candidate_id = str((body or {}).get("candidate_id") or "")
    language = str((body or {}).get("language") or "EN")

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)

    # Pick first NEEDS_REVIEW or first TC if no explicit candidate_id
    if not candidate_id:
        drafts = gtest_state.get("drafts") or {}
        for cid, d in drafts.items():
            if str((d or {}).get("code_status") or "").upper() in {"NEEDS_REVIEW", "ERROR", ""}:
                candidate_id = cid
                break
    if not candidate_id:
        rows = list((bundle.get("test_candidates") or [])[:1])
        if rows:
            candidate_id = str(rows[0].get("id") or rows[0].get("candidate_id") or "")
    if not candidate_id:
        return {"ok": False, "root_cause": "NO_TESTCASE", "detail": "No testcase found in job."}

    row = _workbench_row_for_candidate(bundle, candidate_id, language=language) or {"candidate_id": candidate_id}
    expected_input = str(row.get("expected_input") or "")
    expected_output = str(row.get("expected_output") or "")

    # --- Build minimal debug prompt ---
    ctx = collect_copilot_project_context(bundle, gtest_state, language=language, slim_prompt=True)
    cache = gtest_state.get("project_code_config_cache") or {}
    memory_content = str(cache.get("project_testcode_memory.md") or "")
    critical_map = _extract_generation_critical_map(memory_content, char_limit=600)

    style_snippet = str(ctx.get("style_example_snippet") or "").strip()
    style_label = str(ctx.get("style_example_label") or "")
    style_score = _style_example_score(style_snippet) if style_snippet else 0
    style_block = build_style_example_block(_clip(style_snippet, 600), label=style_label) if style_score > 1 else ""

    prompt = (
        f"TASK:\nGenerate one Google Test C++ TEST_F for testcase_id {candidate_id}.\n\n"
        + (f"STYLE:\n{style_block}\n" if style_block else "")
        + (f"MEMORY (fixture/API/assertion map):\n{critical_map}\n\n" if critical_map else "")
        + f"TESTCASE:\ntestcase_id: {candidate_id}\n"
        + f"Given/When (expected_input):\n{_clip(expected_input, 600)}\n"
        + f"Then (expected_output):\n{_clip(expected_output, 600)}\n\n"
        + "OUTPUT:\nReturn only:\n"
        "[TESTCASE_CODE]\n"
        f"testcase_id: {candidate_id}\n"
        "```cpp\n<full TEST_F code>\n```\n\n"
        "[MISSING_CONTEXT]\n"
        f"testcase_id: {candidate_id}\n"
        "missing_type: INPUT_API|OUTPUT_ASSERTION|FIXTURE|TIMING\n"
        "signal_or_item: <name>\nreason: <brief>\n"
        "(use MISSING_CONTEXT when required API/mapping is not available — do NOT invent)\n"
    )

    prompt_len = len(prompt)
    timeout_s = _chat_timeout(cfg)

    # --- Fire API ---
    t0 = time.perf_counter()
    result = run_copilot_chat_result(
        cfg,
        prompt,
        user_id=uid,
        reuse_session_conversation=False,
        persist_conversation=False,
    )
    elapsed_s = round(time.perf_counter() - t0, 1)

    ok = result.get("ok", False)
    reply = str(result.get("reply") or result.get("content") or "")
    error_cat = str(result.get("error_category") or "")
    error_msg = str(result.get("error") or "")

    # Classify root cause
    if not ok:
        if error_cat == "m365_graph_timeout":
            root_cause = "API_TIMEOUT_PROBLEM"
        elif error_cat in ("m365_not_ready", "m365_auth"):
            root_cause = "API_AUTH_PROBLEM"
        elif "429" in error_msg or "rate" in error_msg.lower():
            root_cause = "API_RATE_LIMIT_429"
        elif "payload" in error_msg.lower() or "too large" in error_msg.lower():
            root_cause = "API_PAYLOAD_TOO_LARGE"
        else:
            root_cause = "API_UNKNOWN_FAILURE"
    else:
        if not reply.strip():
            root_cause = "API_EMPTY_RESPONSE"
        else:
            root_cause = None  # may be SUCCESS or PARSE_PROBLEM

    # Parse response
    parse_result: dict[str, Any] = {}
    code_status = "ERROR"
    if reply:
        parsed = parse_copilot_batch_response(reply)
        parse_result = {
            "parsed_count": parsed.get("parsed_count", 0),
            "unresolved_count": len(parsed.get("unresolved_by_id") or {}),
            "missing_context_count": len(parsed.get("missing_context_by_id") or {}),
            "has_code_block": bool(parsed.get("items")),
        }
        if parsed.get("items"):
            code_status = "NEEDS_REVIEW_OR_SAVED"
            root_cause = root_cause or "SUCCESS"
        elif parsed.get("missing_context_by_id"):
            code_status = "MISSING_CONTEXT"
            root_cause = root_cause or "PROMPT_REFUSAL_OR_MISSING_CONTEXT"
        elif parsed.get("unresolved_by_id"):
            code_status = "UNRESOLVED"
            root_cause = root_cause or "PROMPT_REFUSAL_OR_MISSING_CONTEXT"
        else:
            root_cause = root_cause or "API_RESPONSE_PARSE_PROBLEM"

    return {
        "ok": ok,
        "root_cause": root_cause or ("SUCCESS" if ok and code_status == "NEEDS_REVIEW_OR_SAVED" else "UNKNOWN"),
        "candidate_id": candidate_id,
        "prompt_length": prompt_len,
        "prompt_preview_head": prompt[:800],
        "prompt_preview_tail": prompt[-400:],
        "timeout_s": timeout_s,
        "elapsed_s": elapsed_s,
        "api_ok": ok,
        "error_category": error_cat,
        "error_message": error_msg[:300],
        "response_length": len(reply),
        "response_preview": reply[:600],
        "parse_result": parse_result,
        "code_status": code_status,
        "auth_status": {
            "api_ready": m365_st.get("api_ready"),
            "copilot_entitled": m365_st.get("copilot_chat_entitled"),
        },
    }


@app.get("/api/review/global-config-diagnostics")
def api_global_config_diagnostics(job_id: str | None = None) -> dict[str, Any]:
    """Return global and job config file status for diagnostics panel."""
    from web.alex_storage import global_instruction_path, testcode_memory_path, code_style_samples_path
    from web.project_testcode_memory import _job_memory_path, load_memory_for_job

    gm_path = testcode_memory_path()
    gi_path = global_instruction_path()
    gs_path = code_style_samples_path()

    diag: dict[str, Any] = {
        "global_memory_exists": gm_path.exists(),
        "global_memory_path": str(gm_path),
        "global_instruction_exists": gi_path.exists(),
        "global_instruction_path": str(gi_path),
        "global_style_samples_count": 0,
    }

    # Style samples count
    try:
        import yaml
        if gs_path.exists():
            data = yaml.safe_load(gs_path.read_text(encoding="utf-8")) or {}
            diag["global_style_samples_count"] = len(data.get("samples") or [])
    except Exception:
        pass

    # Job-specific info
    if job_id:
        job_out = _job_output_dir(job_id)
        job_mem = _job_memory_path(job_out)
        diag["job_memory_exists"] = job_mem.exists()
        diag["job_memory_path"] = str(job_mem)
        gtest_state = _load_job_gtest_state(job_id)
        meta = gtest_state.get("project_code_config_meta") or {}
        diag["memory_source"] = meta.get("memory_source", "unknown")
        diag["instruction_source"] = meta.get("instruction_source", "unknown")
        diag["last_synced"] = meta.get("loaded_at", "")

        from web.project_code_config import effective_instruction_for_job
        from web.config_bundle_layers import _overrides_dir
        override_path = _overrides_dir(job_out) / "project_instruction.md"
        diag["job_instruction_override_exists"] = override_path.exists()

    return {"ok": True, **diag}


@app.get("/api/review/testcode-memory")
def api_get_testcode_memory(job_id: str) -> dict[str, Any]:
    from web.project_testcode_memory import load_memory_for_job, _job_memory_path

    content = load_memory_for_job(_job_output_dir(job_id))
    source = "job_override" if _job_memory_path(_job_output_dir(job_id)).exists() else "global"
    return {"job_id": job_id, "content": content, "source": source}


@app.put("/api/review/testcode-memory")
def api_put_testcode_memory(job_id: str, body: dict[str, Any]) -> dict[str, Any]:
    from web.project_testcode_memory import save_memory_for_job

    content = str(body.get("content") or "")
    save_memory_for_job(_job_output_dir(job_id), content)
    gtest_state = _load_job_gtest_state(job_id)
    gtest_state.setdefault("project_code_config_cache", {})["project_testcode_memory.md"] = content
    save_gtest_state(_job_output_dir(job_id), gtest_state)
    return {"job_id": job_id, "ok": True}


@app.get("/api/review/testcode-memory/global")
def api_get_testcode_memory_global() -> dict[str, Any]:
    from web.project_testcode_memory import load_global_memory

    return {"content": load_global_memory()}


@app.put("/api/review/testcode-memory/global")
def api_put_testcode_memory_global(body: dict[str, Any]) -> dict[str, Any]:
    from web.project_testcode_memory import save_global_memory

    content = str(body.get("content") or "")
    path = save_global_memory(content)
    return {"ok": True, "path": str(path)}


@app.post("/api/review/testcode-memory/save-as-global")
def api_save_testcode_memory_as_global(job_id: str) -> dict[str, Any]:
    from web.project_testcode_memory import load_memory_for_job, save_global_memory

    content = load_memory_for_job(_job_output_dir(job_id))
    path = save_global_memory(content)
    return {"job_id": job_id, "ok": True, "path": str(path)}


@app.post("/api/review/testcode-memory/extract")
def api_extract_testcode_memory(job_id: str, body: dict[str, Any]) -> dict[str, Any]:
    from web.project_testcode_memory import (
        build_proposed_memory,
        extract_patterns_from_sample,
        load_memory_for_job,
        merge_proposed_into_memory,
    )

    code = str(body.get("code") or body.get("content") or "")
    source_file = str(body.get("source_file") or body.get("filename") or "sample.cc")
    extraction = extract_patterns_from_sample(code)
    proposed = build_proposed_memory(extraction, source_file=source_file)
    existing = load_memory_for_job(_job_output_dir(job_id))
    merged = merge_proposed_into_memory(existing, proposed)
    return {
        "job_id": job_id,
        "extraction": extraction,
        "proposed": proposed,
        "merged": merged,
    }


@app.post("/api/review/testcode-memory/append")
def api_append_testcode_memory(job_id: str, body: dict[str, Any]) -> dict[str, Any]:
    from web.project_testcode_memory import (
        append_to_section,
        check_before_append,
        load_memory_for_job,
        save_memory_for_job,
    )

    section = str(body.get("section") or "Reviewer Notes / Learned Fixes")
    note = str(body.get("note") or "").strip()
    if not note:
        return {"job_id": job_id, "ok": False, "error": "note required"}
    existing = load_memory_for_job(_job_output_dir(job_id))
    check = check_before_append(existing, section, note)
    if check["is_duplicate"]:
        return {"job_id": job_id, "ok": False, "error": "already_exists",
                "detail": "Identical rule already exists in memory.", "content": existing}
    updated = append_to_section(existing, section, note)
    save_memory_for_job(_job_output_dir(job_id), updated)
    gtest_state = _load_job_gtest_state(job_id)
    gtest_state.setdefault("project_code_config_cache", {})["project_testcode_memory.md"] = updated
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, "ok": True, "content": updated, "conflicts": check["conflicts"]}


@app.post("/api/review/testcode-memory/quick-add")
def api_quick_add_memory_rule(job_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Add a structured Quick Add rule to project memory with duplicate/conflict detection.

    Body: {rule_type, fields: {…}, source_tag: bool, preview_only: bool,
           force: bool (skip duplicate guard), replace_existing: str (bullet to replace)}
    """
    from web.project_testcode_memory import (
        append_to_section,
        check_before_append,
        format_quick_add_rule,
        load_memory_for_job,
        rule_type_section,
        save_memory_for_job,
        QUICK_ADD_RULE_TYPES,
    )

    rule_type = str(body.get("rule_type") or "reviewer_note")
    if rule_type not in QUICK_ADD_RULE_TYPES:
        return {"job_id": job_id, "ok": False, "error": f"Unknown rule_type: {rule_type}"}

    fields = dict(body.get("fields") or {})
    source_tag = bool(body.get("source_tag", True))
    preview_only = bool(body.get("preview_only", False))
    force = bool(body.get("force", False))
    replace_existing = str(body.get("replace_existing") or "").strip()

    bullet = format_quick_add_rule(rule_type, fields, source_tag=source_tag)
    if not bullet:
        return {"job_id": job_id, "ok": False, "error": "Could not generate rule — fill required fields."}

    section = rule_type_section(rule_type)

    # Preview-only mode: return bullet + check without saving
    existing = load_memory_for_job(_job_output_dir(job_id))
    check = check_before_append(existing, section, bullet)

    if preview_only:
        return {
            "job_id": job_id,
            "ok": True,
            "preview": True,
            "bullet": bullet,
            "section": section,
            "is_duplicate": check["is_duplicate"],
            "conflicts": check["conflicts"],
        }

    # Duplicate guard
    if check["is_duplicate"] and not force:
        return {
            "job_id": job_id,
            "ok": False,
            "error": "already_exists",
            "detail": "Identical rule already exists in memory.",
            "bullet": bullet,
            "section": section,
            "content": existing,
        }

    # Replace existing bullet if requested
    if replace_existing:
        import re as _re
        lines = existing.splitlines()
        new_lines = [bullet if l.strip() == replace_existing.strip() else l for l in lines]
        updated = "\n".join(new_lines)
    else:
        updated = append_to_section(existing, section, bullet)

    old_version = _get_bundle_version(job_id)
    save_memory_for_job(_job_output_dir(job_id), updated)
    # Do NOT call _persist_job_gtest_state — it calls _save_bundle_to_job which checks If-Match
    # and raises 409 on stale bundle version. Quick Add is a config-only write; the memory file
    # is the authoritative store. Subsequent codegen requests reload it via _sync_project_code_config_cache.
    # This matches the pattern used in api_put_project_code_config.
    latest_version = _get_bundle_version(job_id)
    return {
        "job_id": job_id,
        "ok": True,
        "bullet": bullet,
        "section": section,
        "conflicts": check["conflicts"],
        "content": updated,
        "bundle_version": latest_version,
        "old_version": old_version,
        "latest_version": latest_version,
        "retry_on_conflict": False,
        "merged_rule_added": True,
    }


@app.get("/api/review/testcode-memory/quick-add-schema")
def api_quick_add_schema() -> dict[str, Any]:
    from web.project_testcode_memory import QUICK_ADD_RULE_TYPES
    return {"ok": True, "rule_types": QUICK_ADD_RULE_TYPES}


@app.post("/api/review/testcode-group-context")
def api_testcode_group_context(job_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Upsert a group-level fixture/namespace context entry in ## Test Group Context.

    Body: {group_name, fixture_class, namespace?, main_function?, note?, preview_only?}
    Conflict-safe: does not call _persist_job_gtest_state, no bundle-version check.
    """
    from web.project_testcode_memory import load_memory_for_job, save_memory_for_job
    from web.test_group_context import (
        format_group_context_block,
        normalize_group_key,
        parse_group_context,
        upsert_group_context,
    )

    group_name = str(body.get("group_name") or "").strip()
    if not group_name:
        return {"job_id": job_id, "ok": False, "error": "group_name is required"}

    fixture_class = str(body.get("fixture_class") or "").strip()
    namespace = str(body.get("namespace") or "").strip()
    main_function = str(body.get("main_function") or "").strip()
    note = str(body.get("note") or "").strip()
    preview_only = bool(body.get("preview_only", False))

    out_dir = _job_output_dir(job_id)
    existing = load_memory_for_job(out_dir)
    normalized_key = normalize_group_key(group_name)
    existing_groups = parse_group_context(existing)
    is_update = normalized_key in existing_groups
    is_duplicate = False
    if is_update:
        ex = existing_groups[normalized_key]
        is_duplicate = (
            ex.get("fixture_class", "").strip() == fixture_class
            and ex.get("namespace", "").strip() == namespace
            and ex.get("main_function", "").strip() == main_function
        )

    block_preview = format_group_context_block(
        group_name, fixture_class=fixture_class, namespace=namespace,
        main_function=main_function, note=note
    )

    if preview_only:
        return {
            "job_id": job_id,
            "ok": True,
            "preview": True,
            "bullet": block_preview,
            "section": "Test Group Context",
            "is_duplicate": is_duplicate,
            "is_update": is_update,
            "normalized_group_key": normalized_key,
            "conflicts": [],
        }

    result = upsert_group_context(
        existing,
        group_name=group_name,
        fixture_class=fixture_class,
        namespace=namespace,
        main_function=main_function,
        note=note,
    )
    updated = result["content"]
    old_version = _get_bundle_version(job_id)
    save_memory_for_job(out_dir, updated)
    # Do NOT call _persist_job_gtest_state — config-only write, no bundle-version check
    latest_version = _get_bundle_version(job_id)
    return {
        "job_id": job_id,
        "ok": True,
        "section": "Test Group Context",
        "group_name": group_name,
        "normalized_group_key": result["normalized_group_key"],
        "detected_fixture_class": fixture_class,
        "detected_namespace": namespace,
        "merged_rule_added": result["merged_rule_added"],
        "merged_rule_updated": result["merged_rule_updated"],
        "duplicate_detected": result["duplicate_detected"],
        "content": updated,
        "bundle_version": latest_version,
        "old_version": old_version,
        "latest_version": latest_version,
        "retry_on_conflict": False,
        "conflicts": [],
    }


@app.get("/api/review/testcode-group-mapping")
def api_testcode_group_mapping_get(job_id: str) -> dict[str, Any]:
    """Return the persisted group mapping for this job."""
    from web.testcase_group_mapping import load_group_mapping
    mapping = load_group_mapping(_job_output_dir(job_id))
    return {"job_id": job_id, "ok": True, **mapping}


@app.put("/api/review/testcode-group-mapping")
def api_testcode_group_mapping_put(job_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Save user-edited group mapping fields (suggested_namespace, suggested_fixture_class, default_main_function).

    Only updates editable fields; preserves tc_count, candidate_ids, group_name, etc.
    Conflict-safe: no bundle-version check.
    """
    from web.testcase_group_mapping import load_group_mapping, save_group_mapping

    groups_edit = dict(body.get("groups") or {})
    out_dir = _job_output_dir(job_id)
    existing = load_group_mapping(out_dir)
    groups = dict(existing.get("groups") or {})

    for gid, edits in groups_edit.items():
        if gid not in groups:
            continue
        for field in ("suggested_namespace", "suggested_fixture_class", "default_main_function"):
            if field in edits:
                groups[gid][field] = str(edits[field] or "").strip()

    updated = {**existing, "groups": groups}
    save_group_mapping(out_dir, updated)

    # Apply updated fixture to existing drafts and clear stale FIXTURE missing-context items.
    # This replaces ALEX_FIXTURE_MISSING (or any other placeholder) with the real fixture
    # for all groups that now have suggested_fixture_class set, so "Save Mapping" has the
    # same effect as "Apply to Drafts" without requiring a separate click.
    _apply_results: dict[str, Any] = {}
    try:
        from web.copilot_batch_codegen import apply_group_mapping_to_drafts

        _gstate_put = _load_job_gtest_state(job_id)
        _updated_mapping = {**existing, "groups": groups}
        _state_dirty = False
        for _gid_put, _edits_put in groups_edit.items():
            if not str(_edits_put.get("suggested_fixture_class") or "").strip():
                continue
            # Replace placeholder / ALEX_FIXTURE_MISSING fixture in drafts for this group
            _ar = apply_group_mapping_to_drafts(_gstate_put, _updated_mapping, group_id=_gid_put)
            _apply_results[_gid_put] = _ar
            if _ar.get("updated"):
                _state_dirty = True
            # Also clear stale FIXTURE missing-context items
            _drafts_put = _gstate_put.get("drafts") or {}
            for _cid_put in (groups.get(_gid_put, {}).get("candidate_ids") or []):
                _draft_put = _drafts_put.get(_cid_put)
                if not isinstance(_draft_put, dict):
                    continue
                _old_mc = _draft_put.get("missing_context") or []
                _new_mc = [
                    _m for _m in _old_mc
                    if str(_m.get("missing_type") or "").upper() != "FIXTURE"
                    and str(_m.get("type") or "").lower() != "missing_fixture"
                ]
                if len(_new_mc) != len(_old_mc):
                    _draft_put["missing_context"] = _new_mc
                    _state_dirty = True
        if _state_dirty:
            save_gtest_state(_job_output_dir(job_id), _gstate_put)
    except Exception:
        pass

    return {
        "job_id": job_id,
        "ok": True,
        "total_groups": len(groups),
        "groups": groups,
        "apply_to_drafts": _apply_results,
    }


@app.post("/api/review/testcode-group-mapping/build")
def api_testcode_group_mapping_build(job_id: str, language: str = "EN") -> dict[str, Any]:
    """Rebuild group mapping from current workbench rows and persist it.

    Uses workbench rows from the current bundle. Conflict-safe: no bundle-version check.
    """
    from src.exporters.customer_testspec_exporter import build_customer_testspec_preview
    from web.testcase_group_mapping import build_group_mapping, save_group_mapping

    bundle = _bundle_for_job(job_id)
    preview = build_customer_testspec_preview(bundle, language=language.upper())
    rows = preview.get("rows") or []
    mapping = build_group_mapping(rows)
    save_group_mapping(_job_output_dir(job_id), mapping)
    return {
        "job_id": job_id,
        "ok": True,
        "total_groups": mapping["total_groups"],
        "diagnostics": mapping["diagnostics"],
        "sample_group_mapping": mapping["sample_group_mapping"],
    }


@app.post("/api/review/testcode-group-mapping/apply-to-drafts")
def api_testcode_group_mapping_apply_to_drafts(
    job_id: str, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Apply group mapping fixture classes to existing drafts without calling Copilot.

    For each TC in each group (or the specified group_id), replaces
    TEST_F(oldFixture, name) with TEST_F(newFixture, name) using suggested_fixture_class.
    SAVED drafts become NEEDS_REVIEW.  Preserves test body.
    """
    from web.copilot_batch_codegen import apply_group_mapping_to_drafts
    from web.testcase_group_mapping import load_group_mapping

    body = body or {}
    group_id = str(body.get("group_id") or "").strip() or None

    group_mapping = load_group_mapping(_job_output_dir(job_id))
    if not group_mapping or not group_mapping.get("groups"):
        return {"job_id": job_id, "ok": False, "error": "No group mapping found for this job."}

    gtest_state = _load_job_gtest_state(job_id)
    result = apply_group_mapping_to_drafts(gtest_state, group_mapping, group_id=group_id)

    if result.get("updated"):
        _persist_job_gtest_state(job_id, gtest_state)

    return {"job_id": job_id, **result}


def _config_bundle_text_from_body(body: ConfigBundleTextRequest) -> tuple[str, list[str]]:
    from web.config_bundle_layers import extract_bundle_text_from_payload

    return extract_bundle_text_from_payload(body.model_dump())


@app.post("/api/review/project-code-config/preview-bundle")
def api_project_code_config_preview_bundle(job_id: str, body: ConfigBundleTextRequest) -> Any:
    from web.config_bundle_layers import bundle_error_payload, preview_config_bundle

    text, payload_keys = _config_bundle_text_from_body(body)
    if not text:
        return JSONResponse(
            status_code=400,
            content=bundle_error_payload(
                "Bundle text is required (use JSON key: bundle, text, content, or bundle_markdown)",
                text=text,
                payload_keys=payload_keys,
            ),
        )
    result = preview_config_bundle(_job_output_dir(job_id), text)
    if not result.get("ok"):
        if payload_keys and "payload_keys" in (result.get("details") or {}):
            result["details"]["payload_keys"] = payload_keys
        elif result.get("details") is not None:
            result["details"]["payload_keys"] = payload_keys
        return JSONResponse(status_code=400, content=result)
    return {"job_id": job_id, **result}


@app.post("/api/review/project-code-config/apply-bundle-import")
def api_project_code_config_apply_bundle_import(
    job_id: str, body: ConfigBundleApplyImportRequest
) -> Any:
    from web.config_bundle_layers import apply_bundle_import_sections, bundle_error_payload

    text, payload_keys = _config_bundle_text_from_body(body)
    if not text:
        return JSONResponse(
            status_code=400,
            content=bundle_error_payload(
                "Bundle text is required (use JSON key: bundle, text, content, or bundle_markdown)",
                text=text,
                payload_keys=payload_keys,
            ),
        )
    result = apply_bundle_import_sections(
        _job_output_dir(job_id),
        text,
        selected_sections=body.selected_sections,
    )
    if not result.get("ok"):
        if isinstance(result.get("details"), dict):
            result["details"]["payload_keys"] = payload_keys
        return JSONResponse(status_code=400, content=result)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/config-bundle/propose")
def api_config_bundle_propose(job_id: str, body: ConfigBundleProposeRequest) -> Any:
    from web.config_bundle_layers import bundle_error_payload, propose_config_bundle

    text, payload_keys = _config_bundle_text_from_body(body)
    if not text:
        return JSONResponse(
            status_code=400,
            content=bundle_error_payload(
                "Bundle text is required (use JSON key: bundle, text, content, or bundle_markdown)",
                text=text,
                payload_keys=payload_keys,
            ),
        )
    result = propose_config_bundle(_job_output_dir(job_id), text)
    if not result.get("ok"):
        if isinstance(result.get("details"), dict):
            result["details"]["payload_keys"] = payload_keys
        return JSONResponse(status_code=400, content=result)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/config-bundle/apply")
def api_config_bundle_apply(job_id: str, body: ConfigBundleApplyRequest) -> dict[str, Any]:
    from web.config_bundle_layers import apply_config_bundle_proposal

    result = apply_config_bundle_proposal(
        _job_output_dir(job_id),
        mode=body.mode,
        selected_ids=body.selected_ids,
        allow_removals=body.allow_removals,
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "apply failed")
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.get("/api/review/config-bundle/export")
def api_config_bundle_export(job_id: str) -> dict[str, Any]:
    from web.config_bundle_layers import export_effective_config_bundle

    return {"job_id": job_id, **export_effective_config_bundle(_job_output_dir(job_id))}


@app.post("/api/review/config-bundle/improvement-prompt")
def api_config_bundle_improvement_prompt(
    job_id: str, body: ConfigImprovementPromptRequest | None = None
) -> dict[str, Any]:
    from web.config_bundle_layers import build_config_improvement_prompt

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    lang = (body.language if body else None) or "EN"
    cr = (body.change_request if body else None) or ""
    return {
        "job_id": job_id,
        **build_config_improvement_prompt(
            _job_output_dir(job_id),
            gtest_state,
            change_request=cr,
            bundle=bundle,
            language=lang,
        ),
    }


@app.post("/api/review/config-bundle/learned-mapping")
def api_config_learned_mapping(job_id: str, body: LearnedMappingRequest) -> dict[str, Any]:
    from web.config_bundle_layers import add_learned_mapping
    from web.local_template_codegen import check_mapping_coverage

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    result = add_learned_mapping(
        _job_output_dir(job_id),
        body.term,
        body.code,
        use_project_override=body.use_project_override,
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "failed")
    cmap = dict(gtest_state.get("code_variable_map") or {})
    cmap[body.term] = body.code
    gtest_state["code_variable_map"] = cmap
    cov = check_mapping_coverage(bundle, gtest_state, _job_output_dir(job_id), language="EN")
    _sync_project_code_config_cache(job_id, gtest_state)
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, "mapping_coverage": cov, **result}


@app.post("/api/review/config-bundle/learned-rule")
def api_config_learned_rule(job_id: str, body: LearnedRuleRequest) -> dict[str, Any]:
    from web.config_bundle_layers import add_learned_rule

    if not (body.rule_text or "").strip():
        raise HTTPException(400, "rule_text is required")
    result = add_learned_rule(_job_output_dir(job_id), body.rule_text, context=body.context)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "failed")
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/config-bundle/rollback")
def api_config_bundle_rollback(job_id: str, body: ConfigVersionRollbackRequest) -> dict[str, Any]:
    from web.config_bundle_layers import rollback_config_version

    result = rollback_config_version(_job_output_dir(job_id), body.config_version_id)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "rollback failed")
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/analyze-project-context")
def api_analyze_project_context(job_id: str, body: AnalyzeProjectContextRequest | None = None) -> dict[str, Any]:
    from web.test_code_smart_workflow import analyze_project_context

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    lang = (body.language if body else None) or "EN"
    extra = (body.extra_snippets if body else None) or []
    paste = str(gtest_state.get("sample_paste") or "").strip()
    if paste:
        extra = list(extra) + [paste]
    result = analyze_project_context(
        _job_output_dir(job_id),
        bundle,
        gtest_state,
        language=lang,
        extra_snippets=extra or None,
        force=bool(body.force) if body else False,
    )
    _sync_project_code_config_cache(job_id, gtest_state)
    report_payload = _smart_workflow_run_report_payload(
        job_id,
        gtest_state,
        bundle,
        event="analyze_project_context",
        event_data=result,
        language=lang,
    )
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result, **report_payload}


@app.post("/api/review/propose-missing-mappings")
def api_propose_missing_mappings(job_id: str, body: MappingCoverageRequest | None = None) -> dict[str, Any]:
    from web.code_style_samples import load_code_style_samples
    from web.test_code_smart_workflow import build_copilot_mapping_prompt, propose_missing_mappings

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    lang = (body.language if body else None) or "EN"
    result = propose_missing_mappings(bundle, gtest_state, _job_output_dir(job_id), language=lang)
    samples = load_code_style_samples(bundle)
    excerpt = str((samples[0] or {}).get("snippet") or "") if samples else ""
    proposals = result.get("proposals") or []
    report_payload = _smart_workflow_run_report_payload(
        job_id,
        gtest_state,
        bundle,
        event="propose_missing_mappings",
        event_data=result,
        language=lang,
    )
    _persist_job_gtest_state(job_id, gtest_state)
    return {
        "job_id": job_id,
        **result,
        "copilot_mapping_prompt": build_copilot_mapping_prompt(proposals, sample_excerpt=excerpt),
        **report_payload,
    }


@app.post("/api/review/accept-proposed-mappings")
def api_accept_proposed_mappings(job_id: str, body: AcceptProposedMappingsRequest) -> dict[str, Any]:
    from web.test_code_smart_workflow import accept_proposed_mappings

    gtest_state = _load_job_gtest_state(job_id)
    result = accept_proposed_mappings(
        _job_output_dir(job_id),
        gtest_state,
        body.items or [],
        use_project_override=body.use_project_override,
    )
    bundle = _bundle_for_job(job_id)
    from web.local_template_codegen import check_mapping_coverage

    cov = check_mapping_coverage(bundle, gtest_state, _job_output_dir(job_id), language="EN")
    _sync_project_code_config_cache(job_id, gtest_state)
    report_payload = _smart_workflow_run_report_payload(
        job_id,
        gtest_state,
        bundle,
        event="accept_proposed_mappings",
        event_data={"mapping_coverage": cov, **result},
        language="EN",
    )
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, "mapping_coverage": cov, **result, **report_payload}


@app.post("/api/review/generate-code-smart-mode")
def api_generate_code_smart_mode(job_id: str, body: SmartGenerateCodeRequest | None = None) -> dict[str, Any]:
    from web.test_code_smart_workflow import smart_generate_code

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    lang = (body.language if body else None) or "EN"
    result = smart_generate_code(
        bundle,
        gtest_state,
        _job_output_dir(job_id),
        language=lang,
        candidate_ids=body.candidate_ids if body else None,
        auto_accept_high_confidence=body.auto_accept_high_confidence if body else True,
        analyze_if_sparse=body.analyze_if_sparse if body else True,
        use_api_for_hard=bool(body.use_api_for_hard) if body else False,
        cfg=_cfg(),
        library_root=_library_root(),
    )
    _sync_project_code_config_cache(job_id, gtest_state)
    report_payload = _smart_workflow_run_report_payload(
        job_id,
        gtest_state,
        bundle,
        event="smart_generate",
        event_data=result,
        language=lang,
    )
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result, **report_payload}


@app.get("/api/review/smart-workflow-run-report")
def api_smart_workflow_run_report(job_id: str, language: str = "EN") -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    report_payload = _smart_workflow_run_report_payload(
        job_id, gtest_state, bundle, language=language or "EN"
    )
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **report_payload}


@app.post("/api/review/mark-code-exemplar")
def api_mark_code_exemplar(job_id: str, body: MarkCodeExemplarRequest) -> dict[str, Any]:
    from web.exemplar_batch_codegen import mark_code_exemplar

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    result = mark_code_exemplar(
        bundle, gtest_state, body.candidate_id, language=body.language or "EN"
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "mark exemplar failed")
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/clear-code-exemplar")
def api_clear_code_exemplar(job_id: str) -> dict[str, Any]:
    from web.exemplar_batch_codegen import clear_code_exemplar

    gtest_state = _load_job_gtest_state(job_id)
    result = clear_code_exemplar(gtest_state)
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/exemplar-batch-prompt")
def api_exemplar_batch_prompt(job_id: str, body: ExemplarBatchPromptRequest | None = None) -> dict[str, Any]:
    from web.exemplar_batch_codegen import build_exemplar_batch_prompts

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    lang = (body.language if body else None) or "EN"
    result = build_exemplar_batch_prompts(
        bundle,
        gtest_state,
        candidate_ids=body.candidate_ids if body else None,
        language=lang,
        engineer_note=str(body.engineer_note if body else "") or "",
        scope=str(body.scope if body else "filter") or "filter",
        group_key=str(body.group_key if body else "") or "",
        group_field=str(body.group_field if body else "test_group") or "test_group",
        allow_missing_sample=bool(body.allow_missing_sample) if body else False,
        user_id=uid,
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "exemplar prompt failed")
    return {"job_id": job_id, **result}


@app.post("/api/review/import-exemplar-batch")
def api_import_exemplar_batch(job_id: str, body: ExemplarBatchImportRequest) -> dict[str, Any]:
    from web.exemplar_batch_codegen import apply_exemplar_batch_import, resolve_exemplar_target_ids

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    targets = resolve_exemplar_target_ids(
        bundle,
        gtest_state,
        candidate_ids=body.candidate_ids,
        language=body.language or "EN",
        scope=body.scope or "filter",
        group_key=body.group_key or "",
        group_field=body.group_field or "test_group",
    )
    expected = body.candidate_ids if body.candidate_ids else targets
    result = apply_exemplar_batch_import(
        bundle,
        gtest_state,
        _job_output_dir(job_id),
        content=body.content,
        expected_candidate_ids=expected,
        language=body.language or "EN",
    )
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/copilot-batch-prompt")
def api_copilot_batch_prompt(job_id: str, body: CopilotBatchPromptRequest | None = None) -> dict[str, Any]:
    from web.copilot_batch_codegen import build_copilot_batch_prompts

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    lang = (body.language if body else None) or "EN"
    result = build_copilot_batch_prompts(
        bundle,
        gtest_state,
        candidate_ids=body.candidate_ids if body else None,
        language=lang,
        engineer_note=str(body.engineer_note if body else "") or "",
        batch_size=body.batch_size if body else 10,
        skip_saved=bool(body.skip_saved) if body else False,
        scope=str(body.scope if body else "filter") or "filter",
        group_key=str(body.group_key if body else "") or "",
        group_field=str(body.group_field if body else "test_group") or "test_group",
        allow_missing_sample=bool(body.allow_missing_sample) if body else False,
        slim_prompt=bool(body.slim_prompt) if body else True,
        prompt_budget=int(body.prompt_budget) if body else 5000,
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "copilot batch prompt failed")
    return {"job_id": job_id, **result}


@app.post("/api/review/import-copilot-batch")
def api_import_copilot_batch(job_id: str, body: CopilotBatchImportRequest) -> dict[str, Any]:
    from web.copilot_batch_codegen import apply_copilot_batch_import, resolve_copilot_batch_targets

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    targets = resolve_copilot_batch_targets(
        bundle,
        gtest_state,
        candidate_ids=body.candidate_ids,
        language=body.language or "EN",
        scope=body.scope or "filter",
        group_key=body.group_key or "",
        group_field=body.group_field or "test_group",
    )
    expected = body.candidate_ids if body.candidate_ids else targets
    result = apply_copilot_batch_import(
        bundle,
        gtest_state,
        _job_output_dir(job_id),
        content=body.content,
        expected_candidate_ids=expected,
        language=body.language or "EN",
    )
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/run-copilot-batch-api")
def api_run_copilot_batch_api(job_id: str, body: CopilotBatchApiRequest | None = None) -> dict[str, Any]:
    from web.copilot_batch_codegen import run_copilot_batch_api

    cfg = _cfg()
    uid = _m365_effective_user_id(cfg)
    m365_st = m365_auth.m365_status(cfg, user_id=uid)
    if not m365_st.get("api_ready"):
        return {"job_id": job_id, **classify_copilot_error(m365_ready=False)}
    if m365_st.get("copilot_chat_entitled") is False:
        return {"job_id": job_id, **classify_copilot_error(m365_ready=True, copilot_entitled=False)}
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    lang = (body.language if body else None) or "EN"
    result = run_copilot_batch_api(
        bundle,
        gtest_state,
        _job_output_dir(job_id),
        cfg=cfg,
        candidate_ids=body.candidate_ids if body else None,
        language=lang,
        engineer_note=str(body.engineer_note if body else "") or "",
        clarification_note=str(body.clarification_note if body else "") or "",
        batch_size=body.batch_size if body else 10,
        skip_saved=bool(body.skip_saved) if body else False,
        scope=str(body.scope if body else "filter") or "filter",
        group_key=str(body.group_key if body else "") or "",
        group_field=str(body.group_field if body else "test_group") or "test_group",
        allow_missing_sample=bool(body.allow_missing_sample) if body else True,
        slim_prompt=bool(body.slim_prompt) if body else True,
        prompt_budget=int(body.prompt_budget) if body else 5000,
    )
    _persist_job_gtest_state(job_id, gtest_state)
    if not result.get("ok"):
        result = enrich_error_response(
            result,
            m365_ready=True,
            copilot_entitled=True,
            has_bundle=True,
            has_candidates=True,
            raw_error=str(result.get("error") or ""),
        )
    return {"job_id": job_id, **result}


@app.post("/api/review/testcode-missing-context")
def api_testcode_missing_context(job_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Analyze what project context is missing for each requested testcase.

    Returns per-TC missing item lists so the user can add Quick Add rules
    before or after generation.  HTTP 200 always.
    Also returns memory_diagnostics for the UI to show source/stats.
    """
    from web.copilot_batch_codegen import analyze_missing_generation_context
    from web.gtest_workspace import _workbench_row_for_candidate
    from web.project_testcode_memory import _job_memory_path, memory_diagnostics

    candidate_ids: list[str] = list((body or {}).get("candidate_ids") or [])
    language = str((body or {}).get("language") or "EN")
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)

    # Memory diagnostics for client display
    cache = gtest_state.get("project_code_config_cache") or {}
    mem_content = str(cache.get("project_testcode_memory.md") or "")
    job_mem_path = _job_memory_path(_job_output_dir(job_id))
    mem_source = "job_override" if (job_mem_path.exists() and mem_content.strip()) else "global"
    mem_diag = memory_diagnostics(mem_content)
    mem_diag["source"] = mem_source
    mem_diag["path"] = str(job_mem_path) if mem_source == "job_override" else "global"

    reports: list[dict[str, Any]] = []
    # If no IDs requested, use all TCs with NEEDS_REVIEW or ERROR draft
    if not candidate_ids:
        drafts = gtest_state.get("drafts") or {}
        candidate_ids = [
            cid for cid, d in drafts.items()
            if isinstance(d, dict) and str(d.get("code_status") or "").upper() in {"NEEDS_REVIEW", "ERROR"}
        ]

    try:
        from web.testcase_group_mapping import _mapping_path as _gmap_path_fn, load_group_mapping as _load_gmap_mc
        _job_out_mc = _job_output_dir(job_id)
        _group_mapping_mc = _load_gmap_mc(_job_out_mc) or {}
        _gmap_load_path_str = str(_gmap_path_fn(_job_out_mc))
    except Exception:
        _group_mapping_mc = {}
        _gmap_load_path_str = ""

    _gmap_groups_mc = _group_mapping_mc.get("groups") or {}
    _gmap_total_mc = _group_mapping_mc.get("total_groups") or len(_gmap_groups_mc)

    # Retrieve last prompt tc_diagnostics for cross-referencing prompt context
    _batch_state_mc = gtest_state.get("copilot_batch") or {}
    _last_prompt_diag_mc = _batch_state_mc.get("last_prompt_diag") or {}
    _tc_diag_list_mc: list[dict[str, Any]] = _last_prompt_diag_mc.get("tc_diagnostics") or []

    for cid in candidate_ids[:50]:  # limit to 50 to avoid huge responses
        row = _workbench_row_for_candidate(bundle, cid, language=language) or {"candidate_id": cid}
        missing = analyze_missing_generation_context(row, gtest_state, group_mapping=_group_mapping_mc or None)
        # Only include stored missing_context items that are still unresolved (not in fresh analysis)
        fresh_keys = {(m.get("type"), m.get("signal")) for m in missing}
        draft = (gtest_state.get("drafts") or {}).get(cid) or {}
        stored_missing = [
            m for m in (draft.get("missing_context") or [])
            if (m.get("type"), m.get("signal")) not in fresh_keys
            # Re-check: only keep stored items whose signal is still missing from memory
            and (not m.get("signal") or m["signal"].upper() not in mem_content.upper())
        ]
        all_missing = {(m.get("type"), m.get("signal")): m for m in missing + stored_missing}

        # Build per-TC group mapping diagnostics
        _gid_mc = str(row.get("group_id") or "")
        _grp_mc = _gmap_groups_mc.get(_gid_mc) if _gid_mc else None
        _gmap_fixture_mc = str((_grp_mc or {}).get("suggested_fixture_class") or "").strip()
        _fresh_has_fixture_missing = any(m.get("type") == "missing_fixture" for m in missing)
        _all_has_fixture_missing = any(
            str(m.get("missing_type") or m.get("type") or "").upper() in ("FIXTURE", "MISSING_FIXTURE")
            for m in list(all_missing.values())
        )
        _last_tc_diag_mc: dict[str, Any] = next(
            (d for d in _tc_diag_list_mc if str(d.get("testcase_id") or "") == cid), {}
        )
        reports.append({
            "candidate_id": cid,
            "missing_items": list(all_missing.values()),
            "has_issues": bool(all_missing),
            "issue_reason": draft.get("issue_reason") or "",
            "code_status": str(draft.get("code_status") or "NO_CODE"),
            "diagnostics": {
                "selected_testcase_id": cid,
                "selected_row_group_id": _gid_mc,
                "group_mapping_load_path": _gmap_load_path_str,
                "group_mapping_loaded_total_groups": _gmap_total_mc,
                "group_mapping_group_found": bool(_grp_mc),
                "group_mapping_fixture_used": _gmap_fixture_mc,
                "missing_fixture_suppressed_by_group_mapping": _fresh_has_fixture_missing and not _all_has_fixture_missing,
                "prompt_contains_GROUP_CONTEXT": _last_tc_diag_mc.get("prompt_contains_GROUP_CONTEXT"),
                "prompt_contains_group_fixture": bool(_last_tc_diag_mc.get("group_fixture_used")),
                "prompt_contains_TryTo_xxx": _last_tc_diag_mc.get("prompt_contains_TryTo_xxx"),
            },
        })

    return {
        "ok": True,
        "job_id": job_id,
        "reports": reports,
        "total": len(reports),
        "memory_diagnostics": mem_diag,
    }


@app.post("/api/review/run-copilot-batch-api-single")
def api_run_copilot_batch_api_single(
    job_id: str, body: CopilotBatchApiRequest | None = None
) -> dict[str, Any]:
    """Run Copilot API for a single selected testcase with optional clarification note.

    Used by 'Retry this testcase' button. Does not skip_saved so user can overwrite.
    """
    from web.copilot_batch_codegen import run_copilot_batch_api

    cfg = _cfg()
    uid = _m365_effective_user_id(cfg)
    m365_st = m365_auth.m365_status(cfg, user_id=uid)
    if not m365_st.get("api_ready"):
        return {"job_id": job_id, **classify_copilot_error(m365_ready=False)}
    if m365_st.get("copilot_chat_entitled") is False:
        return {"job_id": job_id, **classify_copilot_error(m365_ready=True, copilot_entitled=False)}

    candidate_id = str((body.candidate_ids or [None])[0] if body and body.candidate_ids else "") or ""
    if not candidate_id:
        return {"job_id": job_id, "ok": False, "error": "candidate_id required for single retry"}

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    lang = (body.language if body else None) or "EN"

    result = run_copilot_batch_api(
        bundle,
        gtest_state,
        _job_output_dir(job_id),
        cfg=cfg,
        candidate_ids=[candidate_id],
        language=lang,
        engineer_note=str(body.engineer_note if body else "") or "",
        clarification_note=str(body.clarification_note if body else "") or "",
        batch_size=1,
        skip_saved=False,
        scope="selected",
        allow_missing_sample=True,
        slim_prompt=bool(body.slim_prompt) if body else True,
        prompt_budget=int(body.prompt_budget) if body else 5000,
    )
    _persist_job_gtest_state(job_id, gtest_state)
    if not result.get("ok"):
        result = enrich_error_response(
            result,
            m365_ready=True,
            copilot_entitled=True,
            has_bundle=True,
            has_candidates=True,
            raw_error=str(result.get("error") or ""),
        )
    return {"job_id": job_id, **result}


@app.post("/api/review/run-copilot-batch-api-retry-failed")
def api_run_copilot_batch_api_retry_failed(
    job_id: str, body: CopilotBatchApiRequest | None = None
) -> dict[str, Any]:
    """Re-run Copilot API only for testcases in NEEDS_REVIEW or ERROR state.

    SAVED testcases are never overwritten (skip_saved is always True).
    Target IDs are collected in Excel import order from the current drafts.
    """
    from web.copilot_batch_codegen import collect_retry_candidate_ids, run_copilot_batch_api

    cfg = _cfg()
    uid = _m365_effective_user_id(cfg)
    m365_st = m365_auth.m365_status(cfg, user_id=uid)
    if not m365_st.get("api_ready"):
        return {"job_id": job_id, **classify_copilot_error(m365_ready=False)}
    if m365_st.get("copilot_chat_entitled") is False:
        return {"job_id": job_id, **classify_copilot_error(m365_ready=True, copilot_entitled=False)}

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    lang = (body.language if body else None) or "EN"

    retry_ids = collect_retry_candidate_ids(gtest_state, bundle, language=lang)
    if not retry_ids:
        return {"job_id": job_id, "ok": False, "error": "no_failed_candidates",
                "detail": "No testcases in NEEDS_REVIEW or ERROR state."}

    result = run_copilot_batch_api(
        bundle,
        gtest_state,
        _job_output_dir(job_id),
        cfg=cfg,
        candidate_ids=retry_ids,
        language=lang,
        engineer_note=str(body.engineer_note if body else "") or "",
        clarification_note=str(body.clarification_note if body else "") or "",
        batch_size=body.batch_size if body else 10,
        skip_saved=True,
        scope="filter",
        group_key="",
        allow_missing_sample=True,
        slim_prompt=bool(body.slim_prompt) if body else True,
        prompt_budget=int(body.prompt_budget) if body else 5000,
    )
    _persist_job_gtest_state(job_id, gtest_state)
    if not result.get("ok"):
        result = enrich_error_response(
            result,
            m365_ready=True,
            copilot_entitled=True,
            has_bundle=True,
            has_candidates=True,
            raw_error=str(result.get("error") or ""),
        )
    return {"job_id": job_id, "retry_candidate_count": len(retry_ids), **result}


@app.post("/api/review/run-exemplar-batch-api")
def api_run_exemplar_batch_api(job_id: str, body: ExemplarBatchApiRequest | None = None) -> dict[str, Any]:
    from web.exemplar_batch_codegen import run_exemplar_batch_api

    cfg = _cfg()
    uid = _m365_effective_user_id(cfg)
    m365_st = m365_auth.m365_status(cfg, user_id=uid)
    if not m365_st.get("api_ready"):
        return {"job_id": job_id, **classify_copilot_error(m365_ready=False)}
    if m365_st.get("copilot_chat_entitled") is False:
        return {"job_id": job_id, **classify_copilot_error(m365_ready=True, copilot_entitled=False)}
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    lang = (body.language if body else None) or "EN"
    result = run_exemplar_batch_api(
        bundle,
        gtest_state,
        _job_output_dir(job_id),
        cfg=cfg,
        candidate_ids=body.candidate_ids if body else None,
        language=lang,
        engineer_note=str(body.engineer_note if body else "") or "",
        scope=str(body.scope if body else "filter") or "filter",
        group_key=str(body.group_key if body else "") or "",
        group_field=str(body.group_field if body else "test_group") or "test_group",
    )
    _persist_job_gtest_state(job_id, gtest_state)
    if not result.get("ok"):
        result = enrich_error_response(
            result,
            m365_ready=True,
            copilot_entitled=True,
            has_bundle=True,
            has_candidates=True,
            raw_error=str(result.get("error") or ""),
        )
    return {"job_id": job_id, **result}


@app.post("/api/review/mapping-coverage")
def api_mapping_coverage(job_id: str, body: MappingCoverageRequest | None = None) -> dict[str, Any]:
    from web.local_template_codegen import check_mapping_coverage

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    lang = (body.language if body else None) or "EN"
    result = check_mapping_coverage(bundle, gtest_state, _job_output_dir(job_id), language=lang)
    report_payload = _smart_workflow_run_report_payload(
        job_id,
        gtest_state,
        bundle,
        event="mapping_coverage",
        event_data={"coverage": result, **result},
        language=lang,
    )
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result, **report_payload}


@app.post("/api/review/generate-local-template")
def api_generate_local_template(job_id: str, body: LocalTemplateGenerateRequest | None = None) -> dict[str, Any]:
    from web.code_text_transform import load_code_style_samples
    from web.local_template_codegen import batch_generate_local_template

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    _sync_project_code_config_cache(job_id, gtest_state)
    lang = (body.language if body else None) or "EN"
    cids = body.candidate_ids if body else None
    samples = load_code_style_samples(bundle)
    sample_snippet = str((samples[0] or {}).get("snippet") or "") if samples else ""
    result = batch_generate_local_template(
        bundle,
        gtest_state,
        _job_output_dir(job_id),
        candidate_ids=cids,
        language=lang,
        sample_snippet=sample_snippet,
    )
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/ai-batch-review-pack")
def api_ai_batch_review_pack(job_id: str, body: AiBatchReviewPackRequest | None = None) -> dict[str, Any]:
    from web.ai_review_pack import build_ai_batch_review_pack
    from web.gtest_workspace import classify_sync_status
    from web.local_template_codegen import check_mapping_coverage
    from web.project_code_config import load_project_code_config

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    config = load_project_code_config(_job_output_dir(job_id))
    lang = (body.language if body else None) or "EN"
    change_request = (body.change_request if body else "") or ""
    filt = (body.filter if body else "selected") or "selected"
    if body and body.candidate_ids:
        target_ids = list(body.candidate_ids)
    elif filt == "all":
        from src.exporters.customer_testspec_exporter import build_customer_testspec_preview

        preview = build_customer_testspec_preview(bundle, language=lang)
        target_ids = [str(r.get("candidate_id") or "") for r in preview.get("rows") or [] if r.get("candidate_id")]
    elif filt == "needs_review":
        target_ids = [
            cid
            for cid, d in (gtest_state.get("drafts") or {}).items()
            if str(d.get("code_status") or "").upper() == "NEEDS_REVIEW"
        ]
    elif filt == "error":
        target_ids = [
            cid
            for cid, d in (gtest_state.get("drafts") or {}).items()
            if str(d.get("code_status") or "").upper() == "ERROR"
        ]
    elif filt == "missing_mapping":
        cov = check_mapping_coverage(bundle, gtest_state, _job_output_dir(job_id), language=lang)
        target_ids = list(cov.get("affected_testcase_ids") or [])
    else:
        sync = classify_sync_status(bundle, gtest_state, language=lang)
        target_ids = [
            str(r.get("candidate_id") or "")
            for r in sync.get("rows") or []
            if str(r.get("candidate_id") or "")
        ]
    pack = build_ai_batch_review_pack(
        bundle,
        gtest_state,
        candidate_ids=target_ids,
        config=config,
        change_request=change_request,
        language=lang,
    )
    return {"job_id": job_id, "candidate_count": len(target_ids), **pack}


@app.post("/api/review/gtest-quality-check")
def api_gtest_quality_check(job_id: str, body: GTestQualityCheckRequest) -> dict[str, Any]:
    from web.code_quality_gate import run_quality_gate
    from web.code_text_transform import load_code_style_samples
    from web.gtest_workspace import _structured_io_for_candidate, _workbench_row_for_candidate

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    cfg_cache = gtest_state.get("project_code_config_cache") or {}
    if not cfg_cache:
        _sync_project_code_config_cache(job_id, gtest_state)
        cfg_cache = gtest_state.get("project_code_config_cache") or {}
    lang = body.language or "EN"
    wb = _workbench_row_for_candidate(bundle, body.candidate_id, language=lang) or {}
    structured = _structured_io_for_candidate(bundle, body.candidate_id, language=lang)
    samples = load_code_style_samples(bundle)
    sample_snippet = str((samples[0] or {}).get("snippet") or "") if samples else ""
    qg = run_quality_gate(
        body.full_snippet,
        candidate_id=body.candidate_id,
        structured_io=structured,
        code_rules_md=str(cfg_cache.get("code_rules.md") or ""),
        api_catalog_yaml=str(cfg_cache.get("api_catalog.yaml") or ""),
        sample_snippet=sample_snippet,
        expected_input=str(wb.get("expected_input") or ""),
        expected_output=str(wb.get("expected_output") or ""),
    )
    return {"job_id": job_id, "candidate_id": body.candidate_id, **qg}


@app.get("/api/review/gtest-merge-saved-preview")
def api_gtest_merge_saved_preview(
    job_id: str,
    language: str = "EN",
    require_engineer_approved: bool = False,
) -> dict[str, Any]:
    from web.code_text_transform import merge_saved_code_preview

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    sync = classify_sync_status(bundle, gtest_state, language=language or "EN")
    sync_map = {str(r.get("candidate_id") or ""): str(r.get("status") or "") for r in sync.get("rows") or []}
    result = merge_saved_code_preview(
        gtest_state,
        bundle,
        language=language or "EN",
        sync_map=sync_map,
        require_engineer_approved=require_engineer_approved,
        job_id=job_id,
    )
    return {"job_id": job_id, **result}


@app.post("/api/review/testcode-confirm-selected")
def api_testcode_confirm_selected(job_id: str, body: TestCodeApprovalRequest) -> dict[str, Any]:
    from web.test_code_approval import confirm_test_code_drafts

    gtest_state = _load_job_gtest_state(job_id)
    ids = [c for c in (body.candidate_ids or []) if c]
    if not ids:
        raise HTTPException(400, "candidate_ids required")
    result = confirm_test_code_drafts(gtest_state, ids)
    # Force-merge: reload the freshest bundle and bypass stale If-Match.
    # Confirm only writes approval metadata — it never overwrites code bodies.
    _fresh_bundle = _bundle_for_job(job_id)
    sync_gtest_to_bundle(_fresh_bundle, gtest_state)
    save_gtest_state(_job_output_dir(job_id), gtest_state)
    _new_version = _save_bundle_to_job(job_id, _fresh_bundle, force=True)
    all_drafts = (gtest_state.get("drafts") or {}).values()
    exportable_count = sum(1 for d in all_drafts if isinstance(d, dict) and d.get("exportable"))
    confirmed_count_after_confirm = sum(
        1 for d in all_drafts
        if isinstance(d, dict) and str(d.get("approval_status") or "").upper() in {"CONFIRMED", "APPROVED"}
    )
    return {
        "job_id": job_id,
        "bundle_version": _new_version,
        "latest_bundle_version": _new_version,
        "persisted_bundle_version": _new_version,
        "force_merge_used": True,
        "exportable_count": exportable_count,
        "confirmed_ids": result.get("confirmed", []),
        "confirmed_count_after_confirm": confirmed_count_after_confirm,
        **result,
    }


@app.post("/api/review/testcode-approve")
def api_testcode_approve(job_id: str, body: TestCodeApprovalRequest) -> dict[str, Any]:
    from web.test_code_approval import approve_test_code_drafts

    gtest_state = _load_job_gtest_state(job_id)
    ids = [c for c in (body.candidate_ids or []) if c]
    if not ids:
        raise HTTPException(400, "candidate_ids required")
    result = approve_test_code_drafts(gtest_state, ids, only_saved=True)
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/testcode-approve-all-saved")
def api_testcode_approve_all_saved(job_id: str) -> dict[str, Any]:
    from web.test_code_approval import approve_all_saved_test_code

    gtest_state = _load_job_gtest_state(job_id)
    result = approve_all_saved_test_code(gtest_state)
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/testcode-mark-reviewed")
def api_testcode_mark_reviewed(job_id: str, body: TestCodeApprovalRequest) -> dict[str, Any]:
    from web.test_code_approval import mark_test_code_reviewed

    gtest_state = _load_job_gtest_state(job_id)
    ids = [c for c in (body.candidate_ids or []) if c]
    if not ids:
        raise HTTPException(400, "candidate_ids required")
    result = mark_test_code_reviewed(gtest_state, ids)
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/testcode-reopen")
def api_testcode_reopen(job_id: str, body: TestCodeApprovalRequest) -> dict[str, Any]:
    from web.test_code_approval import reopen_test_code_drafts

    gtest_state = _load_job_gtest_state(job_id)
    ids = [c for c in (body.candidate_ids or []) if c]
    if not ids:
        raise HTTPException(400, "candidate_ids required")
    result = reopen_test_code_drafts(gtest_state, ids)
    _persist_job_gtest_state(job_id, gtest_state)
    return {"job_id": job_id, **result}


@app.post("/api/review/testcode-edit-testcase")
def api_testcode_edit_testcase(job_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Inline testcase I/O edit from Test Code tab — saves overlay and marks code stale.

    Accepts: candidate_id, expected_input, expected_output, language.
    Delegates to the same workbench-row save path so edits are visible everywhere.
    """
    candidate_id = str(body.get("candidate_id") or "")
    if not candidate_id:
        raise HTTPException(400, "candidate_id required")

    req_body = WorkbookReviewUpdateRequest(
        candidate_id=candidate_id,
        language=str(body.get("language") or "EN"),
        expected_input=body.get("expected_input"),
        expected_output=body.get("expected_output"),
    )
    # Reuse the workbench-row save handler — it handles overlay + stale marking
    return api_review_workbench_row(job_id=job_id, body=req_body)


@app.get("/api/review/testcode-workflow-counts")
def api_testcode_workflow_counts(job_id: str) -> dict[str, Any]:
    from web.test_code_approval import count_workflow_statuses

    gtest_state = _load_job_gtest_state(job_id)
    return {"job_id": job_id, "counts": count_workflow_statuses(gtest_state)}


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
@app.get("/api/export/gtest-cc")
def api_export_gtest_cc(job_id: str, candidate_id: str) -> Response:
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    content = export_single_snippet(bundle, gtest_state, candidate_id)
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", str(candidate_id or "testcase"))[:80]
    filename = f"{safe_id}.cc"
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/export/gtest-cpp-bundle")
def api_export_gtest_cc_bundle(job_id: str) -> Response:
    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    content = export_approved_bundle(bundle, gtest_state)
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="alex_generated_tests.cc"'},
    )


@app.get("/api/export/gtest-cc-final")
def api_export_gtest_cc_final(job_id: str, language: str = "EN") -> Response:
    from web.code_text_transform import merge_saved_code_preview

    bundle = _bundle_for_job(job_id)
    gtest_state = _load_job_gtest_state(job_id)
    sync = classify_sync_status(bundle, gtest_state, language=language or "EN")
    sync_map = {str(r.get("candidate_id") or ""): str(r.get("status") or "") for r in sync.get("rows") or []}
    merged = merge_saved_code_preview(
        gtest_state,
        bundle,
        language=language or "EN",
        sync_map=sync_map,
        require_engineer_approved=False,
        job_id=job_id,
    )
    filename = str(merged.get("export_filename") or "ALEX_GTest_export.cc")
    content = str(merged.get("content") or "")
    if merged.get("export_included_count", 0) == 0:
        skip_reasons = merged.get("skipped_reason_by_testcase") or {}
        approval_statuses = merged.get("approval_status_by_testcase") or {}
        exportable_flags = merged.get("exportable_by_testcase") or {}
        diag_lines = [
            "/*",
            " * ALEX EXPORT DIAGNOSTIC — No testcase code was included in this export.",
            f" * total_drafts={merged.get('total_drafts', 0)}"
            f"  confirmed={merged.get('confirmed_count', 0)}"
            f"  exportable={merged.get('exportable_count', 0)}"
            f"  non_empty_code={merged.get('non_empty_code_count', 0)}",
            " *",
        ]
        for cid, reason in sorted(skip_reasons.items()):
            diag_lines.append(
                f" * {cid}: skip={reason}"
                f" approval={approval_statuses.get(cid, '?')!r}"
                f" exportable={exportable_flags.get(cid, '?')}"
            )
        diag_lines.append(" */")
        content = content.rstrip() + "\n" + "\n".join(diag_lines) + "\n"
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
    m365_st = _m365_copilot_gate()
    if not m365_st.get("api_ready"):
        return {"job_id": job_id, **classify_copilot_error(m365_ready=False)}
    if m365_st.get("copilot_chat_entitled") is False:
        return {"job_id": job_id, **classify_copilot_error(m365_ready=True, copilot_entitled=False)}
    bundle = _bundle_for_job(job_id)
    if not any(str(b.get("id") or "") == logic_id for b in bundle.get("logic_blocks") or []):
        return {"job_id": job_id, **classify_copilot_error(has_logic_id=False)}
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
    gate = _copilot_gate_response(bundle=bundle, logic_id=body.logic_id, has_context=False)
    if gate:
        return {"job_id": job_id, **gate}
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
    else:
        result = enrich_error_response(
            result,
            m365_ready=True,
            copilot_entitled=True,
            has_bundle=True,
            has_logic_id=True,
            has_context_pack=bool(get_copilot_session(bundle, body.logic_id).get("context_pack")),
            has_plan=False,
        )
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
    gate = _copilot_gate_response(bundle=bundle, logic_id=body.logic_id, has_context=False, has_plan=False)
    if gate:
        return {"job_id": job_id, **gate}
    result = run_write(bundle, body.logic_id, _cfg())
    if result.get("ok"):
        _save_bundle_to_job(job_id, bundle)
    else:
        session = get_copilot_session(bundle, body.logic_id)
        result = enrich_error_response(
            result,
            m365_ready=True,
            copilot_entitled=True,
            has_bundle=True,
            has_logic_id=True,
            has_context_pack=bool(session.get("context_pack")),
            has_plan=bool((session.get("plan") or {}).get("plan_items")),
        )
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


@app.post("/api/review/copilot/write-from-row")
def api_copilot_write_from_row(body: CopilotRowRequest, job_id: str) -> dict[str, Any]:
    m365_st = _m365_copilot_gate()
    if not m365_st.get("api_ready"):
        return {"job_id": job_id, **classify_copilot_error(m365_ready=False)}
    if m365_st.get("copilot_chat_entitled") is False:
        return {"job_id": job_id, **classify_copilot_error(m365_ready=True, copilot_entitled=False)}
    bundle = _bundle_for_job(job_id)
    if not bundle.get("test_candidates"):
        return {"job_id": job_id, **classify_copilot_error(has_candidates=False)}
    preview = build_customer_testspec_preview(bundle, language=body.language or "EN")
    row = next(
        (r for r in preview.get("rows") or [] if str(r.get("candidate_id") or "") == body.candidate_id),
        None,
    )
    if not row:
        return {"job_id": job_id, "ok": False, "error": f"Test case not found: {body.candidate_id}"}
    result = write_from_row_via_copilot(_cfg(), row, engineer_note=body.engineer_note)
    if not result.get("ok"):
        result = enrich_error_response(
            result,
            m365_ready=True,
            copilot_entitled=True,
            has_bundle=True,
            has_candidates=True,
            raw_error=str(result.get("error") or ""),
        )
        return {"job_id": job_id, **result}
    draft = result.get("draft") or {}
    preview_result = preview_row_draft(bundle, row, draft)
    return {"job_id": job_id, **result, **preview_result}


@app.post("/api/review/copilot/apply-row")
def api_copilot_apply_row(body: CopilotApplyRowRequest, job_id: str) -> dict[str, Any]:
    bundle = _bundle_for_job(job_id)
    if not bundle.get("test_candidates"):
        return {"job_id": job_id, **classify_copilot_error(has_candidates=False)}
    preview = build_customer_testspec_preview(bundle, language=body.language or "EN")
    row = next(
        (r for r in preview.get("rows") or [] if str(r.get("candidate_id") or "") == body.candidate_id),
        None,
    )
    if not row:
        return {"job_id": job_id, "ok": False, "error": f"Test case not found: {body.candidate_id}"}
    result = apply_row_draft(bundle, row, body.draft)
    if result.get("ok"):
        _save_bundle_to_job(job_id, bundle)
    return {"job_id": job_id, **result}


@app.post("/api/review/copilot/follow-up")
def api_copilot_follow_up(body: CopilotFollowUpRequest, job_id: str) -> dict[str, Any]:
    from web.m365_copilot import run_copilot_chat_result

    m365_st = _m365_copilot_gate()
    if not m365_st.get("api_ready"):
        return {"job_id": job_id, **classify_copilot_error(m365_ready=False)}
    if m365_st.get("copilot_chat_entitled") is False:
        return {"job_id": job_id, **classify_copilot_error(m365_ready=True, copilot_entitled=False)}
    msg = str(body.message or "").strip()
    if not msg:
        return {"job_id": job_id, "ok": False, "error": "Message is required."}
    cfg = _cfg()
    uid = _m365_effective_user_id(cfg)
    prefix = ""
    if body.logic_id:
        bundle = _bundle_for_job(job_id)
        ai = bundle.get("ai_assists") or {}
        note = str((ai.get("engineer_notes") or {}).get(body.logic_id) or "")
        if note:
            prefix = f"Engineer context for logic {body.logic_id}:\n{note[:2000]}\n\n"
    result = run_copilot_chat_result(
        cfg,
        f"{prefix}{msg}",
        user_id=uid,
        reuse_session_conversation=bool(body.reuse_conversation),
    )
    if not result.get("ok"):
        result = enrich_error_response(
            result,
            m365_ready=True,
            copilot_entitled=True,
            raw_error=str(result.get("error") or ""),
        )
    return {"job_id": job_id, "logic_id": body.logic_id, **result}


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
    if not _github_copilot_cli_enabled(_cfg()):
        return {
            "installed": False,
            "enabled": False,
            "trust_state": "disabled",
            "trust_reason": "GitHub Copilot CLI is disabled in config (assist.copilot.enabled: false).",
        }
    return probe_copilot_cli()


def _copilot_disabled() -> None:
    if not _github_copilot_cli_enabled(_cfg()):
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
            "bootstrap_source": b.get("bootstrap_source") or "analyze",
            "bootstrap_label": b.get("bootstrap_label") or "",
        },
        "strict_mode": b.get("strict_mode"),
        "module_name": derive_module_name(b),
        "has_bundle": True,
        "bootstrap_source": b.get("bootstrap_source") or "analyze",
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
        "bootstrap_source": b.get("bootstrap_source") or "analyze",
        "excel_sheets": (
            (b.get("excel_import") or {}).get("sheets")
            or (b.get("summary") or {}).get("excel_sheets")
            or []
        ),
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
