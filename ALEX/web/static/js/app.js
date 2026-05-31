/**
 * ALEX — engineering review workflow (trace evidence, approve, export).
 */
const PAGES = [
  { id: "review", step: "1", label: "Review", icon: "review" },
  { id: "logic-review", step: "2", label: "Logic & Definitions", icon: "logic" },
  { id: "diagram-graph", step: "3", label: "Diagram Graph", icon: "diagram" },
  { id: "library", step: "4", label: "Library", icon: "library" },
  { id: "export", step: "5", label: "Final File", icon: "export" },
  { id: "test-code", step: "6", label: "Test Code", icon: "code" },
  { id: "guide", step: "7", label: "Guide", icon: "guide" },
];

const PAGE_ROUTES = {
  review: { slug: "review", title: "Spec review" },
  "logic-review": { slug: "logic", title: "Logic & Definitions" },
  "diagram-graph": { slug: "diagram", title: "Diagram Graph" },
  library: { slug: "library", title: "Library" },
  export: { slug: "export", title: "Final File" },
  "test-code": { slug: "test-code", title: "Test Code" },
  guide: { slug: "guide", title: "Guide" },
};

const SLUG_TO_PAGE = Object.fromEntries(
  Object.entries(PAGE_ROUTES).map(([id, meta]) => [meta.slug, id])
);

const FILE_TYPE_OPTIONS = [
  { value: "system_spec", label: "System Spec" },
  { value: "test_spec", label: "Test Spec" },
  { value: "sample_code", label: "Sample Code" },
  { value: "test_code", label: "Test Code" },
];

const DRAFT_STORAGE_VERSION = "v1";
const AUTOSAVE_DEBOUNCE_MS = 800;
const THEME_STORAGE_KEY = "alex.theme";
const AI_SIGNIN_OPEN_KEY = "alex.aiSigninOpen";
const COPILOT_WEB_URL = "https://m365.cloud.microsoft/chat/";
const _autosaveTimers = {};

const API_CACHE_TTL = {
  summary: 4000,
  logicReview: 12000,
  workbench: 10000,
  gtestWorkspace: 60000,
  states: 12000,
};

const _apiCache = new Map();
const _apiInflight = new Map();

function invalidateApiCache(prefix = "") {
  for (const key of [..._apiCache.keys()]) {
    if (!prefix || key.startsWith(prefix)) _apiCache.delete(key);
  }
}

function noteBundleVersion(version) {
  if (version == null) return;
  if (state.bundleVersion != null && state.bundleVersion !== version) {
    invalidateApiCache();
  }
  state.bundleVersion = version;
}

async function cachedApi(key, fetcher, ttlMs = 10000) {
  const hit = _apiCache.get(key);
  if (hit && Date.now() - hit.at < ttlMs) {
    return hit.data;
  }
  if (_apiInflight.has(key)) {
    return _apiInflight.get(key);
  }
  const pending = Promise.resolve()
    .then(fetcher)
    .then((data) => {
      _apiCache.set(key, { data, at: Date.now() });
      return data;
    })
    .finally(() => _apiInflight.delete(key));
  _apiInflight.set(key, pending);
  return pending;
}

function debounceAutosave(key, fn, ms = AUTOSAVE_DEBOUNCE_MS) {
  if (_autosaveTimers[key]) window.clearTimeout(_autosaveTimers[key]);
  _autosaveTimers[key] = window.setTimeout(fn, ms);
}

function readJsonDraft(storageKey) {
  if (!storageKey) return null;
  try {
    const raw = localStorage.getItem(storageKey);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

function writeJsonDraft(storageKey, payload) {
  if (!storageKey) return;
  try {
    localStorage.setItem(storageKey, JSON.stringify({ ...payload, ts: Date.now() }));
  } catch (_) {
    /* quota or private mode */
  }
}

function clearJsonDraft(storageKey) {
  if (!storageKey) return;
  try {
    localStorage.removeItem(storageKey);
  } catch (_) {
    /* ignore */
  }
}

function workbookDraftKey(scope, candidateId) {
  if (!state.jobId || !candidateId) return "";
  return `alex.draft.${DRAFT_STORAGE_VERSION}.${state.jobId}.${scope}.${candidateId}`;
}

function readWorkbookDraft(scope, candidateId) {
  return readJsonDraft(workbookDraftKey(scope, candidateId));
}

function writeWorkbookDraft(scope, candidateId, fields) {
  writeJsonDraft(workbookDraftKey(scope, candidateId), { fields });
}

function clearWorkbookDraft(scope, candidateId) {
  clearJsonDraft(workbookDraftKey(scope, candidateId));
}

function mergeRowWithDraft(row, scope) {
  const draft = readWorkbookDraft(scope, row?.candidate_id);
  if (!draft?.fields) return row;
  return { ...row, ...draft.fields };
}

function collectWorkbookDraftFields(scope) {
  return {
    use_case: document.getElementById(`${scope}-focus-use_case`)?.value || "",
    operation: document.getElementById(`${scope}-focus-operation`)?.value || "",
    expected_input: document.getElementById(`${scope}-focus-expected_input`)?.value || "",
    expected_output: document.getElementById(`${scope}-focus-expected_output`)?.value || "",
    review_status: document.getElementById(`${scope}-focus-review_status`)?.value || "pending",
    engineer_confirmation_required:
      document.getElementById(`${scope}-focus-engineer_confirmation_required`)?.value || "yes",
    open_questions: document.getElementById(`${scope}-focus-open_questions`)?.value || "",
  };
}

function bindWorkbookDraftAutosave(scope, candidateId, statusElSelector) {
  if (!state.jobId || !candidateId) return;
  const draft = readWorkbookDraft(scope, candidateId);
  const timerKey = `${scope}:${candidateId}`;
  const fields = [
    `${scope}-focus-use_case`,
    `${scope}-focus-operation`,
    `${scope}-focus-expected_input`,
    `${scope}-focus-expected_output`,
    `${scope}-focus-review_status`,
    `${scope}-focus-engineer_confirmation_required`,
    `${scope}-focus-open_questions`,
  ];
  const saveDraft = () => {
    writeWorkbookDraft(scope, candidateId, collectWorkbookDraftFields(scope));
    const statusEl = statusElSelector ? document.querySelector(statusElSelector) : null;
    if (statusEl && !statusEl.dataset.busy) {
      statusEl.textContent = "Draft saved locally.";
    }
  };
  fields.forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("input", () => debounceAutosave(timerKey, saveDraft));
    el.addEventListener("change", () => debounceAutosave(timerKey, saveDraft));
  });
  if (draft?.fields) {
    const statusEl = statusElSelector ? document.querySelector(statusElSelector) : null;
    if (statusEl) statusEl.textContent = "Restored unsaved draft.";
  }
}

function definitionDraftKey(logicId) {
  if (!state.jobId || !logicId) return "";
  return `alex.draft.${DRAFT_STORAGE_VERSION}.${state.jobId}.definition.${logicId}`;
}

function readDefinitionDraft(logicId) {
  return readJsonDraft(definitionDraftKey(logicId));
}

function writeDefinitionDraft(logicId, text) {
  writeJsonDraft(definitionDraftKey(logicId), { text: String(text ?? "") });
}

function clearDefinitionDraft(logicId) {
  clearJsonDraft(definitionDraftKey(logicId));
}

function bindDefinitionDraftAutosave(logicId) {
  const noteEl = document.getElementById("definition-workbench-note");
  if (!noteEl || !state.jobId || !logicId) return;
  const timerKey = `definition:${logicId}`;
  const draft = readDefinitionDraft(logicId);
  noteEl.addEventListener("input", () => {
    debounceAutosave(timerKey, () => writeDefinitionDraft(logicId, noteEl.value));
  });
  const statusEl = document.querySelector("[data-definition-query-status]");
  if (draft?.text != null && String(draft.text).trim()) {
    if (statusEl) statusEl.textContent = "Restored unsaved draft.";
  }
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme === "light" ? "light" : "dark");
}

function initThemeToggle() {
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  let theme = "dark";
  try {
    theme = localStorage.getItem(THEME_STORAGE_KEY) === "light" ? "light" : "dark";
  } catch (_) {
    theme = "dark";
  }
  const sync = (next) => {
    applyTheme(next);
    btn.classList.toggle("is-light", next === "light");
    btn.setAttribute("aria-pressed", next === "light" ? "true" : "false");
    btn.title = next === "light" ? "Switch to dark theme" : "Switch to light theme";
  };
  sync(theme);
  btn.onclick = () => {
    const next = btn.classList.contains("is-light") ? "dark" : "light";
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch (_) {
      /* ignore */
    }
    sync(next);
  };
}

function setTopbarChipState(chipId, { ok = false, warn = false, err = false } = {}) {
  const chip = document.getElementById(chipId);
  if (!chip) return;
  chip.classList.remove("topbar-chip--ok", "topbar-chip--warn", "topbar-chip--err");
  if (ok) chip.classList.add("topbar-chip--ok");
  else if (err) chip.classList.add("topbar-chip--err");
  else if (warn) chip.classList.add("topbar-chip--warn");
}

let state = {
  jobId: null,
  pollTimer: null,
  files: [],
  filters: { issues: "all", candidates: "all" },
  selectedLogicId: null,
  saveTimer: null,
  exportLanguage: "EN",
  workbookFocus: {
    logic: null,
    export: null,
    testcode: null,
  },
  inboxFocus: {},
  logicTreeFocus: { nodeId: null, highlightTerms: [] },
  pathSimAssignments: {},
  pathSimResult: {},
  pathRegenProposal: {},
  diagramFocus: {
    state: null,
    edgeKey: null,
    match: null,
  },
  library: {
    root: "",
    rootExists: false,
    rootInputDraft: "",
    rootError: null,
    focusId: "",
    items: [],
    links: [],
    pickerOpenItemId: null,   // when set: file picker modal targets this item
    pickerCwd: "",
    pickerListing: null,
    pickerLoading: false,
    pickerError: null,
    rootPickerOpen: false,
    rootPickerCwd: "",
    rootPickerListing: null,
    rootPickerLoading: false,
    rootPickerError: null,
    addRowMode: false,        // toggles inline "+ Add relationship" form
    addRowDraft: "",
    busy: false,
    error: null,
  },
  serviceStatusTimer: null,
  currentPageId: "review",
  routingBoot: false,
  copilot: {
    status: null,
    loginCommandId: null,
    loginCommand: null,
    loginPollTimer: null,
    verifyCommand: null,
    assistCommandId: null,
    assistCommand: null,
    assistPollTimer: null,
  },
  appConfig: {
    features: { validator: false, add_clone_tc: false },
    export: { strict: false },
  },
  currentUser: null,
  teamAuthEnabled: false,
  bundleVersion: null,
  testCode: {
    workspace: null,
    loading: false,
    error: null,
    selectedCandidateId: null,
    selectedLogicId: null,
    draft: null,
    copilotDraft: null,
    baselineDraft: null,
    variableMapDraft: {},
    harnessDraft: {},
    codeStyleSamples: [],
    userRequest: "",
    referenceTestName: "",
    batchResults: null,
    batchRunning: false,
    draftCache: {},
    status: "",
    syncStatus: null,
    showStaleOnly: false,
    progressFilter: "all",
    caseFilter: "all",
    copilotWebFollowUp: false,
    samplePasteDraft: "",
    apiGenStatus: "idle",
    dirtyMap: {},
    stashedEdits: {},
    savedSnapshot: {},
    generationSource: {},
    errorMap: {},
    mergePreview: null,
  },
  _suppressTestCodeEditorInput: false,
  copilotRowDraft: {},
  guideOpenSection: null,
  m365Tasks: {
    byId: {},
    activeIds: [],
    pollTimer: null,
  },
};

const $ = (sel) => document.querySelector(sel);
const content = () => $("#content");

/** Safe event binding — avoids "Cannot set properties of null (setting 'onchange')". */
function bindOnChange(sel, fn) {
  const el = typeof sel === "string" ? $(sel) : sel;
  if (el) el.onchange = fn;
}

function bindOnInput(sel, fn) {
  const el = typeof sel === "string" ? $(sel) : sel;
  if (el) el.oninput = fn;
}

function bindClick(sel, fn) {
  const el = typeof sel === "string" ? $(sel) : sel;
  if (el) el.onclick = fn;
}

function setJobId(id) {
  state.jobId = id;
  const el = $("#job-id");
  if (el) el.textContent = id ? id.slice(-16) : "—";
  try {
    if (id) sessionStorage.setItem("alex.currentJobId", id);
    else sessionStorage.removeItem("alex.currentJobId");
  } catch (_) {
    /* private mode */
  }
  if (state.currentPageId && !state.routingBoot) {
    syncUrlForPage(state.currentPageId, { replace: true });
  }
}

function pageSlug(pageId) {
  return PAGE_ROUTES[pageId]?.slug || "review";
}

function pageFromPath(pathname) {
  const slug = String(pathname || "")
    .replace(/^\/+|\/+$/g, "")
    .toLowerCase();
  if (!slug || slug === "index.html") return "review";
  return SLUG_TO_PAGE[slug] || "review";
}

function buildAppUrl(pageId, { jobId } = {}) {
  const slug = pageSlug(pageId);
  const path = `/${slug}`;
  const params = new URLSearchParams();
  const job = jobId !== undefined ? jobId : state.jobId;
  if (job) params.set("job", job);
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

function syncUrlForPage(pageId, { replace = false } = {}) {
  const next = buildAppUrl(pageId);
  const current = `${window.location.pathname}${window.location.search}`;
  if (next === current) return;
  const historyState = { pageId, jobId: state.jobId || null };
  if (replace) history.replaceState(historyState, "", next);
  else history.pushState(historyState, "", next);
}

function updatePageChrome(pageId) {
  const meta = PAGE_ROUTES[pageId] || PAGE_ROUTES.review;
  document.title = `ALEX — ${meta.title}`;
  const stepEl = $("#topbar-page-step");
  const titleEl = $("#topbar-page-title");
  const page = PAGES.find((p) => p.id === pageId);
  if (stepEl) stepEl.textContent = page ? `Step ${page.step}` : "";
  if (titleEl) titleEl.textContent = meta.title;
}

function initRouting() {
  window.addEventListener("popstate", (ev) => {
    const pageId = ev.state?.pageId || pageFromPath(window.location.pathname);
    if (ev.state?.jobId) setJobId(ev.state.jobId);
    showPage(pageId, { skipHistory: true });
  });
}

function readJobIdFromUrl() {
  try {
    return new URLSearchParams(window.location.search).get("job");
  } catch (_) {
    return null;
  }
}

function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const method = (opts.method || "GET").toUpperCase();
  if (state.bundleVersion != null && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    headers["If-Match"] = String(state.bundleVersion);
  }
  return fetch(path, { ...opts, headers, credentials: "same-origin" }).then(async (r) => {
    if (r.status === 401) {
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
      throw new Error("Not authenticated");
    }
    if (r.status === 409) {
      let detail = "Someone else saved — refresh the page and try again.";
      try {
        const j = await r.json();
        detail = j.detail || detail;
      } catch (_) {
        /* ignore */
      }
      throw new Error(detail);
    }
    if (!r.ok) {
      let detail = r.statusText;
      try {
        const j = await r.json();
        detail = j.detail || j.message || JSON.stringify(j);
      } catch (_) {
        try {
          detail = await r.text();
        } catch (_e) {
          /* ignore */
        }
      }
      throw new Error(detail || `HTTP ${r.status}`);
    }
    const ct = r.headers.get("content-type") || "";
    if (ct.includes("json")) {
      const data = await r.json();
      if (data?.bundle_version != null) noteBundleVersion(data.bundle_version);
      if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
        invalidateApiCache();
      }
      return data;
    }
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      invalidateApiCache();
    }
    return r;
  });
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function formatSourceReadable(src) {
  if (src == null || src === "") return "";
  if (typeof src === "string") return src.trim();
  if (typeof src !== "object") return String(src);
  const file = src.file ? basename(src.file) : "";
  const loc = [];
  if (src.sheet) loc.push(src.sheet);
  if (src.section) loc.push(src.section);
  if (src.table || src.table_id) loc.push(src.table || src.table_id);
  if (src.row != null) loc.push(`row ${src.row}`);
  if (src.paragraph != null) loc.push(`¶${src.paragraph}`);
  if (src.page != null) loc.push(`page ${src.page}`);
  if (src.kind) loc.push(src.kind);
  if (file && loc.length) return `${file} — ${loc.join(" · ")}`;
  if (file) return file;
  if (loc.length) return loc.join(" · ");
  const compact = compactSourceLabel(src);
  if (compact) return compact;
  const summary = src.summary || src.control || src.document;
  if (summary) return String(summary);
  return "source";
}

function compactSourceLabel(src) {
  if (!src) return "";
  if (typeof src === "string") return src.length > 42 ? `${src.slice(0, 39)}…` : src;
  if (typeof src !== "object") return String(src);
  const file = src.file ? basename(src.file) : "";
  const where = [];
  if (src.sheet) where.push(src.sheet);
  if (src.section) where.push(src.section);
  if (src.row != null) where.push(`r${src.row}`);
  if (src.paragraph != null) where.push(`¶${src.paragraph}`);
  if (src.page != null) where.push(`p${src.page}`);
  if (file && where.length) return `${file} › ${where.join(" · ")}`;
  return file || where.join(" · ") || formatSourceReadable(src);
}

function renderMetaStats(items, { compact = false } = {}) {
  const cls = compact ? "alex-meta-stats is-compact" : "alex-meta-stats";
  return `<dl class="${cls}">${items
    .map(
      ([label, value]) =>
        `<div><dt>${esc(label)}</dt><dd>${esc(String(value ?? "—"))}</dd></div>`
    )
    .join("")}</dl>`;
}

function logicSpecExpression(item) {
  const fromSpec = String(item?.raw_expression || "").trim();
  if (fromSpec) return fromSpec;
  const fromExpr = String(item?.expression || "").trim();
  if (fromExpr) return fromExpr;
  return (item?.table_rows || [])
    .map((r) => String(r.raw_condition || "").trim())
    .filter(Boolean)
    .join("\n");
}

function renderMetricCards(items) {
  return `<div class="metric-cards">${items
    .map(([label, value, tone]) => {
      const toneClass = tone ? ` metric-card--${tone}` : "";
      return `<article class="metric-card${toneClass}">
        <span class="metric-card__label">${esc(label)}</span>
        <span class="metric-card__value">${esc(String(value ?? "—"))}</span>
      </article>`;
    })
    .join("")}</div>`;
}

function renderSourceCardFromObject(src) {
  if (!src) return "";
  if (typeof src === "string") {
    return `<article class="alex-source-card"><p class="alex-source-card__file">${esc(src)}</p></article>`;
  }
  const file = src.file ? basename(src.file) : "";
  const meta = [];
  if (src.sheet) meta.push(`Sheet: ${src.sheet}`);
  if (src.section) meta.push(src.section);
  if (src.table || src.table_id) meta.push(src.table || src.table_id);
  if (src.row != null) meta.push(`Row ${src.row}`);
  if (src.paragraph != null) meta.push(`¶${src.paragraph}`);
  if (src.page != null) meta.push(`Page ${src.page}`);
  if (src.kind) meta.push(src.kind);
  const title = file || src.summary || (meta[0] || "Source");
  const sub = file ? meta.join(" · ") : meta.slice(title === meta[0] ? 1 : 0).join(" · ");
  return `<article class="alex-source-card">
    <p class="alex-source-card__file">${esc(title)}</p>
    ${sub ? `<p class="alex-source-card__loc">${esc(sub)}</p>` : ""}
  </article>`;
}

function renderSourceCards(sources) {
  if (!sources?.length) return `<p class="detail">No source references.</p>`;
  return `<div class="alex-evidence-stack">${sources
    .map((s) => renderSourceCardFromObject(s))
    .join("")}</div>`;
}

function renderVisualSourcePreview(visualSource, tableRows = [], highlightTerms = [], highlightRowNos = []) {
  const rows = (visualSource?.rows || []).filter((row) => (row.cells || []).some((cell) => String(cell || "").trim()));
  if (!rows.length && !tableRows.length) {
    return `<p class="detail">No source table snapshot available yet.</p>`;
  }
  const source = visualSource?.source || {};
  const title = visualSource?.title || source.control || "Source table";
  const loc = compactSourceLabel(source) || formatSourceReadable(source);
  const terms = (highlightTerms || []).map((t) => String(t || "").toUpperCase()).filter(Boolean);
  const rowNoSet = new Set((highlightRowNos || []).map((n) => String(n)));
  const bodyRows = rows.length
    ? rows
    : tableRows.map((row) => ({ row_no: row[0], cells: [row[1]] }));
  const branchGroupCounts = {};
  bodyRows.forEach((row) => {
    const key = String(row.branch_group || "").trim();
    if (key) branchGroupCounts[key] = (branchGroupCounts[key] || 0) + 1;
  });
  const mergedGroups = Object.keys(branchGroupCounts).filter((k) => branchGroupCounts[k] > 1);
  const branchStripe = (group) => {
    const key = String(group || "").trim();
    if (!key || branchGroupCounts[key] < 2) return "";
    return "var(--merge-stripe)";
  };
  const rowMatches = (row) => {
    const rowNo = String(row.row_no ?? "");
    if (rowNoSet.size && rowNoSet.has(rowNo)) return true;
    if (!terms.length) return false;
    const text = [(row.cells || []).join(" "), row.row_no].join(" ").toUpperCase();
    return terms.some((term) => text.includes(term));
  };
  return `<div class="alex-source-preview">
    <div class="alex-source-preview__head">
      <b>${esc(title)}</b>
      ${loc ? `<span class="detail">${esc(loc)}</span>` : ""}
      ${mergedGroups.length ? `<span class="detail alex-source-preview__legend">Grey bar = rows sharing a merged Word cell (same OR branch)</span>` : ""}
    </div>
    <div class="grid-wrap alex-source-preview__grid">
      <table class="data-grid alex-table alex-source-preview__table" id="logic-source-table">
        <tbody>${bodyRows
          .map((row) => {
            const cells = row.cells || [];
            const hl = rowMatches(row) ? " logic-source-row--highlight" : "";
            const stripe = branchStripe(row.branch_group || "");
            const focus =
              rowNoSet.has(String(row.row_no ?? "")) && state.logicTreeFocus?.nodeId ? " is-tree-focus" : "";
            const branchAttr = row.branch_group ? ` data-branch-group="${esc(row.branch_group)}"` : "";
            const branchStyle = stripe ? ` style="--branch-stripe:${stripe}"` : "";
            return `<tr class="logic-source-row${hl}${focus}" data-source-row="${esc(row.row_no ?? "")}"${branchAttr}${branchStyle}${
              row.branch_group ? ` title="merge group: ${esc(row.branch_group)}"` : ""
            }>
              <th class="col-no">${esc(row.row_no ?? "")}</th>
              ${cells.map((cell) => `<td>${esc(cell)}</td>`).join("")}
            </tr>`;
          })
          .join("")}</tbody>
      </table>
    </div>
  </div>`;
}

function syncLogicTreeSourceFocus(treeNodes = []) {
  const focus = state.logicTreeFocus || {};
  const terms = (focus.highlightTerms || []).map((t) => String(t).toUpperCase()).filter(Boolean);
  const rowNos = new Set((focus.highlightRowNos || []).map(String));
  const root = content();
  if (!root) return;
  root.querySelectorAll(".logic-tree-node").forEach((el) => {
    el.classList.toggle("is-focus", el.getAttribute("data-tree-node") === focus.nodeId);
  });
  root.querySelectorAll(".logic-source-row").forEach((row) => {
    const rowNo = String(row.dataset.sourceRow || "");
    const text = row.textContent.toUpperCase();
    const termMatch = terms.length > 0 && terms.some((t) => text.includes(t));
    const rowMatch = rowNos.has(rowNo);
    row.classList.toggle("logic-source-row--highlight", termMatch || rowMatch);
    row.classList.toggle("is-tree-focus", rowMatch);
  });
  if (focus.scrollSourceRow && rowNos.size) {
    const target = root.querySelector(`.logic-source-row[data-source-row="${CSS.escape(String([...rowNos][0]))}"]`);
    target?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    state.logicTreeFocus = { ...focus, scrollSourceRow: false };
  }
}

function bindLogicTreeSourceNavigation(item) {
  const treeNodes = item?.tree_nodes || [];
  const nodeById = Object.fromEntries(treeNodes.map((n) => [n.node_id, n]));
  const nodeByRow = Object.fromEntries(
    treeNodes.filter((n) => n.source_row != null).map((n) => [String(n.source_row), n])
  );

  content().querySelectorAll(".logic-tree-node").forEach((btn) => {
    btn.querySelector(".logic-tree-node__btn")?.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const nodeId = btn.getAttribute("data-tree-node") || "";
      const node = nodeById[nodeId];
      const label = btn.getAttribute("data-tree-label") || "";
      const terms = label.match(/[A-Z][A-Z0-9_]+/g) || [];
      const highlightRowNos = node?.source_row != null ? [node.source_row] : [];
      state.logicTreeFocus = {
        nodeId,
        highlightTerms: terms,
        highlightRowNos,
        scrollSourceRow: highlightRowNos.length > 0,
      };
      syncLogicTreeSourceFocus(treeNodes);
    });
  });

  content().querySelectorAll(".logic-source-row").forEach((row) => {
    row.addEventListener("click", () => {
      const rowNo = String(row.dataset.sourceRow || "");
      const node = nodeByRow[rowNo];
      const terms = node ? (logicNodeLabel(node).match(/[A-Z][A-Z0-9_]+/g) || []) : [];
      state.logicTreeFocus = {
        nodeId: node?.node_id || null,
        highlightTerms: terms,
        highlightRowNos: rowNo ? [rowNo] : [],
        scrollSourceRow: false,
      };
      syncLogicTreeSourceFocus(treeNodes);
    });
  });
}

async function copyTextToClipboard(text) {
  const value = String(text || "");
  if (!value) return false;
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch (_) {
    const ta = document.createElement("textarea");
    ta.value = value;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      return true;
    } catch (_e) {
      return false;
    } finally {
      ta.remove();
    }
  }
}

function applyM365ExpiredBanner(st) {
  const banner = document.getElementById("m365-expired-banner");
  const textEl = document.getElementById("m365-expired-banner-text");
  if (!banner) return;
  const show = !!(st?.session_refresh_failed || (st?.session_expired && st?.client_id_configured));
  if (!show) {
    banner.hidden = true;
    return;
  }
  banner.hidden = false;
  if (textEl) {
    textEl.textContent = st?.session_refresh_failed
      ? "Microsoft 365 session expired — sign in again to use M365 Copilot in-app."
      : "Microsoft 365 sign-in required for in-app Copilot.";
  }
}


function attrTitle(text) {
  return esc(String(text ?? "")).replace(/\n/g, "&#10;");
}

function tryParsePythonDict(line) {
  const raw = String(line || "").trim();
  if (!raw.startsWith("{")) return null;
  try {
    return JSON.parse(raw.replace(/'/g, '"'));
  } catch {
    return null;
  }
}

function legacyEvidenceLabel(kind, body) {
  const text = String(body || "").trim();
  if (kind === "logic") {
    const name = text.split("->")[0].trim();
    return name.length > 36 ? `${name.slice(0, 33)}…` : name;
  }
  if (kind === "transition" || kind === "diagram") {
    const arrow = text.match(/(.+?)\s*->\s*([^\[]+)/);
    if (arrow) {
      const from = arrow[1].trim().split(/\s+/).pop() || "?";
      const to = arrow[2].trim().split(/\s+/)[0] || "?";
      return `${from} → ${to}`;
    }
  }
  if (kind === "output") {
    const m = text.match(/^(\S+)\s+(\S+)\s*=\s*(.+)$/);
    if (m) return `${m[1]} · ${m[2]}`;
  }
  return text.length > 40 ? `${text.slice(0, 37)}…` : text;
}

function parseLegacyEvidenceString(text) {
  const raw = String(text || "").trim();
  if (!raw) return [];
  const items = [];
  let current = null;
  const chunks = raw.split(/\s*;\s*(?=\{'|[a-z]+:)/i);
  for (const chunk of chunks) {
    const lines = chunk
      .split(/\n+/)
      .map((line) => line.trim())
      .filter(Boolean);
    for (const line of lines) {
      const srcMatch = line.match(/^(?:source|evidence):\s*(.+)$/i);
      if (srcMatch && current) {
        current.detail = `${current.detail || current.label}\n${srcMatch[1].trim()}`;
        continue;
      }
      if (line.startsWith("{")) {
        const obj = tryParsePythonDict(line);
        const detail = formatSourceReadable(obj || line) || line;
        const label = detail.length > 44 ? `${detail.slice(0, 41)}…` : detail;
        current = { kind: "source", label, detail };
        items.push(current);
        continue;
      }
      const typed = line.match(/^(logic|transition|diagram|output):\s*(.+)$/i);
      if (typed) {
        const kind = typed[1].toLowerCase();
        const body = typed[2].trim();
        current = {
          kind,
          label: legacyEvidenceLabel(kind, body),
          detail: `${typed[1]}: ${body}`,
        };
        items.push(current);
        continue;
      }
      const label = line.length > 44 ? `${line.slice(0, 41)}…` : line;
      current = { kind: "note", label, detail: line };
      items.push(current);
    }
  }
  return items;
}

function bindingEvidenceItems(binding) {
  if (!binding) return [];
  const items = [];
  (binding.logic_blocks || []).forEach((row) => {
    const name = row.name || row.id || "logic";
    const detail = [row.raw_expression, row.source].filter(Boolean).join("\n");
    items.push({ kind: "logic", label: name, detail: detail || name });
  });
  (binding.transitions || []).forEach((row) => {
    const label = `${row.from_state || "?"} → ${row.to_state || "?"}`;
    const detail = [row.id, row.event, row.raw_condition, row.source].filter(Boolean).join("\n");
    items.push({ kind: "transition", label, detail: detail || label });
  });
  (binding.state_outputs || []).forEach((row) => {
    const label = `${row.state || "?"} · ${row.name || "output"}`.trim();
    const detail = [row.expression, row.source].filter(Boolean).join("\n");
    items.push({ kind: "output", label, detail: detail || label });
  });
  return items;
}

function renderEvidenceNotes(items, { label = "Sources", defaultOpen = false } = {}) {
  if (!items?.length) return "";
  const openAttr = defaultOpen ? " open" : "";
  return `<details class="alex-ev-notes"${openAttr}>
    <summary class="alex-ev-notes__summary">${esc(label)} <span class="alex-ev-notes__count">${items.length}</span></summary>
    <div class="alex-ev-notes__body">${renderEvidenceChips(items)}</div>
  </details>`;
}

function renderEvidenceChips(items) {
  if (!items?.length) return `<span class="detail">—</span>`;
  return `<div class="alex-ev-row">${items
    .map(
      (item) =>
        `<span class="alex-ev-chip alex-ev-chip--${esc(item.kind || "note")}" title="${attrTitle(item.detail || item.label)}">${esc(item.label)}</span>`
    )
    .join("")}</div>`;
}

function renderRowEvidence(row) {
  const fromBinding = bindingEvidenceItems(row?.evidence_binding);
  if (fromBinding.length) return renderEvidenceNotes(fromBinding, { label: "Evidence" });
  const legacy = parseLegacyEvidenceString(row?.source_evidence || "");
  if (legacy.length) return renderEvidenceNotes(legacy, { label: "Evidence" });
  return `<span class="detail">—</span>`;
}

function tagSeverity(s) {
  const cls = s === "error" ? "error" : s === "warning" ? "warning" : s === "ok" ? "high" : "medium";
  return `<span class="tag ${cls}">${esc(s)}</span>`;
}

async function loadCopilotStatus() {
  if (!copilotFeatureEnabled()) {
    state.copilot.status = { installed: false, enabled: false, trust_state: "disabled" };
    return state.copilot.status;
  }
  const st = await api("/api/copilot/status");
  state.copilot.status = st;
  return st;
}

function copilotFeatureEnabled() {
  return !!(state.appConfig?.assist?.copilot_enabled);
}

function copilotStatusBadge(st) {
  if (state.copilot.loginCommand?.status === "running") return `<span class="tag warning">login pending</span>`;
  if (state.copilot.verifyCommand?.status === "running") return `<span class="tag warning">checking…</span>`;
  if (!st?.installed) return `<span class="tag error">not installed</span>`;
  if (st.trust_state === "runtime_verified") return `<span class="tag high">ready</span>`;
  if (st.trust_state === "auth_verified") return `<span class="tag high">auth ok</span>`;
  if (st.trust_state === "login_completed") return `<span class="tag warning">login done</span>`;
  if (st.login_state === "configured") return `<span class="tag warning">configured</span>`;
  return `<span class="tag warning">not connected</span>`;
}

function githubAuthBadge(st) {
  if (state.copilot.loginCommand?.status === "running") {
    return `<span class="auth-badge auth-badge--warn">${icon("warn", "alex-icon--badge")} PENDING</span>`;
  }
  if (state.copilot.verifyCommand?.status === "running") {
    return `<span class="auth-badge auth-badge--warn">${icon("warn", "alex-icon--badge")} CHECKING</span>`;
  }
  if (!st?.installed) {
    return `<span class="auth-badge auth-badge--err">NOT INSTALLED</span>`;
  }
  if (st.trust_state === "runtime_verified" || st.trust_state === "auth_verified") {
    return `<span class="auth-badge auth-badge--ok">${icon("check", "alex-icon--badge")} AUTH OK</span>`;
  }
  if (st.trust_state === "login_completed" || st.login_state === "configured") {
    return `<span class="auth-badge auth-badge--warn">CONFIGURED</span>`;
  }
  return `<span class="auth-badge auth-badge--warn">SIGN IN</span>`;
}

function m365AuthBadge(m) {
  if (!m) return `<span class="auth-badge auth-badge--warn">LOADING</span>`;
  if (m.api_ready || m.connected) {
    if (m.copilot_chat_entitled === false) {
      const label = m.not_entitled_reason === "msa" ? "MSA (NO API)" : "NO LICENSE";
      return `<span class="auth-badge auth-badge--warn" title="${esc(m.entitlement_note || "Copilot Chat API not entitled")}">${label}</span>`;
    }
    if (m.copilot_api_probe_ok === true) {
      return `<span class="auth-badge auth-badge--ok">${icon("check", "alex-icon--badge")} COPILOT OK</span>`;
    }
    if (m.copilot_api_probe_ok === false) {
      return `<span class="auth-badge auth-badge--err" title="${esc(m.copilot_api_probe_error || "Probe failed")}">PROBE FAIL</span>`;
    }
    return `<span class="auth-badge auth-badge--warn">TEST API</span>`;
  }
  if (m.client_id_configured) {
    return `<span class="auth-badge auth-badge--warn">SIGN IN</span>`;
  }
  return `<span class="auth-badge auth-badge--err">NEEDS CLIENT ID</span>`;
}

function renderM365EntitlementBanner(m, { compact = false } = {}) {
  if (!m || m.copilot_chat_entitled !== false || !(m.api_ready || m.connected)) {
    return "";
  }
  const reasonText =
    m.not_entitled_reason === "msa"
      ? "Personal Microsoft account — Microsoft 365 Copilot Chat API is blocked. Use Apply locally, or sign in with a licensed work account on the Review tab."
      : "No Microsoft 365 Copilot license assigned to this work account. Ask IT to add the SKU Microsoft_365_Copilot, or use Apply locally.";
  const guide = m.activation_guide_url || "README.md";
  const cls = compact ? "m365-entitlement-banner m365-entitlement-banner--compact" : "m365-entitlement-banner";
  return `<div class="${cls}" role="status">
    <strong>M365 Copilot API not entitled.</strong>
    <span class="detail"> ${esc(reasonText)}</span>
    <a class="detail" href="${esc(guide)}" target="_blank" rel="noreferrer">Activation guide</a>
  </div>`;
}

function renderM365KnowledgeBanner() {
  if (m365KnowledgeReady()) return "";
  const st = state.m365Status || {};
  if (st.copilot_chat_entitled === false) {
    return renderM365EntitlementBanner(st, { compact: true });
  }
  if ((st.api_ready || st.connected) && st.copilot_api_probe_ok === false) {
    return `<div class="m365-entitlement-banner m365-entitlement-banner--compact" role="status">
      <strong>Copilot API probe failed.</strong>
      <span class="detail"> ${esc(st.copilot_api_probe_error || "Click Test Copilot API on Review tab or contact IT.")}</span>
    </div>`;
  }
  if (m365ApiSignedIn() && st.copilot_api_probe_ok !== true) {
    const extra =
      st.copilot_scopes_granted === false
        ? " Bấm <b>Authorize Copilot API</b> rồi <b>Test Copilot API</b> trên tab Review (AI sign-in)."
        : " Bấm <b>Test Copilot API</b> trên tab Review (AI sign-in) — sign in một lần chưa đủ để bật Generate.";
    return `<div class="m365-entitlement-banner m365-entitlement-banner--compact" role="status">
      <strong>M365 đã sign in — cần xác nhận Copilot API.</strong>
      <span class="detail">${extra}</span>
    </div>`;
  }
  const msg = st.client_id_configured
    ? "Sign in on the Review tab to use Resolve with Copilot. Apply locally works without AI for simple patterns."
    : "Microsoft 365 Copilot must be configured by IT before AI features are available. Use Apply locally for simple patterns.";
  return `<div class="m365-entitlement-banner m365-entitlement-banner--compact" role="status">
    <strong>M365 Copilot sign-in required.</strong>
    <span class="detail"> ${esc(msg)}</span>
  </div>`;
}

function renderBriefReadinessHtml(readiness) {
  if (!readiness) return "";
  const blockers = readiness.blockers || [];
  const warnings = readiness.warnings || [];
  const tc = readiness.test_case_count ?? 0;
  const cls = blockers.length ? "brief-readiness brief-readiness--blocked" : warnings.length ? "brief-readiness brief-readiness--warn" : "brief-readiness brief-readiness--ok";
  const title = blockers.length
    ? "Brief chưa sẵn sàng — sửa blocker trước khi hỏi Copilot"
    : warnings.length
      ? "Brief sẵn sàng (có cảnh báo)"
      : "Brief sẵn sàng";
  const stats = `<span class="brief-readiness__stats">${tc} test case(s) · parse <code>${esc(readiness.parse_status || "—")}</code>${
    readiness.compliance_fail_count != null
      ? ` · compliance fail ${readiness.compliance_fail_count}/${readiness.compliance_total || tc}`
      : ""
  }</span>`;
  const blockerHtml = blockers.length
    ? `<ul class="brief-readiness__list brief-readiness__list--err">${blockers.map((b) => `<li>${esc(b)}</li>`).join("")}</ul>`
    : "";
  const warnHtml = warnings.length
    ? `<ul class="brief-readiness__list brief-readiness__list--warn">${warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>`
    : "";
  return `<div class="${cls}" data-brief-readiness>${stats}<strong>${esc(title)}</strong>${blockerHtml}${warnHtml}</div>`;
}

function isCopilotPolicyError(text) {
  return /policy settings|access denied by policy|organization has restricted|copilot cli policy/i.test(
    String(text || "")
  );
}

function isCopilotQuotaError(text) {
  return /quota|rate limit|billing|exceeded|usage limit/i.test(String(text || ""));
}

function copilotStatusHtml(st, extraDetail = "") {
  if (!st) {
    return `<p class="detail">Checking Copilot status…</p>`;
  }
  const verify = st.last_verify || {};
  const login = st.last_login || {};
  const staleAuthError =
    st.trust_state === "auth_verified" &&
    verify.ok === false &&
    verify.reason &&
    /GH_TOKEN|GITHUB_TOKEN|`gh`/i.test(verify.reason);
  const connectionDetail = staleAuthError
    ? st.trust_reason || "Logged in via Copilot CLI"
    : verify.ok === false && verify.error_kind === "policy"
      ? "login OK · policy blocked test prompt"
      : verify.checked_at
        ? `${verify.checked_at}${verify.ok ? " · OK" : verify.error_kind === "policy" ? " · policy blocked" : ""}`
        : "not run";
  const policyHint =
    verify.error_kind === "policy" || isCopilotPolicyError(verify.reason)
      ? `<div class="copilot-policy-hint">
          <p><b>Copilot policy</b> — ${esc(verify.reason || "CLI prompts are blocked by GitHub policy.")}</p>
          <p class="detail">This is not a login failure. Review <a href="https://github.com/settings/copilot" target="_blank" rel="noreferrer">GitHub Copilot settings</a> or contact your organization admin.</p>
        </div>`
      : "";
  const quotaHint =
    (verify.error_kind === "quota" || isCopilotQuotaError(verify.reason)) && verify.error_kind !== "policy"
      ? `<p class="detail" style="color:var(--status-error)">Copilot quota/billing: ${esc(verify.reason)}</p>`
      : "";
  return `
    <p><b>Copilot CLI</b> ${copilotStatusBadge(st)}</p>
    <p class="detail">${esc(st.trust_reason || "unknown")}</p>
    <p class="detail">Login: ${login.completed_at ? esc(login.completed_at) : "not run"}${login.reason ? ` · ${esc(login.reason)}` : ""}</p>
    <p class="detail">Connection: ${esc(connectionDetail)}</p>
    ${verify.note ? `<p class="copilot-hint">${esc(verify.note)}</p>` : ""}
    ${policyHint}
    ${quotaHint}
    ${!st.installed ? `<p class="detail">Install: <code>${esc(st.install_hint || "npm install -g @github/copilot")}</code></p>` : ""}
    <p class="copilot-hint">Login once (device flow). <b>Check connection</b> does not use quota. <b>Test prompt</b> sends one real request — policy or quota errors come from GitHub, not ALEX.</p>
    ${extraDetail ? `<p class="detail">${extraDetail}</p>` : ""}
  `;
}

function currentCopilotLoginHtml() {
  const cmd = state.copilot.loginCommand;
  if (!cmd || cmd.status === "completed") return "";
  const code = cmd.one_time_code
    ? `<div class="device-code">${esc(cmd.one_time_code)}</div>`
    : `<div class="device-code muted">waiting for code…</div>`;
  const url = cmd.verify_url || "https://github.com/login/device";
  const logs = (cmd.log || []).join("\n");
  return `
    <div class="copilot-login-box">
      <p><b>Device Login</b> ${tagSeverity(cmd.status === "failed" ? "error" : cmd.status === "completed" ? "ok" : "warning")}</p>
      <p class="detail">Open <a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(url)}</a> and paste this one-time code:</p>
      ${code}
      ${cmd.error_message ? `<p class="detail" style="color:var(--red)">${esc(cmd.error_message)}</p>` : ""}
      <pre class="tree-view copilot-login-log">${esc(logs || "Waiting for terminal output…")}</pre>
    </div>
  `;
}

function currentCopilotVerifyHtml() {
  const cmd = state.copilot.verifyCommand;
  if (!cmd || cmd.status === "completed" || cmd.silent) return "";
  if (cmd.status === "failed" && state.copilot.status?.trust_state === "auth_verified" && !cmd.deep) {
    return "";
  }
  const isPolicy = cmd.error_kind === "policy" || isCopilotPolicyError(cmd.error_message);
  const boxClass = isPolicy ? "copilot-verify-box copilot-policy-hint" : "copilot-verify-box";
  const title =
    cmd.status === "failed"
      ? isPolicy
        ? "Copilot policy blocked test prompt"
        : cmd.deep
          ? "Test prompt failed"
          : "Connection check failed"
      : cmd.deep
        ? "Sending test prompt…"
        : "Checking connection…";
  return `<div class="${boxClass}">
    <p><b>${title}</b></p>
    ${cmd.error_message ? `<p class="detail">${esc(cmd.error_message)}</p>` : ""}
    ${isPolicy ? `<p class="detail"><a href="https://github.com/settings/copilot" target="_blank" rel="noreferrer">Open GitHub Copilot settings</a></p>` : ""}
    ${cmd.detail ? `<details class="copilot-error-detail"><summary>Technical details</summary><pre class="tree-view copilot-login-log">${esc(cmd.detail)}</pre></details>` : ""}
    ${cmd.log?.length ? `<pre class="tree-view copilot-login-log">${esc(cmd.log.join("\n"))}</pre>` : ""}
  </div>`;
}

function refreshCopilotLoginContainers() {
  document.querySelectorAll("[data-copilot-login]").forEach((el) => {
    el.innerHTML = currentCopilotLoginHtml() + currentCopilotVerifyHtml();
  });
}

function currentAssistHtml() {
  const cmd = state.copilot.assistCommand;
  if (!cmd) return "<p class='detail'>No active Copilot draft.</p>";
  const title = cmd.current_logic_id
    ? `Drafting ${cmd.current_logic_id} (${(cmd.progress_current || 0) + (cmd.status === "running" ? 1 : 0)}/${cmd.progress_total || 0})`
    : cmd.status === "completed"
      ? "Copilot draft completed."
      : "Copilot draft running…";
  return `<div class="copilot-stream-box">
    <p><b>${esc(title)}</b> ${cmd.status === "running" ? '<span class="spinner" aria-hidden="true"></span>' : ""} ${tagSeverity(cmd.status === "failed" ? "error" : cmd.status === "completed" ? "ok" : "warning")}</p>
    ${cmd.error_message ? `<p class="detail" style="color:var(--red)">${esc(cmd.error_message)}</p>` : ""}
    <pre class="tree-view copilot-stream-log">${esc((cmd.log || []).join("\n") || "Waiting for Copilot output…")}</pre>
  </div>`;
}

function refreshAssistContainers() {
  document.querySelectorAll("[data-copilot-assist]").forEach((el) => {
    el.innerHTML = currentAssistHtml();
  });
}

async function startCopilotLogin(onDone) {
  state.copilot.loginCommand = {
    status: "running",
    one_time_code: "",
    verify_url: "https://github.com/login/device",
    log: ["Starting Copilot login…"],
  };
  refreshCopilotLoginContainers();
  try {
    const res = await api("/api/copilot/login", { method: "POST" });
    state.copilot.loginCommandId = res.command_id;
    state.copilot.loginCommand = res;
    refreshCopilotLoginContainers();
    await pollCopilotLogin(res.command_id, onDone);
  } catch (e) {
    state.copilot.loginCommand = {
      status: "failed",
      error_message: e.message,
      log: [e.message],
    };
    refreshCopilotLoginContainers();
  }
}

async function pollCopilotLogin(commandId, onDone) {
  if (state.copilot.loginPollTimer) clearInterval(state.copilot.loginPollTimer);
  state.copilot.loginPollTimer = setInterval(async () => {
    try {
      const st = await api(`/api/copilot/commands/${encodeURIComponent(commandId)}`);
      state.copilot.loginCommand = st;
      refreshCopilotLoginContainers();
      if (st.status === "completed" || st.status === "failed") {
        clearInterval(state.copilot.loginPollTimer);
        state.copilot.loginPollTimer = null;
        await loadCopilotStatus().catch(() => null);
        if (st.status === "completed") {
          await verifyCopilot(null, { deep: false, silent: true });
        }
        if (onDone) onDone(st);
      }
    } catch (e) {
      clearInterval(state.copilot.loginPollTimer);
      state.copilot.loginPollTimer = null;
      state.copilot.loginCommand = {
        status: "failed",
        error_message: e.message,
        log: [e.message],
      };
      refreshCopilotLoginContainers();
    }
  }, 1200);
}

async function verifyCopilot(onDone, { deep = false, silent = false } = {}) {
  if (!silent) {
    state.copilot.verifyCommand = {
      status: "running",
      deep,
      silent: false,
      log: [deep ? "Sending one test prompt to Copilot…" : "Checking Copilot login (no quota)…"],
    };
    refreshCopilotLoginContainers();
  }
  try {
    const res = await api(`/api/copilot/verify?deep=${deep ? "true" : "false"}`, { method: "POST" });
    await loadCopilotStatus().catch(() => null);
    if (silent && res.ok) {
      state.copilot.verifyCommand = null;
    } else if (res.ok) {
      state.copilot.verifyCommand = silent
        ? null
        : {
            status: "completed",
            deep,
            silent: false,
            log: [deep ? "Test prompt succeeded." : "Connection OK."],
          };
    } else {
      const hideFailure =
        !deep && !silent && state.copilot.status?.trust_state === "auth_verified";
      state.copilot.verifyCommand = hideFailure
        ? null
        : {
            status: "failed",
            deep,
            silent: false,
            error_kind: res.error_kind,
            error_message: res.reason || "unknown",
            detail: res.detail,
            log: [],
          };
    }
    refreshCopilotLoginContainers();
    if (onDone) onDone(res);
  } catch (e) {
    if (!silent) {
      state.copilot.verifyCommand = {
        status: "failed",
        deep,
        silent: false,
        error_message: e.message,
        log: [],
      };
      refreshCopilotLoginContainers();
    }
  }
}

async function startCopilotAssist(payload, onDone) {
  state.copilot.assistCommand = {
    status: "running",
    log: ["Preparing Copilot draft…"],
    progress_current: 0,
    progress_total: payload.mode === "all" ? 0 : 1,
  };
  refreshAssistContainers();
  try {
    const res = await api(`/api/copilot/assist?job_id=${encodeURIComponent(state.jobId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.copilot.assistCommandId = res.command_id;
    state.copilot.assistCommand = res;
    refreshAssistContainers();
    await pollCopilotAssist(res.command_id, onDone);
  } catch (e) {
    state.copilot.assistCommand = {
      status: "failed",
      error_message: e.message,
      log: [e.message],
    };
    refreshAssistContainers();
  }
}

async function pollCopilotAssist(commandId, onDone) {
  if (state.copilot.assistPollTimer) clearInterval(state.copilot.assistPollTimer);
  state.copilot.assistPollTimer = setInterval(async () => {
    try {
      const st = await api(`/api/copilot/commands/${encodeURIComponent(commandId)}`);
      state.copilot.assistCommand = st;
      refreshAssistContainers();
      if (st.status === "completed" || st.status === "failed") {
        clearInterval(state.copilot.assistPollTimer);
        state.copilot.assistPollTimer = null;
        if (onDone) onDone(st);
      }
    } catch (e) {
      clearInterval(state.copilot.assistPollTimer);
      state.copilot.assistPollTimer = null;
      state.copilot.assistCommand = {
        status: "failed",
        error_message: e.message,
        log: [e.message],
      };
      refreshAssistContainers();
    }
  }, 1200);
}

const M365_TASK_STORAGE_PREFIX = "alex.m365Tasks.";

function m365TaskStorageKey(jobId) {
  return `${M365_TASK_STORAGE_PREFIX}${jobId || ""}`;
}

function persistM365TaskIds(jobId, ids) {
  try {
    sessionStorage.setItem(m365TaskStorageKey(jobId), JSON.stringify(ids));
  } catch (_) {
    /* private mode */
  }
}

function readM365TaskIds(jobId) {
  try {
    const raw = sessionStorage.getItem(m365TaskStorageKey(jobId));
    return raw ? JSON.parse(raw) : [];
  } catch (_) {
    return [];
  }
}

function m365TaskLabel(task) {
  return task?.label || task?.kind || "Copilot";
}

function hasRunningM365TaskForPage(pageId) {
  return Object.values(state.m365Tasks.byId || {}).some(
    (t) => t.status === "running" && (t.target_page === pageId || !t.target_page)
  );
}

function m365TaskErrorDetail(t) {
  const r = t.result || {};
  const fromTask = String(t.error || "").trim();
  if (fromTask && fromTask !== "Task failed") return fromTask;
  const fromResult = String(r.error || "").trim();
  if (fromResult) return fromResult;
  const flags = r.validation?.flags || [];
  if (flags.length) return `Validation: ${flags.join(", ")}`;
  const raw = String(r.raw_preview || "").trim();
  if (raw) return `Copilot reply: ${raw.slice(0, 160)}${raw.length > 160 ? "…" : ""}`;
  return fromTask || "Task failed — thử Copilot web hoặc xem log.";
}

function refreshM365TaskBanner() {
  const host = document.getElementById("m365-task-banner");
  if (!host) return;
  const tasks = Object.values(state.m365Tasks.byId || {});
  const running = tasks.filter((t) => t.status === "running");
  const done = tasks.filter((t) => t.status === "completed" && !t._seen);
  const failed = tasks.filter((t) => (t.status === "failed" || t.status === "cancelled") && !t._seen);

  if (!running.length && !done.length && !failed.length) {
    host.hidden = true;
    host.innerHTML = "";
    return;
  }

  host.hidden = false;
  const lines = [];
  running.forEach((t) => {
    const prog = t.progress || {};
    const progTxt = prog.total ? ` (${prog.current || 0}/${prog.total})` : "";
    const elapsed = t.elapsed_s || 0;
    const codeTask = String(t.kind || "").startsWith("code_");
    const slowHint =
      codeTask && elapsed >= 15
        ? `<span class="detail">API chậm (${elapsed}s) — <button type="button" class="btn secondary btn-inline" data-m365-copy-prompt>Hủy &amp; dùng Copilot web</button></span>`
        : `<span class="detail">Bạn có thể chuyển tab</span>`;
    lines.push(
      `<div class="m365-task-banner__row m365-task-banner__row--running">
        <span class="tag warning">Copilot</span>
        <span>${esc(m365TaskLabel(t))}${progTxt} — ${elapsed}s</span>
        ${slowHint}
        <button type="button" class="btn secondary btn-inline" data-m365-cancel="${esc(t.task_id)}">Hủy</button>
      </div>`
    );
  });
  done.forEach((t) => {
    lines.push(
      `<div class="m365-task-banner__row m365-task-banner__row--done">
        <span class="tag high">Xong</span>
        <span>${esc(m365TaskLabel(t))}</span>
        <button type="button" class="btn btn-inline" data-m365-view="${esc(t.task_id)}">Xem kết quả</button>
        <button type="button" class="btn secondary btn-inline" data-m365-dismiss="${esc(t.task_id)}">Đóng</button>
      </div>`
    );
  });
  failed.forEach((t) => {
    const detail = m365TaskErrorDetail(t);
    const cat = t.error_category || t.result?.error_category || "";
    const hasDraft = !!(t.result?.copilot_draft?.full_snippet || t.result?.copilot_draft?.code_body || t.result?.draft?.full_snippet || t.result?.draft?.code_body);
    const viewBtn = hasDraft
      ? `<button type="button" class="btn btn-inline" data-m365-view="${esc(t.task_id)}">Xem draft</button>`
      : "";
    lines.push(
      `<div class="m365-task-banner__row m365-task-banner__row--failed">
        <span class="tag error">Lỗi</span>
        <span>${esc(m365TaskLabel(t))}${cat ? ` [${esc(cat)}]` : ""}: ${esc(detail)}</span>
        ${viewBtn}
        <button type="button" class="btn secondary btn-inline" data-m365-dismiss="${esc(t.task_id)}">Đóng</button>
      </div>`
    );
  });
  host.innerHTML = lines.join("");
  host.querySelectorAll("[data-m365-cancel]").forEach((btn) => {
    btn.onclick = () => cancelM365Task(btn.getAttribute("data-m365-cancel"));
  });
  host.querySelectorAll("[data-m365-copy-prompt]").forEach((btn) => {
    btn.onclick = async () => {
      const runningTask = tasks.find((t) => t.status === "running");
      if (runningTask) await cancelM365Task(runningTask.task_id);
      try {
        await openTestCodeCopilotWeb(state.testCode.rows || []);
      } catch (e) {
        const statusEl = $("#testcode-status");
        if (statusEl) statusEl.textContent = e.message || String(e);
      }
    };
  });
  host.querySelectorAll("[data-m365-view]").forEach((btn) => {
    btn.onclick = () => viewM365TaskResult(btn.getAttribute("data-m365-view"));
  });
  host.querySelectorAll("[data-m365-dismiss]").forEach((btn) => {
    btn.onclick = () => dismissM365Task(btn.getAttribute("data-m365-dismiss"));
  });
}

function dismissM365Task(taskId) {
  if (state.m365Tasks.byId[taskId]) state.m365Tasks.byId[taskId]._seen = true;
  state.m365Tasks.activeIds = (state.m365Tasks.activeIds || []).filter((id) => id !== taskId);
  persistM365TaskIds(state.jobId, state.m365Tasks.activeIds);
  refreshM365TaskBanner();
}

async function cancelM365Task(taskId) {
  if (!state.jobId || !taskId) return;
  try {
    await api(`/api/review/copilot/m365-tasks/${encodeURIComponent(taskId)}?job_id=${encodeURIComponent(state.jobId)}`, {
      method: "DELETE",
    });
    dismissM365Task(taskId);
  } catch (e) {
    refreshM365TaskBanner();
  }
}

function viewM365TaskResult(taskId) {
  const task = state.m365Tasks.byId[taskId];
  if (!task) return;
  task._seen = true;
  refreshM365TaskBanner();
  const page = task.target_page || (task.kind?.startsWith("code_") ? "test-code" : "logic-review");
  if (page) showPage(page);
  const normalized = normalizeTestCodeTaskResult(task);
  if (normalized.kind === "code_generate" || normalized.kind === "code_refine") {
    applyTestCodeTaskResult(normalized);
  }
  if (task.status === "completed") handleM365TaskComplete(task, { fromView: true });
}

function applyTestCodeTaskResult(task) {
  const tc = state.testCode;
  const result = task.result || {};
  const draft = result.copilot_draft || result.draft || null;
  if (!draft?.full_snippet && !draft?.code_body) return;
  tc.copilotDraft = draft;
  tc.baselineDraft = result.baseline || null;
  const cid = tc.selectedCandidateId;
  if (cid) {
    if (!tc.generationSource) tc.generationSource = {};
    tc.generationSource[cid] = "API";
  }
  const row = (tc.rows || []).find((r) => r.candidate_id === tc.selectedCandidateId);
  const merged = { ...draft, full_snippet: draft.full_snippet || draft.code_body, provider: "m365_copilot" };
  applyTestCodeDraftToUi(merged, row);
  if (cid) {
    if (!tc.stashedEdits) tc.stashedEdits = {};
    tc.stashedEdits[cid] = merged.full_snippet || "";
    if (!tc.dirtyMap) tc.dirtyMap = {};
    tc.dirtyMap[cid] = true;
  }
  const editor = $("#testcode-code-editor");
  if (editor) editor.classList.add("field-copilot-changed");
  const val = result.validation || {};
  const valEl = document.getElementById("testcode-validation");
  if (valEl) {
    valEl.hidden = false;
    valEl.innerHTML = renderTestCodeValidation(val);
  }
  const statusEl = $("#testcode-status");
  if (statusEl) {
    const notes = (val.warnings || []).slice(0, 2).join(", ");
    statusEl.textContent = notes
      ? `API done — review (${notes}) → Validate / Save Code.`
      : "API done — review editor → Validate / Save Code.";
  }
  setTestCodeApiStatus("done");
  patchTestCodeCaseStatusUi();
}

function normalizeTestCodeTaskResult(task) {
  const result = task?.result || {};
  const draft = result.copilot_draft || result.draft;
  if (!draft?.full_snippet && !draft?.code_body) return task;
  return {
    ...task,
    result: { ...result, copilot_draft: draft },
  };
}

async function handleM365TaskComplete(task, { fromView = false } = {}) {
  if (!task || task.status !== "completed") return;
  const kind = task.kind;
  const result = task.result || {};
  const payload = task.payload || result.payload || {};

  if (kind === "code_generate" || kind === "code_refine") {
    applyTestCodeTaskResult(task);
    if (payload.batch_all && state.testCode.rows?.length) {
      const activeRow = state.testCode.rows.find((r) => r.candidate_id === state.testCode.selectedCandidateId);
      const req = payload.user_request || "";
      const runBatchAll = () =>
        startM365Task({
          kind: "code_batch",
          label: `Batch GTest (${state.testCode.rows.length} TC)`,
          targetPage: "test-code",
          payload: {
            candidate_ids: state.testCode.rows
              .filter((r) => r.candidate_id !== state.testCode.selectedCandidateId)
              .map((r) => r.candidate_id),
            engineer_note: req,
            copilot_prompt_override: req,
            persist_drafts: true,
            language: state.exportLanguage || "EN",
            slim: true,
          },
        });
      if (fromView || state.currentPageId === "test-code") {
        showTestCodeApplyAllBanner(state.testCode.rows, activeRow, runBatchAll, {
          allJob: true,
          userRequest: req,
        });
      }
    }
  }

  if (kind === "code_batch") {
    invalidateApiCache(`gtest-ws:${state.jobId}:${state.exportLanguage || "EN"}`);
    state.testCode.workspace = await fetchGtestWorkspace(true);
    const statusEl = $("#testcode-status");
    if (statusEl) {
      statusEl.textContent = `Batch xong: ${result.generated || 0} ok — mở từng TC → Save.`;
    }
  }

  if (kind === "copilot_context_plan" || kind === "copilot_plan") {
    const logicId = task.logic_id || payload.logic_id;
    if (logicId) {
      state.copilotStep[logicId] = "plan";
      invalidateApiCache(`copilot-session:${state.jobId}:${logicId}`);
    }
    if (fromView || state.currentPageId === "logic-review") {
      await renderLogicReview({ skipSummary: true, force: true });
    }
  }

  if (kind === "copilot_write") {
    const logicId = task.logic_id || payload.logic_id;
    if (logicId) {
      state.copilotStep[logicId] = "review";
      invalidateApiCache(`copilot-session:${state.jobId}:${logicId}`);
    }
    if (fromView || state.currentPageId === "logic-review") {
      await renderLogicReview({ skipSummary: true, force: true });
    }
  }

  if (kind === "write_from_row") {
    const scope = payload.scope || "export";
    const cid = task.candidate_id || payload.candidate_id;
    state.copilotRowDraft = state.copilotRowDraft || {};
    state.copilotRowDraft[scope] = {
      candidate_id: cid,
      draft: result.draft || {},
      diffs: result.diffs || [],
    };
    if (fromView || state.currentPageId === "export" || state.currentPageId === "logic-review") {
      if (state.currentPageId === "export") await renderExport({ preserveSelection: true });
      else await renderLogicReview({ skipSummary: true, force: true });
    }
  }
}

async function startM365Task({ kind, payload = {}, label = "", logicId = "", candidateId = "", targetPage = "" }) {
  if (!state.jobId) throw new Error("No active job");
  const res = await api(`/api/review/copilot/m365-tasks?job_id=${encodeURIComponent(state.jobId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      kind,
      payload,
      label,
      logic_id: logicId,
      candidate_id: candidateId,
      target_page: targetPage,
    }),
  });
  if (res.ok === false) throw new Error(res.error || "Could not start Copilot task");
  const taskId = res.task_id;
  state.m365Tasks.byId[taskId] = { ...res, kind, payload, logic_id: logicId, candidate_id: candidateId, target_page: targetPage };
  state.m365Tasks.activeIds = [...new Set([...(state.m365Tasks.activeIds || []), taskId])];
  persistM365TaskIds(state.jobId, state.m365Tasks.activeIds);
  refreshM365TaskBanner();
  pollM365Tasks();
  return res;
}

function pollM365Tasks() {
  if (state.m365Tasks.pollTimer) clearInterval(state.m365Tasks.pollTimer);
  state.m365Tasks.pollTimer = setInterval(async () => {
    const ids = (state.m365Tasks.activeIds || []).filter((id) => {
      const t = state.m365Tasks.byId[id];
      return !t || t.status === "running";
    });
    if (!ids.length) {
      clearInterval(state.m365Tasks.pollTimer);
      state.m365Tasks.pollTimer = null;
      return;
    }
    for (const id of ids) {
      try {
        const st = await api(
          `/api/review/copilot/m365-tasks/${encodeURIComponent(id)}?job_id=${encodeURIComponent(state.jobId)}`
        );
        const prev = state.m365Tasks.byId[id] || {};
        state.m365Tasks.byId[id] = { ...prev, ...st, kind: prev.kind || st.kind, payload: prev.payload || st.payload };
        if (st.status === "completed" || st.status === "failed" || st.status === "cancelled") {
          state.m365Tasks.activeIds = (state.m365Tasks.activeIds || []).filter((x) => x !== id);
          persistM365TaskIds(state.jobId, state.m365Tasks.activeIds);
          if (st.status === "completed") await handleM365TaskComplete(state.m365Tasks.byId[id]);
          else if (st.status === "failed" && (st.kind === "code_generate" || st.kind === "code_refine")) {
            setTestCodeApiStatus("failed", st.error || st.result?.error || "Generation failed");
            const normalized = normalizeTestCodeTaskResult(state.m365Tasks.byId[id]);
            if (normalized.result?.copilot_draft) applyTestCodeTaskResult(normalized);
          }
        }
      } catch (_) {
        /* keep polling */
      }
    }
    refreshM365TaskBanner();
  }, 1500);
}

async function resumeM365Tasks() {
  if (!state.jobId) return;
  const ids = readM365TaskIds(state.jobId);
  if (!ids.length) return;
  state.m365Tasks.activeIds = ids;
  for (const id of ids) {
    try {
      const st = await api(
        `/api/review/copilot/m365-tasks/${encodeURIComponent(id)}?job_id=${encodeURIComponent(state.jobId)}`
      );
      state.m365Tasks.byId[id] = st;
      if (st.status === "completed") await handleM365TaskComplete(st);
    } catch (_) {
      /* task may be gone */
    }
  }
  refreshM365TaskBanner();
  pollM365Tasks();
}

function updateSelectedCount() {
  const n = state.files.filter((f) => f.selected).length;
  const total = state.files.length;
  const el = $("#stat-selected");
  if (el) el.textContent = `${n} / ${total}`;
}

function queueStatusClass(status) {
  if (status === "completed") return "high";
  if (status === "ready_for_ai" || status === "ai_drafted") return "warning";
  if (status === "needs_engineer_answer") return "medium";
  return "error";
}

function queueStatusLabel(status) {
  return {
    ready_for_ai: "Ready for AI",
    blocked_missing_definition: "Blocked — missing defs",
    needs_engineer_answer: "Needs your review",
    ai_drafted: "AI draft ready",
    completed: "Ready",
    no_rows: "No rows yet",
  }[status] || status || "Unknown";
}

function queueShortReason(row = {}) {
  if (row.queue_status === "ready_for_ai") return "Definitions look usable.";
  if (row.queue_status === "blocked_missing_definition") {
    const terms = (row.missing_terms || []).slice(0, 4);
    return terms.length ? `Missing: ${terms.join(", ")}${(row.missing_terms || []).length > 4 ? "…" : ""}` : "Definitions missing.";
  }
  if (row.queue_status === "needs_engineer_answer") {
    return row.has_engineer_note ? "Review AI draft after your note." : "Engineer confirmation needed.";
  }
  if (row.queue_status === "ai_drafted") return "Draft exists. Review final rows.";
  if (row.queue_status === "completed") return "Rows are ready or approved.";
  return "No final rows linked yet.";
}

function reasonCodeLabel(code) {
  return {
    not_found: "Not found",
    normalized_match: "Name looks similar",
    added_file_only: "From added file",
    engineer_note_only: "From engineer note",
    conflicting_definitions: "Conflicting definitions",
    spec_definition_found: "Found in spec",
  }[code] || code || "Review";
}

function renderTermSummaryBrief(counts, total) {
  if (!total) return "";
  if (!counts.missing) return `<p class="detail term-counts">${total} terms · all defined</p>`;
  const bits = [`${counts.missing} need define`];
  if (counts.added) bits.push(`${counts.added} from note`);
  return `<p class="detail term-counts">${total} terms · ${bits.join(", ")}</p>`;
}

function renderCapabilitySummary(_capability) {
  return "";
}

function guideDetails(title, body, { id = "", open = false, step = "" } = {}) {
  const stepHtml = step ? `<span class="alex-guide-details__step">${esc(step)}</span>` : "";
  return `<details class="alex-guide-details card"${id ? ` id="${esc(id)}"` : ""}${open ? " open" : ""}>
    <summary class="alex-guide-details__summary">${stepHtml}<span class="alex-guide-details__title">${esc(title)}</span></summary>
    <div class="alex-guide-details__body">${body}</div>
  </details>`;
}

function renderGuideWorkflow() {
  return guideDetails(
    "Bắt đầu nhanh (5 phút)",
    `<ol class="alex-guide-steps">
      <li><b>Review</b> — chọn file spec → <b>Review specification</b> → đợi job xong.</li>
      <li><b>Logic &amp; Definitions</b> — đối chiếu cây logic với bảng spec, bổ sung definition còn thiếu.</li>
      <li><b>Final File</b> — sửa Before/After, đánh dấu row <b>ready</b> / <b>approved</b>.</li>
      <li><b>Test Code</b> — chọn TC → copy <code>TEST_F</code> (chỉ map tên khi spec ≠ code).</li>
      <li><b>Diagram Graph</b> — chỉ khi spec có state machine / diagram.</li>
    </ol>
    <p class="detail">Bookmark URL: <code>/review</code> · <code>/logic</code> · <code>/export</code> · <code>/test-code?job=…</code></p>`,
    { id: "guide-start", open: true, step: "★" }
  );
}

function renderGuideReviewTab() {
  return guideDetails(
    "Tab 1 — Review (Sources & analyze)",
    `<p class="detail">Chuẩn bị input và chạy phân tích. Phải có job trước khi sang tab khác.</p>
    <ol class="alex-guide-steps">
      <li><b>Upload</b> hoặc <b>Load sample package</b> — tick đúng file cần review.</li>
      <li>Chỉnh <b>Type</b> nếu auto-detect sai (System Spec / Test Spec / Sample Code).</li>
      <li>Đăng nhập M365 Copilot trên Review nếu cần Resolve with Copilot sau này.</li>
      <li><b>Review specification</b> — theo dõi progress bar đến <b>completed</b>.</li>
      <li>Top bar hiện JOB id, Rows Ready/Blocked, Missing Terms.</li>
    </ol>
    <p class="detail"><b>M365:</b> Sign in một lần → mở <code>login.microsoft.com/device</code> → nhập code trên Mac → đợi ALEX poll xong.</p>`,
    { id: "guide-review", step: "1" }
  );
}

function renderGuideLogicTab() {
  return guideDetails(
    "Tab 2 — Logic & Definitions",
    `<p class="detail">Một <b>logic group</b> = một control trong spec. Sửa definition trước, rồi mới tin workbook rows.</p>
    <div class="grid-wrap"><table class="data-grid alex-table alex-guide-table">
      <thead><tr><th>Khu vực</th><th>Cách dùng</th></tr></thead>
      <tbody>
        <tr><td><b>Logic group</b></td><td>Dropdown chọn control. Đổi group → cây + bảng spec cập nhật.</td></tr>
        <tr><td><b>Tree logic</b></td><td>Click node → highlight dòng tương ứng ở <b>Source table</b> bên phải.</td></tr>
        <tr><td><b>Source table</b></td><td>Bảng Word/Excel gốc — nguồn tin cậy nhất khi cây parse lạ.</td></tr>
        <tr><td><b>Path simulator</b></td><td>Nhập giá trị signal → <b>Run what-if</b> xem nhánh nào active (thử nhanh, không thay test case).</td></tr>
        <tr><td><b>Definitions</b></td><td>Term thiếu → ghi engineer note → <b>Resolve with AI</b> → Apply.</td></tr>
        <tr><td><b>Workbook rows</b></td><td>Given/When/Then của TC thuộc logic group — sửa trực tiếp nếu cần.</td></tr>
      </tbody>
    </table></div>
    <p class="detail">Tag <b>parse ok / partial</b> = độ tin cậy parser. Tree phức tạp → ưu tiên đọc source table.</p>`,
    { id: "guide-logic", step: "2" }
  );
}

function renderGuideDiagramTab() {
  return guideDetails(
    "Tab 3 — Diagram Graph",
    `<p class="detail">Chỉ dùng khi spec có state machine hoặc diagram OCR.</p>
    <ol class="alex-guide-steps">
      <li>Chọn <b>state</b> ở trên → lọc transition liên quan.</li>
      <li>Chọn <b>edge</b> → xem condition + evidence bên phải.</li>
      <li><b>Jump to linked logic</b> — nhảy sang Logic tab của control liên kết.</li>
      <li>Arrow purely visual (không có spec text) vẫn cần engineer review.</li>
    </ol>`,
    { id: "guide-diagram", step: "3" }
  );
}

function renderGuideLibraryTab() {
  return guideDetails(
    "Tab 4 — Library",
    `<p class="detail">Quản lý file mẫu và quan hệ traceability tái sử dụng giữa các job.</p>
    <ol class="alex-guide-steps">
      <li>Chọn thư mục <b>Library root</b> (folder trên máy).</li>
      <li>Thêm relationship: file spec ↔ code ↔ test.</li>
      <li>Từ <b>Test Code</b>: <b>Library</b> lưu harness preset (fixture, in/out, evaluate fn).</li>
    </ol>`,
    { id: "guide-library", step: "4" }
  );
}

function renderGuideExportTab() {
  return guideDetails(
    "Tab 5 — Final File",
    `<p class="detail">Workbook cuối — nguồn cho export Excel và sinh Test Code.</p>
    <ol class="alex-guide-steps">
      <li>Chọn test case ở dropdown → sửa <b>Expected input</b> / <b>Expected output</b>.</li>
      <li>Đặt <b>Status</b>: <b>ready</b> hoặc <b>approved</b> khi đã review xong.</li>
      <li><b>Save row</b> sau mỗi lần sửa.</li>
      <li><b>Open in Test Code</b> — nhảy sang tab 6 với TC đang chọn.</li>
      <li>Export Excel EN/JP khi blocked rows đã xử lý hoặc chấp nhận cố ý.</li>
    </ol>
    <p class="detail">Test Code đọc Before/After từ đây — sửa Final File trước khi regenerate code.</p>`,
    { id: "guide-export", step: "5" }
  );
}

function renderGuideTestCodeTab() {
  return guideDetails(
    "Tab 6 — Test Code",
    `<p class="detail">Sinh <code>TEST_F</code> từ Before/After — Copilot bám <b>code mẫu</b> project (fixture, helper, style).</p>
    <ol class="alex-guide-steps">
      <li>Upload <b>Code sample</b> (.cpp) — 1–3 TEST_F mẫu từ project (hoặc upload cùng spec ở Review).</li>
      <li>Chọn <b>Reference test</b> làm anchor style (tuỳ chọn).</li>
      <li>Ghi <b>Engineer note</b> (helper, timing, quy ước assert) trước Generate.</li>
      <li><b>Regenerate</b> = skeleton offline · <b>Generate with Copilot</b> = viết theo I/O + mẫu.</li>
      <li><b>Batch Copilot</b> — sinh hàng loạt TC cùng logic (cần M365).</li>
      <li><b>Library</b> — lưu harness + code samples cho module sau.</li>
    </ol>
    <p class="detail">Approve Expected I/O ở Final File trước — Copilot cần Given/Then rõ.</p>`,
    { id: "guide-testcode", step: "6" }
  );
}

function renderGuideProviders() {
  return guideDetails(
    "Copilot testcase session (4 steps)",
    `<ol class="alex-guide-list">
      <li><b>Build context</b> — ALEX assembles logic, paths, gaps, testcase snapshots, attachments (incl. screenshots).</li>
      <li><b>Generate plan</b> — M365 Copilot proposes update/add/retire with rationale (edit before write).</li>
      <li><b>Write test cases</b> — Copilot fills UseCase, Operation, Expected input/output per style guide + golden samples.</li>
      <li><b>Review &amp; Apply</b> — Full-row diff; no-op rows flagged; Apply selected updates the workbook.</li>
    </ol>
    <p class="detail">Sign in on Review tab. Upload 2–3 style sample rows (JSON) for Copilot to match your company văn phong.</p>`,
    { id: "guide-providers" }
  );
}

function renderGuideReference() {
  return guideDetails(
    "Tham chiếu: status, metrics, xử lý sự cố",
    `<h4>Top bar</h4>
    <ul class="alex-guide-list">
      <li><b>Rows Ready / Blocked</b> — sức khỏe workbook.</li>
      <li><b>Missing Terms</b> — definition còn thiếu trong job.</li>
      <li><b>Logic Groups</b> — số control đã parse.</li>
      <li><b>M365</b> — trạng thái Copilot sign-in.</li>
    </ul>
    <h4>Logic</h4>
    <ul class="alex-guide-list">
      <li><b>parse ok</b> — parser deterministic ổn.</li>
      <li><b>partial</b> — cần review thêm.</li>
      <li>Vạch xám ở source table = các dòng cùng merge cell Word (cùng nhánh OR).</li>
    </ul>
    <h4>Sự cố thường gặp</h4>
    <ul class="alex-guide-list">
      <li><b>Test Code API unavailable</b> — restart server: <code>python run_web.py</code> + hard refresh.</li>
      <li><b>Job not found</b> — chạy lại Review specification.</li>
      <li><b>M365 code expired</b> — Sign in lại, tab device code mới.</li>
      <li><b>UI chậm</b> — data cache vài giây; Save/Apply tự refresh.</li>
    </ul>`,
    { id: "guide-reference" }
  );
}

function renderGuideCard() {
  return `<div class="alex-guide-sections">
    ${renderGuideWorkflow()}
    ${renderGuideReviewTab()}
    ${renderGuideLogicTab()}
    ${renderGuideDiagramTab()}
    ${renderGuideLibraryTab()}
    ${renderGuideExportTab()}
    ${renderGuideTestCodeTab()}
    ${renderGuideProviders()}
    ${renderGuideReference()}
  </div>`;
}

function openGuideSection(anchorId) {
  state.guideOpenSection = anchorId || null;
  showPage("guide");
}

function bindTabHelpLinks(root = content()) {
  root?.querySelectorAll("[data-goto-page]").forEach((link) => {
    link.onclick = (ev) => {
      ev.preventDefault();
      const page = link.getAttribute("data-goto-page");
      const anchor =
        link.getAttribute("data-goto-anchor") ||
        (link.getAttribute("href")?.startsWith("#") ? link.getAttribute("href").slice(1) : "");
      if (page === "guide" && anchor) {
        openGuideSection(anchor);
        return;
      }
      if (page) showPage(page);
    };
  });
}

function inboxFocusTerm(inbox) {
  if (!inbox?.terms?.length) return null;
  const current = state.inboxFocus[inbox.logic_id];
  return inbox.terms.find((row) => row.term === current) || inbox.terms[0];
}

function renderAiQueue(_queue) {
  return "";
}

async function refreshJobSummary(force = false) {
  if (!state.jobId) {
    $("#stat-ready").textContent = "—";
    $("#stat-blocked").textContent = "—";
    $("#stat-missing").textContent = "—";
    $("#stat-logic").textContent = "—";
    return false;
  }
  const cached = state._summaryCache;
  if (
    !force &&
    cached?.jobId === state.jobId &&
    Date.now() - cached.at < API_CACHE_TTL.summary
  ) {
    applyJobSummary(cached.summary);
    return true;
  }
  try {
    const s = await cachedApi(
      `summary:${state.jobId}`,
      () => api(`/api/jobs/${encodeURIComponent(state.jobId)}/summary`),
      API_CACHE_TTL.summary
    );
    if (s.bundle_version != null) noteBundleVersion(s.bundle_version);
    const summary = s.summary || {};
    applyJobSummary(summary);
    state._summaryCache = { jobId: state.jobId, summary, at: Date.now() };
    return true;
  } catch (e) {
    const msg = String(e.message || "");
    if (/not found|no analysis bundle/i.test(msg)) {
      setJobId(null);
    }
    return false;
  }
}

function applyJobSummary(summary) {
  if (!summary) return;
  $("#stat-ready").textContent = summary.rows_ready ?? 0;
  $("#stat-blocked").textContent = summary.rows_blocked ?? 0;
  $("#stat-missing").textContent = summary.missing_terms ?? 0;
  $("#stat-logic").textContent = summary.logic_groups ?? 0;
}

function updateTopbar(summary) {
  applyJobSummary(summary);
}

function resolveInitialPage(summary) {
  const fromPath = pageFromPath(window.location.pathname);
  const imported = jobBootstrapSource(summary).startsWith("imported");
  if (imported && fromPath === "logic-review") {
    return "export";
  }
  if (fromPath === "logic-review" && !state.jobId) {
    return "review";
  }
  return fromPath;
}

function persistCurrentPage(pageId) {
  try {
    sessionStorage.setItem("alex.currentPageId", pageId);
  } catch (_) {
    /* private mode */
  }
}

function jobBootstrapSource(summary) {
  return String(summary?.bootstrap_source || state._summaryCache?.summary?.bootstrap_source || "").trim();
}

function jobHasWorkableBundle(summary) {
  if (!state.jobId) return false;
  const s = summary || state._summaryCache?.summary || {};
  const src = jobBootstrapSource(s);
  if (src.startsWith("imported")) return true;
  return (s.test_candidates ?? 0) > 0 || (s.logic_groups ?? 0) > 0 || (s.logic_blocks ?? 0) > 0;
}

function jobReadiness(summary) {
  if (!state.jobId) return "no_job";
  if (jobHasWorkableBundle(summary)) {
    const src = jobBootstrapSource(summary);
    if (src.startsWith("imported")) return "imported_ready";
    return "analyzed_ready";
  }
  return "pending";
}

function copilotErrorBanner(result) {
  if (!result || result.ok !== false) return "";
  const cat = result.error_category || "unknown";
  const action = result.user_action ? `<p class="detail">${esc(result.user_action)}</p>` : "";
  return `<div class="card copilot-error-banner" data-error-category="${esc(cat)}">
    <p><b>Copilot:</b> ${esc(result.error || "Request failed")}</p>
    <p class="detail">Category: <code>${esc(cat)}</code></p>
    ${action}
  </div>`;
}

function requireJobHtml(mode = "no_job") {
  if (mode === "imported_ready" || mode === "analyzed_ready") return "";
  return `<div class="card">
    <p><b>No active job yet.</b> You can either analyze spec files or import existing work:</p>
    <ul class="detail">
      <li><b>Review specification</b> — parse .docx / .xlsx from uploads.</li>
      <li><b>Import TestSpec</b> — upload Final TestSpec .xlsx (no analyze required).</li>
      <li><b>Import bundle</b> — upload saved <code>ui_bundle.yaml</code>.</li>
    </ul>
    <button class="btn secondary" id="btn-goto-review">Go to Spec review</button>
  </div>`;
}

function bindNoJob() {
  const b = $("#btn-goto-review");
  if (b) b.onclick = () => showPage("review");
}

function initNav() {
  const nav = $("#nav");
  nav.innerHTML = PAGES.map(
    (p) =>
      `<button data-page="${p.id}" title="${esc(p.label)}"><span class="nav-icon">${icon(p.icon, "alex-icon--nav")}</span><span class="nav-step">${esc(p.step)}.</span><span class="nav-label">${esc(p.label)}</span></button>`
  ).join("");
  nav.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      showPage(btn.dataset.page);
    });
  });
}

function showPage(id, opts = {}) {
  const pageId = PAGE_ROUTES[id] ? id : "review";
  state.currentPageId = pageId;
  if (!opts.skipHistory) {
    syncUrlForPage(pageId, { replace: !!opts.replace });
  }
  persistCurrentPage(pageId);
  updatePageChrome(pageId);
  refreshM365TaskBanner();
  $("#nav").querySelectorAll("button").forEach((b) => {
    b.classList.toggle("active", b.dataset.page === pageId);
  });
  const map = {
    review: renderReview,
    "logic-review": renderLogicReview,
    "diagram-graph": renderDiagramGraph,
    library: renderLibrary,
    export: renderExport,
    "test-code": renderTestCode,
    guide: renderGuide,
  };
  const render = map[pageId] || renderReview;
  if (pageId === "test-code" && hasRunningM365TaskForPage("test-code")) {
    render({ ...opts, skipShell: true, preserveSelection: true });
  } else if (pageId === "logic-review" && hasRunningM365TaskForPage("logic-review")) {
    render({ ...opts, skipShell: true, skipSummary: true });
  } else {
    render(opts);
  }
}

async function saveFileSelection() {
  const payload = state.files.map((f) => ({
    path: f.path,
    name: f.name,
    file_type: f.file_type,
    file_type_label: f.file_type_label,
    role: f.role,
    selected: !!f.selected,
  }));
  await api("/api/files/select", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ files: payload }),
  });
}

function scheduleSaveSelection() {
  if (state.saveTimer) clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(async () => {
    try {
      await saveFileSelection();
      const st = $("#src-status");
      if (st) st.textContent = "Saved";
    } catch (e) {
      const st = $("#src-status");
      if (st) st.textContent = e.message;
    }
  }, 400);
}

function renderSourcesTable() {
  const tbody = $("#sources-tbody");
  const chkAll = $("#chk-all");
  if (!tbody) return;

  const allOn = state.files.length > 0 && state.files.every((f) => f.selected);
  const someOn = state.files.some((f) => f.selected);
  if (chkAll) {
    chkAll.checked = allOn;
    chkAll.indeterminate = someOn && !allOn;
  }

  tbody.innerHTML = state.files
    .map((f, idx) => {
      const typeOpts = FILE_TYPE_OPTIONS.map(
        (o) =>
          `<option value="${o.value}" ${f.file_type === o.value ? "selected" : ""}>${o.label}</option>`
      ).join("");
      return `<tr class="source-row ${f.selected ? "selected" : ""}" data-idx="${idx}">
        <td class="col-chk"><input type="checkbox" class="row-chk" data-idx="${idx}" ${
          f.selected ? "checked" : ""
        } /></td>
        <td class="col-name"><div class="source-file-cell">${icon("file-doc", "alex-icon--file")}<div class="source-file-cell__body"><div>${esc(f.name)}</div><div class="detail">Uploaded snapshot: ${esc(f.modified_label || "")}</div></div></div></td>
        <td class="col-type"><div class="type-select-wrap"><select class="type-select" data-idx="${idx}">${typeOpts}</select>${icon("chevron-down", "alex-icon--chevron")}</div></td>
      </tr>`;
    })
    .join("");

  tbody.querySelectorAll(".row-chk").forEach((cb) => {
    cb.onchange = (e) => {
      e.stopPropagation();
      const i = +cb.dataset.idx;
      state.files[i].selected = cb.checked;
      scheduleSaveSelection();
      updateSelectedCount();
      renderSourcesTable();
    };
  });

  tbody.querySelectorAll(".type-select").forEach((sel) => {
    sel.onchange = (e) => {
      e.stopPropagation();
      const i = +sel.dataset.idx;
      state.files[i].file_type = sel.value;
      state.files[i].file_type_label =
        FILE_TYPE_OPTIONS.find((o) => o.value === sel.value)?.label || sel.value;
      scheduleSaveSelection();
    };
  });

  tbody.querySelectorAll(".source-row").forEach((row) => {
    row.onclick = (e) => {
      if (e.target.matches("input, select, option")) return;
      const i = +row.dataset.idx;
      state.files[i].selected = !state.files[i].selected;
      scheduleSaveSelection();
      updateSelectedCount();
      renderSourcesTable();
    };
  });

  updateSelectedCount();
  updateReviewButton();
}

function renderReviewSummaryPanel(dash, preview, containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const wb = dash.workbench || {};
  const ev = dash.evidence_summary || {};
  const rows = (preview && preview.rows) || [];
  el.style.display = "block";
  el.innerHTML = `<section class="analysis-results card">
    <header class="alex-hero">
      <div>
        <h2 class="alex-hero__title">Analysis results</h2>
        <p class="alex-hero__sub">Continue in Logic for structure, Diagram for states, Final File for export.</p>
      </div>
      <div class="alex-hero__actions review-actions">
        <button class="btn" id="btn-logic-review">Logic &amp; definitions</button>
        <button class="btn secondary" id="btn-diagram-graph">State machine</button>
        <button class="btn secondary" id="btn-export">Final file</button>
      </div>
    </header>
    ${renderMetricCards([
      ["Rows ready", wb.rows_ready ?? 0, "ok"],
      ["Blocked", wb.rows_blocked ?? 0, "error"],
      ["Needs review", wb.rows_needing_review ?? 0, "warn"],
      ["Missing terms", wb.missing_terms ?? ev.terms_missing_definition ?? 0, "warn"],
      ["Logic groups", wb.logic_groups ?? 0, "info"],
    ])}
    ${renderSpecOverviewPanel(dash.overview)}
    ${
      (dash.excel_sheets || []).length
        ? `<div style="margin-top:1rem"><h3 class="alex-primary-panel__label">Excel sheets</h3><ul class="detail">${(dash.excel_sheets || [])
            .map(
              (s) =>
                `<li><b>${esc(s.name || "?")}</b>${s.selected === false ? " (skipped)" : ""} — ${esc(String(s.logic_blocks ?? s.rows_imported ?? "—"))} block/row(s)</li>`
            )
            .join("")}</ul></div>`
        : ""
    }
    ${
      (dash.prioritized_issues || []).length
        ? `<div style="margin-top:1rem"><h3 class="alex-primary-panel__label">Notes</h3>${renderPrioritizedIssues((dash.prioritized_issues || []).slice(0, 10))}</div>`
        : ""
    }
  </section>`;
  el.querySelector("#btn-logic-review").onclick = () => showPage("logic-review");
  el.querySelector("#btn-diagram-graph").onclick = () => showPage("diagram-graph");
  el.querySelector("#btn-export").onclick = () => showPage("export");
}

async function loadReviewResults() {
  if (!state.jobId) return;
  try {
    const [dash, preview] = await Promise.all([
      api(`/api/review/dashboard?job_id=${encodeURIComponent(state.jobId)}`),
      fetchWorkbench(state.exportLanguage),
    ]);
    state.bundle = {
      term_roles: dash.term_roles || {},
      source_index: dash.source_index || {},
    };
    applyJobSummary(dash.summary || {});
    renderReviewSummaryPanel(dash, preview, "review-results");
  } catch (e) {
    const el = $("#review-results");
    if (el) {
      el.style.display = "block";
      el.innerHTML = `<p class="detail" style="color:var(--red)">${esc(e.message)}</p>`;
    }
  }
}

function pollProgress(jobId) {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = setInterval(async () => {
    try {
      const st = await api(`/api/analysis/status?job_id=${encodeURIComponent(jobId)}`);
      updateProgressUI(st);
      if (st.status === "completed") {
        clearInterval(state.pollTimer);
        await refreshJobSummary();
        const pt = $("#progress-text");
        if (pt) pt.textContent = "Review complete.";
        await loadReviewResults();
      }
      if (st.status === "failed") {
        clearInterval(state.pollTimer);
        const pt = $("#progress-text");
        if (pt) pt.textContent = "Failed: " + (st.error_message || "unknown");
      }
    } catch (e) {
      const pt = $("#progress-text");
      if (pt) pt.textContent = e.message;
    }
  }, 800);
}

function isAiSigninOpen() {
  return localStorage.getItem(AI_SIGNIN_OPEN_KEY) === "1";
}

function setAiSigninOpen(open) {
  localStorage.setItem(AI_SIGNIN_OPEN_KEY, open ? "1" : "0");
}

function updateProgressUI(st) {
  const area = $("#progress-area");
  if (!area || !st) return;
  area.style.display = "block";
  const status = st.status || "waiting";
  const progress = Number(st.progress) || 0;
  const step = st.current_step || st.status || "…";
  const pt = $("#progress-text");
  const pf = $("#progress-fill");
  const badge = $("#progress-status-badge");
  const pct = $("#progress-percent");
  const hint = $("#progress-worker-hint");
  const logEl = $("#progress-log");
  const barWrap = $("#progress-bar-wrap");
  if (pt) pt.textContent = step;
  if (pct) pct.textContent = status === "queued" ? "waiting" : `${progress}%`;
  if (badge) {
    const label =
      status === "completed"
        ? "done"
        : status === "failed"
          ? "failed"
          : status === "queued"
            ? "queued"
            : status === "running"
              ? "running"
              : status;
    badge.textContent = label;
    badge.className = `tag ${
      status === "completed" ? "high" : status === "failed" ? "error" : status === "queued" ? "warning" : "warn"
    }`;
  }
  if (barWrap && pf) {
    if (status === "queued") {
      barWrap.classList.add("progress-bar--indeterminate");
      pf.style.width = "35%";
    } else {
      barWrap.classList.remove("progress-bar--indeterminate");
      pf.style.width = `${Math.max(progress, status === "running" && progress === 0 ? 4 : 0)}%`;
    }
  }
  if (hint) {
    if (status === "queued") {
      hint.hidden = false;
      hint.innerHTML =
        'Analyze is waiting for the worker. Run <code>./chay.sh</code> (Ubuntu) or <code>./dev.sh</code> (Mac) — one terminal starts web + worker. Or set <code>deployment.mode: local</code> in config.';
    } else {
      hint.hidden = true;
    }
  }
  if (logEl) {
    const lines = st.log || [];
    logEl.innerHTML = lines.length
      ? `<ul class="analyze-progress-log">${lines
          .slice(-8)
          .map((line) => `<li>${esc(line)}</li>`)
          .join("")}</ul>`
      : "";
  }
}

async function resumeAnalyzeProgress(jobId) {
  if (!jobId) return;
  try {
    const st = await api(`/api/analysis/status?job_id=${encodeURIComponent(jobId)}`);
    updateProgressUI(st);
    if (st.status !== "completed" && st.status !== "failed") {
      pollProgress(jobId);
    }
  } catch (_) {
    /* job may not exist yet */
  }
}

function updateReviewButton() {
  const n = state.files.filter((f) => f.selected).length;
  const btn = $("#btn-review");
  if (btn) {
    btn.disabled = n === 0;
    btn.className = "btn btn-with-icon";
    btn.innerHTML = `${icon("play-circle", "alex-icon--btn")} Review specification (${n} file${n === 1 ? "" : "s"})`;
  }
}

async function renderReview() {
  try {
    await loadM365Status();
    const copilot = copilotFeatureEnabled() ? await loadCopilotStatus().catch(() => null) : null;
    const data = await api("/api/files");
    state.files = data.files || [];
    updateSelectedCount();
    const n = state.files.filter((f) => f.selected).length;

    content().innerHTML = `<header class="page-header">
        <h2>Sources &amp; analyze</h2>
        <p class="lead">Select files, run one analysis pass, then continue to Logic review. Re-upload if you changed a local file.</p>
        <button type="button" class="btn secondary btn-with-icon" id="btn-review-guide">${icon("guide", "alex-icon--btn")} Open Guide</button>
      </header>
      ${renderReviewLoginHub(copilot)}
      <section class="card">
        <h3 class="section-kicker">Import existing TestSpec (Excel)</h3>
        <p class="detail">Upload file <b>.xlsx</b> TestSpec thực tế — hỗ trợ template <b>JP</b> (機能テスト, 手順, 入力/出力に対する期待値) và export EN của ALEX.</p>
        <p class="detail">Cột <b>手順</b> = mô tả thao tác; <b>Given/When/Then</b> đọc từ cột input/output. Tool tự nhận JP/EN từ header.</p>
        <div class="toolbar-row">
          <label class="detail">Ngôn ngữ import
            <select id="import-testspec-language" class="gtest-input gtest-select">
              <option value="">Tự nhận (JP/EN)</option>
              <option value="JP">JP — 日本語 TestSpec</option>
              <option value="EN">EN</option>
            </select>
          </label>
          <label class="btn secondary btn-with-icon upload-label">${icon("upload", "alex-icon--btn")} Import TestSpec (.xlsx)<input type="file" id="import-testspec-file" accept=".xlsx,.xlsm" hidden /></label>
          <label class="btn secondary btn-with-icon upload-label" title="Chỉ dùng khi restore job từ máy khác">${icon("upload", "alex-icon--btn")} Restore ui_bundle.yaml (advanced)<input type="file" id="import-bundle-file" accept=".yaml,.yml" hidden /></label>
        </div>
        <p id="import-status" class="detail"></p>
      </section>
      <section class="card">
        <div class="toolbar-row">
          <div class="toolbar-row__start">
            <label class="btn secondary btn-with-icon upload-label">${icon("upload", "alex-icon--btn")} Upload<input type="file" id="file-upload" multiple accept=".docx,.xlsx,.xlsm,.pdf,.cpp,.h,.png,.jpg,.md" hidden /></label>
            <button type="button" class="btn secondary btn-with-icon" id="btn-clear-files">${icon("refresh", "alex-icon--btn")} Start new review</button>
          </div>
          <div class="toolbar-row__end">
            <span id="src-status" class="detail"></span>
            <button type="button" class="btn btn-with-icon" id="btn-review" ${n ? "" : "disabled"}>${icon("play-circle", "alex-icon--btn")} Review specification (${n} file${n === 1 ? "" : "s"})</button>
          </div>
        </div>
        <div class="grid-wrap sources-table-wrap">
          <table class="data-grid sources-grid alex-table">
            <thead><tr>
              <th class="col-chk"><input type="checkbox" id="chk-all" title="Select all" aria-label="Select all files" /></th>
              <th class="col-name">File</th>
              <th class="col-type">Type</th>
            </tr></thead>
            <tbody id="sources-tbody"></tbody>
          </table>
        </div>
      </section>
      <div id="progress-area" class="card analyze-progress" style="display:none;margin-top:0.75rem">
        <div class="analyze-progress__head">
          <span id="progress-status-badge" class="tag warning">—</span>
          <span id="progress-percent" class="detail">0%</span>
        </div>
        <p id="progress-text">Starting…</p>
        <div class="progress-bar" id="progress-bar-wrap"><div id="progress-fill" style="width:0%"></div></div>
        <p id="progress-worker-hint" class="detail analyze-worker-hint" hidden></p>
        <div id="progress-log"></div>
      </div>
      <p id="review-run-status" class="detail"></p>
      <div id="review-results" style="display:none;margin-top:0.75rem"></div>`;

    bindOnChange("#file-upload", async () => {
      const inp = $("#file-upload");
      if (!inp.files.length) return;
      const fd = new FormData();
      for (const f of inp.files) fd.append("files", f);
      $("#src-status").textContent = "Uploading…";
      try {
        const r = await fetch("/api/upload", { method: "POST", body: fd });
        if (!r.ok) throw new Error(await r.text());
        const j = await r.json();
        state.files = j.files || [];
        $("#src-status").textContent = (j.replaced || []).length
          ? `Updated ${(j.replaced || []).length} existing file(s).`
          : `Added ${(j.saved || []).length} file(s).`;
        renderSourcesTable();
        updateReviewButton();
      } catch (e) {
        $("#src-status").textContent = e.message;
      }
      inp.value = "";
    });
    $("#btn-review-guide").onclick = () => openGuideSection("guide-start");
    bindTabHelpLinks();

    async function importJobFromFile(inputId, endpoint, { language = "" } = {}) {
      const inp = $(inputId);
      if (!inp?.files?.length) return;
      const statusEl = $("#import-status");
      statusEl.textContent = "Importing…";
      const fd = new FormData();
      fd.append("file", inp.files[0]);
      const lang = language || $("#import-testspec-language")?.value || "";
      const url = lang && endpoint.includes("import-testspec") ? `${endpoint}?language=${encodeURIComponent(lang)}` : endpoint;
      try {
        const r = await fetch(url, { method: "POST", body: fd });
        const text = await r.text();
        let data = {};
        try {
          data = JSON.parse(text);
        } catch {
          throw new Error(text || `HTTP ${r.status}`);
        }
        if (!r.ok) {
          const msg =
            typeof data.detail === "object"
              ? data.detail.error || JSON.stringify(data.detail.preview || data.detail)
              : data.detail || data.error || text;
          throw new Error(msg);
        }
        setJobId(data.job_id);
        if (data.export_language) state.exportLanguage = data.export_language;
        invalidateApiCache();
        await refreshJobSummary(true);
        const sheets = (data.sheet_summary || [])
          .map((s) => `${s.name}: ${s.rows_imported ?? 0} row(s)`)
          .join("; ");
        statusEl.textContent = `Import complete — job ${data.job_id}${sheets ? ` (${sheets})` : ""}.`;
        showPage("export", { replace: true });
      } catch (e) {
        statusEl.textContent = `Import failed: ${e.message}`;
      }
      inp.value = "";
    }

    bindOnChange("#import-testspec-file", () =>
      importJobFromFile("#import-testspec-file", "/api/jobs/import-testspec"));
    bindOnChange("#import-bundle-file", () =>
      importJobFromFile("#import-bundle-file", "/api/jobs/import-bundle"));

    $("#btn-clear-files").onclick = async () => {
      $("#src-status").textContent = "Clearing uploaded files…";
      try {
        await api("/api/files/clear", { method: "POST" });
        state.files = [];
        setJobId(null);
        state.copilot.assistCommand = null;
        state.copilot.loginCommand = null;
        $("#review-results").style.display = "none";
        $("#src-status").textContent = "Workspace cleared.";
        renderSourcesTable();
        updateReviewButton();
      } catch (e) {
        $("#src-status").textContent = e.message;
      }
    };

    bindOnChange("#chk-all", () => {
      const on = $("#chk-all").checked;
      state.files.forEach((f) => (f.selected = on));
      scheduleSaveSelection();
      renderSourcesTable();
      updateReviewButton();
    });

    $("#btn-review").onclick = async () => {
      $("#progress-area").style.display = "block";
      const rr = $("#review-results");
      if (rr) rr.style.display = "none";
      try {
        await saveFileSelection();
        const paths = state.files.filter((f) => f.selected).map((f) => f.path);
        if (!paths.length) {
          $("#progress-text").textContent = "Select at least one file.";
          return;
        }
        const res = await api("/api/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            use_all_detected: false,
            selected_files: paths,
            enable_ollama: false,
            strict_mode: true,
            generate_candidates: true,
          }),
        });
        setJobId(res.job_id);
        pollProgress(res.job_id);
      } catch (e) {
        $("#progress-text").textContent = "Error: " + e.message;
      }
    };

    const btnCopilotLogin = $("#btn-copilot-login");
    if (btnCopilotLogin) {
      btnCopilotLogin.onclick = async () => {
        const testBtn = $("#btn-copilot-test-prompt");
        if (testBtn) testBtn.disabled = true;
        await startCopilotLogin(async () => {
          const fresh = await loadCopilotStatus().catch(() => null);
          $("#copilot-review-status").innerHTML = copilotStatusHtml(fresh);
          refreshGithubAuthBadge(fresh);
          if (testBtn) testBtn.disabled = false;
        });
      };
    }

    const btnCopilotCheck = $("#btn-copilot-check");
    if (btnCopilotCheck) {
      btnCopilotCheck.onclick = async () => {
        await verifyCopilot(async () => {
          const fresh = await loadCopilotStatus().catch(() => null);
          $("#copilot-review-status").innerHTML = copilotStatusHtml(fresh);
          refreshGithubAuthBadge(fresh);
        }, { deep: false });
      };
    }

    const btnCopilotTest = $("#btn-copilot-test-prompt");
    if (btnCopilotTest) {
      btnCopilotTest.onclick = async () => {
        await verifyCopilot(async () => {
          const fresh = await loadCopilotStatus().catch(() => null);
          $("#copilot-review-status").innerHTML = copilotStatusHtml(fresh);
          refreshGithubAuthBadge(fresh);
        }, { deep: true });
      };
    }

    bindReviewLoginHub();
    refreshCopilotLoginContainers();
    renderSourcesTable();
    updateReviewButton();
    refreshJobSummary();
    if (state.jobId) {
      resumeAnalyzeProgress(state.jobId);
      loadReviewResults();
    }
  } catch (e) {
    content().innerHTML = `<p class="detail" style="color:var(--red)">${esc(e.message)}</p>`;
  }
}
function renderTreeLines(lines) {
  if (!lines?.length) return "<p class='detail'>No tree lines.</p>";
  return `<pre class="tree-view logic-tree-pre">${esc(lines.join("\n"))}</pre>`;
}

function logicNodeLabel(node) {
  const t = node?.node_type || node?.type || "";
  if (t === "edge_event" || node?.atom_kind === "edge_event") {
    const raw = node.raw_text || "";
    if (raw.includes("→") || raw.includes("->")) return raw;
    return `${node.from_state || "?"} → ${node.to_state || "?"}`;
  }
  if (t === "timing_condition" || node?.atom_kind === "timing_condition") {
    const tq = node.timer_qualified || {};
    if (tq.timer_symbol) return `${tq.timer_symbol} ${tq.qualifier || "elapsed"}`;
    return node.raw_text || node.normalized_text || "timer";
  }
  if (t === "signal_condition") {
    return [node.condition_name || node.signal, node.operator, node.value].filter(Boolean).join(" ");
  }
  if (t === "boolean_predicate") {
    return node.condition_name || node.signal || node.raw_text || node.normalized_text || "flag";
  }
  if (t === "timing_condition" || t === "opaque") {
    return node.raw_text || node.normalized_text || t;
  }
  if (t === "condition") {
    return node.condition_name || node.name || node.raw_text || "condition";
  }
  if (t === "AND" || t === "OR" || t === "NOT" || node.gate) {
    return node.gate || t;
  }
  return node.condition_name || node.raw_text || node.normalized_text || node.node_type || "?";
}

function renderInteractiveLogicTree(item, activeNodeIds = []) {
  const nodes = item?.tree_nodes || [];
  if (!nodes.length) {
    return renderTreeLines(item?.tree_lines || []);
  }
  const byParent = {};
  nodes.forEach((node) => {
    const pid = node.parent_node_id || "__root__";
    if (!byParent[pid]) byParent[pid] = [];
    byParent[pid].push(node);
  });
  Object.values(byParent).forEach((list) => list.sort((a, b) => (a.depth || 0) - (b.depth || 0)));

  const renderNodeLi = (node, isLast) => {
    const nid = node.node_id || "";
    const active = activeNodeIds.includes(nid) ? " is-active" : "";
    const focus = state.logicTreeFocus?.nodeId === nid ? " is-focus" : "";
    const typeClass = ` logic-tree-node--${esc(node.node_type || "ref")}`;
    const cssClass = node.css_class ? ` ${esc(node.css_class)}` : "";
    const lastClass = isLast ? " logic-tree-node--last" : "";
    const sourceRow = node.source_row != null ? String(node.source_row) : "";
    const opClass = ` logic-tree-node__btn--${esc(node.node_type || "ref")}`;
    const kindChip =
      node.atom_kind === "edge_event" || node.node_type === "edge_event"
        ? `<span class="logic-node-kind logic-node-kind--edge" title="Edge event (one cycle)">edge</span>`
        : node.atom_kind === "timing_condition" || node.node_type === "timing_condition"
          ? `<span class="logic-node-kind logic-node-kind--timer" title="Timer-qualified">T</span>`
          : node.value_domain === "sentinel"
            ? `<span class="logic-node-kind logic-node-kind--sentinel" title="Multivalued sentinel">Σ</span>`
            : "";
    return `<li class="logic-tree-node${active}${focus}${typeClass}${lastClass}${cssClass}" data-tree-node="${esc(nid)}" data-tree-label="${esc(logicNodeLabel(node))}" data-source-row="${esc(sourceRow)}">
      <span class="logic-tree-node__connector" aria-hidden="true"></span>
      <button type="button" class="logic-tree-node__btn${opClass}">${kindChip}${esc(logicNodeLabel(node))}</button>
      ${renderBranch(nid)}
    </li>`;
  };

  const renderBranch = (parentId) => {
    const children = byParent[parentId] || [];
    if (!children.length) return "";
    return `<ul class="logic-tree-interactive">${children
      .map((node, idx) => renderNodeLi(node, idx === children.length - 1))
      .join("")}</ul>`;
  };

  const roots = byParent["__root__"] || nodes.filter((n) => !n.parent_node_id);
  if (!roots.length) {
    return `<div class="logic-tree-interactive-wrap">${renderBranch("__root__")}</div>`;
  }
  return `<div class="logic-tree-interactive-wrap"><ul class="logic-tree-interactive">${roots
    .map((node, idx) => renderNodeLi(node, idx === roots.length - 1))
    .join("")}</ul></div>`;
}

function renderPathSimulatorPanel(item, simResult = null) {
  const signals = simResult?.signals || [];
  const defaults = Object.fromEntries(
    signals.map((row) => [row.signal, row.default ?? "0"])
  );
  const saved = state.pathSimAssignments?.[item.logic_id] || {};
  const inputs = signals.length
    ? signals
    : (item.trace_rows || [])
        .map((row) => row.term)
        .filter(Boolean)
        .slice(0, 12)
        .map((term) => ({ signal: term, default: "0" }));
  if (!inputs.length) {
    return `<p class="detail">No simulatable signals detected in this logic tree yet.</p>`;
  }
  const status = simResult?.status || "unknown";
  const statusLabel =
    status === "active" ? "Logic path ACTIVE" : status === "inactive" ? "Logic path INACTIVE" : "Partial / unknown";
  const statusClass = status === "active" ? "high" : status === "inactive" ? "error" : "warning";
  return `<div class="logic-path-simulator">
    <div class="logic-path-simulator__head">
      <h4>Path simulator</h4>
      <span class="tag ${statusClass}" id="logic-sim-status">${esc(statusLabel)}</span>
    </div>
    <p class="detail">Set signal values, then run what-if to see which branches activate.</p>
    <div class="logic-path-simulator__grid">${inputs
      .map(
        (row) => `<label class="logic-path-simulator__field">
          <span>${esc(row.signal)}</span>
          <input type="text" class="gtest-input logic-sim-input" data-sim-signal="${esc(row.signal)}" value="${esc(saved[row.signal] ?? row.default ?? "0")}" />
        </label>`
      )
      .join("")}</div>
    <button type="button" class="btn secondary" id="btn-logic-sim-run">Run what-if</button>
  </div>`;
}

function renderFootnoteAttachmentsPanel(data) {
  if (!data) return "";
  const attached = data.by_logic ? Object.values(data.by_logic).flat() : data.attachments || [];
  if (!attached.length) return "";
  return `<details class="alex-ref-panel" style="margin-top:0.75rem">
    <summary>Attached from footnote (${attached.length})</summary>
    <div class="alex-ref-body">
      <p class="detail">Cross-file logic materialized from footnote references.</p>
      <ul class="detail footnote-attach-list">${attached
        .map(
          (row) =>
            `<li><b>${esc(row.source_footnote || "footnote")}</b> → ${esc(row.control_name || row.logic_id || "")} · ${esc(row.from_file || "")}
              <pre class="expr-block expr-block--spec" style="margin-top:0.35rem">${esc((row.materialized_excerpt?.raw_expression || "").slice(0, 240))}</pre>
            </li>`
        )
        .join("")}</ul>
      <label class="detail">Attach reference file (Excel/Word/PDF)
        <input type="file" id="reference-file-upload" multiple accept=".xlsx,.xlsm,.docx,.pdf" />
      </label>
      <p id="reference-file-status" class="detail"></p>
    </div>
  </details>`;
}

function renderPathTcMatrixPanel(matrix, proposal) {
  if (!matrix?.ok) return "";
  const paths = matrix.paths || [];
  const summary = matrix.summary || {};
  if (!paths.length) return "";
  const rows = paths
    .map((p) => {
      const cls =
        p.coverage_status === "full" ? "high" : p.coverage_status === "partial" ? "warning" : "error";
      return `<tr>
        <td><code>${esc(p.path_id)}</code></td>
        <td>${esc(p.label || "")}</td>
        <td><span class="tag ${cls}">${esc(p.coverage_status)}</span></td>
        <td>${p.covered_count || 0}</td>
        <td class="detail">${esc((p.signals || []).join(", "))}</td>
      </tr>`;
    })
    .join("");
  const proposeNote = proposal?.proposed_count
    ? `<p class="detail">${proposal.proposed_count} missing path TC(s) can be proposed.</p>`
    : "";
  return `<details class="alex-ref-panel" open style="margin-top:0.75rem">
    <summary>Path × test case matrix (${summary.path_count || paths.length} paths)</summary>
    <div class="alex-ref-body">
      <p class="detail">${summary.paths_full || 0} full · ${summary.paths_partial || 0} partial · ${summary.paths_missing || 0} missing coverage</p>
      <div class="grid-wrap"><table class="data-grid alex-table path-tc-matrix">
        <thead><tr><th>Path</th><th>Label</th><th>Coverage</th><th>TCs</th><th>Signals</th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
      ${proposeNote}
      <button type="button" class="btn secondary" id="btn-path-tc-propose">Propose missing TCs</button>
      <p id="path-tc-propose-status" class="detail"></p>
    </div>
  </details>`;
}

function formatSectionZone(zone) {
  const map = {
    control_conditions: "Control conditions",
    definitions: "Definitions",
    constants: "Constants",
    overview: "Overview",
    state_charts: "State / timing chart",
    changelog: "Changelog",
    metadata: "Metadata",
    unknown: "Unclassified",
  };
  return map[String(zone || "").toLowerCase()] || String(zone || "").replaceAll("_", " ");
}

function renderLogicSemanticsBadges(item) {
  const chips = [];
  if (item?.section_zone) {
    chips.push({ cls: "logic-chip--zone", label: formatSectionZone(item.section_zone) });
  }
  if (item?.decision_mode === "sequential") {
    chips.push({ cls: "logic-chip--priority", label: "Priority order" });
  } else if (item?.decision_mode === "boolean") {
    chips.push({ cls: "logic-chip--boolean", label: "Boolean OR/AND" });
  }
  (item?.timer_qualifiers || []).slice(0, 4).forEach((tq) => {
    const sym = tq.timer_symbol || "Timer";
    const q = tq.qualifier || "elapsed";
    chips.push({ cls: "logic-chip--timer", label: `${sym} · ${q}` });
  });
  const treeNodes = item?.tree_nodes || [];
  const edgeCount = treeNodes.filter((n) => n.atom_kind === "edge_event" || n.node_type === "edge_event").length;
  if (edgeCount) {
    chips.push({ cls: "logic-chip--edge", label: `${edgeCount} edge event${edgeCount > 1 ? "s" : ""}` });
  }
  if (!chips.length) return "";
  return `<div class="logic-semantics-badges">${chips
    .map((c) => `<span class="logic-chip ${c.cls}">${esc(c.label)}</span>`)
    .join("")}</div>`;
}

function renderFormalSpecContextPanel(data, item) {
  const profiles = data?.spec_profiles || [];
  const machines = (data?.state_machines || []).filter(Boolean);
  const retention = data?.retention_rules || [];
  const annotations = data?.review_annotations || [];
  const relatedMachine = machines.find((m) => m.state && item?.control_name && m.state === item.control_name);
  const blocks = [];
  if (profiles.length) {
    const p = profiles[0];
    blocks.push(
      `<div class="formal-spec-card"><h4>Spec profile</h4>
        <p class="detail">${p.is_logic_spec ? "Logic specification detected" : "Document type uncertain"}
          · score ${Math.round((p.classifier_score || 0) * 100)}%</p>
        ${(p.section_zones || []).length ? `<ul class="detail">${(p.section_zones || [])
          .slice(0, 8)
          .map((z) => `<li>${esc(z.title || "")} → ${esc(formatSectionZone(z.zone))}</li>`)
          .join("")}</ul>` : ""}
      </div>`
    );
  }
  if (relatedMachine || machines.length) {
    const m = relatedMachine || machines[0];
    blocks.push(
      `<div class="formal-spec-card"><h4>State lifecycle</h4>
        <dl class="alex-meta-stats is-compact">
          ${m.initial_value != null ? `<div><dt>Initial</dt><dd>${esc(m.initial_value)}</dd></div>` : ""}
          ${m.start_expression ? `<div><dt>Get started</dt><dd>${esc(m.start_expression)}</dd></div>` : ""}
          ${m.finish_expression ? `<div><dt>Finish</dt><dd>${esc(m.finish_expression)}</dd></div>` : ""}
        </dl>
      </div>`
    );
  }
  if (retention.length) {
    blocks.push(
      `<div class="formal-spec-card"><h4>Memory / retention (${retention.length})</h4>
        <ul class="detail">${retention
          .slice(0, 5)
          .map((r) => `<li><b>${esc(r.rule_kind || "rule")}</b> — ${esc((r.raw_text || "").slice(0, 120))}</li>`)
          .join("")}</ul>
      </div>`
    );
  }
  if (annotations.length) {
    blocks.push(
      `<div class="formal-spec-card"><h4>Excel review notes (${annotations.length})</h4>
        <ul class="detail">${annotations
          .slice(0, 6)
          .map(
            (a) =>
              `<li><b>${esc(a.cell || "")}</b> ${esc((a.text || "").slice(0, 100))}${a.source?.sheet ? ` <span class="muted">(${esc(a.source.sheet)})</span>` : ""}</li>`
          )
          .join("")}</ul>
      </div>`
    );
  }
  const signals = data?.signals || [];
  if (signals.length) {
    blocks.push(
      `<div class="formal-spec-card"><h4>Signal registry (${signals.length})</h4>
        <ul class="detail">${signals
          .slice(0, 8)
          .map(
            (s) =>
              `<li><b>${esc(s.name || "")}</b>${s.initial_value ? ` · init=${esc(s.initial_value)}` : ""}${s.fail_safe_value ? ` · fail=${esc(s.fail_safe_value)}` : ""}</li>`
          )
          .join("")}</ul>
      </div>`
    );
  }
  if (item?.outcome_label) {
    blocks.push(
      `<div class="formal-spec-card"><h4>Transition outcome</h4>
        <p class="detail">${esc(item.outcome_label)}</p>
      </div>`
    );
  }
  if (!blocks.length) return "";
  return `<section class="formal-spec-panel card"><h3 class="alex-primary-panel__label">Formal spec context</h3><div class="formal-spec-grid">${blocks.join("")}</div></section>`;
}

function renderSpecOverviewPanel(overview) {
  if (!overview) return "";
  return `<section class="alex-overview-panel card">
    <h3 class="alex-primary-panel__label">Spec overview</h3>
    <div class="alex-overview-grid">
      <div><span class="detail">Logic OK</span><b>${overview.logic_groups_ok ?? 0}</b></div>
      <div><span class="detail">Partial</span><b>${overview.logic_groups_partial ?? 0}</b></div>
      <div><span class="detail">Failed</span><b>${overview.logic_groups_failed ?? 0}</b></div>
      <div><span class="detail">Understanding</span><b>${overview.understanding_percent != null ? `${overview.understanding_percent}%` : "—"}</b></div>
    </div>
    ${
      (overview.top_blockers || []).length
        ? `<div style="margin-top:0.75rem"><h4>Notes</h4>${renderPrioritizedIssues(overview.top_blockers)}</div>`
        : ""
    }
  </section>`;
}

function renderPrioritizedIssues(issues) {
  if (!issues?.length) return "";
  return `<ul class="detail issue-plain-list">${issues
    .map((row) => {
      const text = String(
        row.message || row.parser_reason || (row.type || "issue").replaceAll("_", " ")
      ).trim();
      return `<li>${esc(text.slice(0, 220))}</li>`;
    })
    .join("")}</ul>`;
}

function traceStatusLabel(status) {
  if (status === "resolved") return "Defined";
  if (status === "needs_review") return "Review added";
  return "Needs define";
}

function renderTraceRows(traceRows) {
  if (!traceRows?.length) return "<p class='detail'>No referenced terms detected.</p>";
  return `<div class="grid-wrap"><table class="data-grid alex-table alex-trace-table"><thead><tr>
    <th class="col-term">Term</th><th>What we found</th><th>Sources</th>
  </tr></thead><tbody>${traceRows
    .map((row) => {
      const chips = [];
      (row.definitions || []).slice(0, 4).forEach((d) => {
        const kind = d.kind === "added_file" ? "file" : d.kind === "engineer_note" ? "note" : "spec";
        const label = (d.name || "term").length > 28 ? `${(d.name || "term").slice(0, 25)}…` : d.name || "term";
        chips.push({
          kind,
          label: compactSourceLabel(d.source) ? `${label} · ${compactSourceLabel(d.source)}` : label,
          detail: [d.name, compactSourceLabel(d.source) || formatSourceReadable(d.source), d.definition]
            .filter(Boolean)
            .join("\n"),
        });
      });
      (row.aliases || []).slice(0, 2).forEach((a) => {
        chips.push({
          kind: "alias",
          label: `${a.alias} → ${a.target}`,
          detail: formatSourceReadable(a.source) || `${a.alias} → ${a.target}`,
        });
      });
      (row.footnotes || []).slice(0, 2).forEach((f) => {
        chips.push({ kind: "note", label: f.ref || "footnote", detail: formatSourceReadable(f.source) || f.ref });
      });
      if (row.nested_logic_block) {
        chips.push({
          kind: "logic",
          label: row.nested_logic_block.name || "nested",
          detail:
            formatSourceReadable(row.nested_logic_block.source) || row.nested_logic_block.parse_status || "",
        });
      }
      const sources = chips.length
        ? renderEvidenceNotes(chips, { label: "Definitions" })
        : "<span class='detail'>No definition found yet.</span>";
      return `<tr>
        <td><code>${esc(row.term)}</code></td>
        <td>${esc(row.preview || "")}</td>
        <td>${sources}</td>
      </tr>`;
    })
    .join("")}</tbody></table></div>`;
}

function renderIssueList(issues) {
  if (!issues?.length) return "<p class='detail'>No direct issues linked to this control.</p>";
  const grouped = [];
  const map = new Map();
  issues.forEach((i) => {
    const status = i.display_severity || i.severity || "warning";
    const title = i.type === "unresolved_condition" ? "Missing definition" : (i.type || i.id || "Issue").replaceAll("_", " ");
    const message = i.type === "unresolved_condition"
      ? (i.resolved_in_review ? "Resolved during review." : "Still missing a trusted definition.")
      : (i.message || "").slice(0, 160);
    const key = `${status}|${title}|${message}`;
    if (!map.has(key)) {
      map.set(key, { status, title, message, count: 0 });
      grouped.push(map.get(key));
    }
    map.get(key).count += 1;
  });
  return `<div class="logic-issue-list compact-list">${grouped
    .map(
      (row) => `<div class="issue-pill">
      <span class="issue-main"><b>${esc(row.title)}</b></span>
      <span class="issue-detail">${esc(row.message)}${row.count > 1 ? ` (${row.count})` : ""}</span>
    </div>`
    )
    .join("")}</div>`;
}

function renderCopilotUnderstandingBanner(pack, plan) {
  const fk = pack?.footnote_knowledge || {};
  const openQs = [
    ...(plan?.open_questions || []).map((q) => (typeof q === "string" ? q : q.question || q.text || "")),
    ...(pack?.logic?.missing_definitions || []).map((d) => `Thiếu định nghĩa: ${d}`),
  ].filter(Boolean);
  const unresolved = (fk.footnotes || []).filter((f) => f.needs_clarification || !f.resolved);
  unresolved.forEach((f) => {
    openQs.push(`Footnote ${f.ref || "?"} chưa rõ — ${f.condition_name || "cross-spec ref"}`);
  });
  if (!openQs.length) return "";
  const pct = fk.understanding_percent != null ? `${fk.understanding_percent}%` : "—";
  return `<div class="copilot-clarify-banner">
    <p><b>Copilot cần làm rõ trước khi viết testcase</b> <span class="detail">(hiểu spec: ${esc(pct)})</span></p>
    <ul class="copilot-clarify-list">${openQs
      .slice(0, 8)
      .map((q) => `<li>${esc(q)}</li>`)
      .join("")}</ul>
    <p class="detail">Trả lời ngắn trong ô Engineer note bên dưới, hoặc bấm <b>Send follow-up</b>. Không đoán giá trị cho (*n).</p>
  </div>`;
}

function renderCopilotContextSummary(pack) {
  if (!pack) return "<p class='detail'>Bấm <b>Hiểu spec</b> để Copilot đọc logic, footnote (*n) và gap coverage.</p>";
  const gaps = pack.coverage_gaps || {};
  const vm = pack.verification_matrix || {};
  const logic = pack.logic || {};
  const fk = pack.footnote_knowledge || {};
  const constraints = pack.engineer_input?.parsed_constraints || {};
  const constraintLines = Object.entries(constraints)
    .map(([sig, def]) => `<li><code>${esc(sig)}</code> → ${esc(def)}</li>`)
    .join("");
  const vmLine =
    vm.one_to_many_count || vm.many_to_one_count || vm.partial_assert_count
      ? `<p class="detail">Verify matrix: ${vm.one_to_many_count || 0} same-input variants · ${vm.many_to_one_count || 0} same-output variants · ${vm.partial_assert_count || 0} partial assert</p>`
      : "";
  const footLine =
    fk.unresolved_footnote_count > 0
      ? `<p class="detail warn">Footnote chưa resolve: ${fk.unresolved_footnote_count} — Copilot sẽ hỏi thay vì hardcode.</p>`
      : fk.footnotes?.length
        ? `<p class="detail">Footnotes linked: ${fk.footnotes.length}</p>`
        : "";
  return `<div class="copilot-context-summary">
    <p><b>${esc(logic.control_name || pack.logic_id)}</b> · parse <code>${esc(logic.parse_status || "—")}</code></p>
    <p class="detail">Test cases: ${(pack.testcases || []).length} · Paths: ${(pack.paths || []).length} · Missing paths: ${gaps.missing_path_count ?? 0} · Compliance fails: ${gaps.compliance_fail_count ?? 0} · Boundary gaps: ${gaps.boundary_gap_count ?? 0}</p>
    ${footLine}
    ${vmLine}
    ${constraintLines ? `<ul class="detail">${constraintLines}</ul>` : ""}
    ${(pack.evidence?.attachments || []).length ? `<p class="detail">Attachments: ${pack.evidence.attachments.map((a) => esc(a.name)).join(", ")}</p>` : ""}
  </div>`;
}

function collectCopilotPlanFromDom() {
  const items = [];
  document.querySelectorAll(".copilot-plan-table tbody tr[data-plan-index]").forEach((tr) => {
    const idx = Number(tr.dataset.planIndex);
    const read = (sel) => tr.querySelector(sel)?.value?.trim() ?? "";
    items.push({
      plan_item_id: read("[data-plan-field='plan_item_id']") || `P${idx + 1}`,
      action: read("[data-plan-field='action']") || "update_existing",
      candidate_id: read("[data-plan-field='candidate_id']"),
      proposed_id: read("[data-plan-field='proposed_id']"),
      test_function: read("[data-plan-field='test_function']"),
      event: read("[data-plan-field='event']"),
      intent: read("[data-plan-field='intent']"),
      rationale: read("[data-plan-field='rationale']"),
    });
  });
  return { plan_items: items };
}

function renderCopilotPlanTable(plan) {
  const items = plan?.plan_items || [];
  if (!items.length) return "<p class='detail'>No plan yet — click Generate plan.</p>";
  return `<div class="grid-wrap"><table class="copilot-plan-table">
    <thead><tr><th>ID</th><th>Action</th><th>TC</th><th>Proposed</th><th>Fn</th><th>Event</th><th>Intent</th><th>Rationale</th></tr></thead>
    <tbody>${items
      .map(
        (row, i) => `<tr data-plan-index="${i}">
          <td><input class="gtest-input" data-plan-field="plan_item_id" value="${esc(row.plan_item_id || "")}" /></td>
          <td><input class="gtest-input" data-plan-field="action" value="${esc(row.action || "")}" /></td>
          <td><input class="gtest-input" data-plan-field="candidate_id" value="${esc(row.candidate_id || "")}" /></td>
          <td><input class="gtest-input" data-plan-field="proposed_id" value="${esc(row.proposed_id || "")}" /></td>
          <td><input class="gtest-input" data-plan-field="test_function" value="${esc(row.test_function || "")}" /></td>
          <td><input class="gtest-input" data-plan-field="event" value="${esc(row.event || "")}" /></td>
          <td><input class="gtest-input" data-plan-field="intent" value="${esc(row.intent || "")}" /></td>
          <td><input class="gtest-input" data-plan-field="rationale" value="${esc(row.rationale || "")}" /></td>
        </tr>`
      )
      .join("")}</tbody>
  </table></div>
  <div class="review-actions" style="margin-top:0.5rem">
    <button type="button" class="btn secondary" id="btn-copilot-save-plan">Save plan</button>
  </div>
  ${plan.understanding_summary ? `<p class="detail"><b>Summary:</b> ${esc(plan.understanding_summary)}</p>` : ""}`;
}

function buildCopilotM365Brief({ engineerNote = "", copilotSession = null, logicId = "" } = {}) {
  const pack = copilotSession?.context_pack || {};
  const plan = copilotSession?.plan || {};
  const logic = pack.logic || {};
  const lines = [
    "# ALEX — M365 Copilot brief",
    logicId ? `Logic group: ${logicId}` : "",
    logic.control_name ? `Control: ${logic.control_name}` : "",
    "",
    "## Engineer note",
    engineerNote.trim() || "(none)",
    "",
    "## Context summary",
    `Test cases: ${(pack.testcases || []).length}`,
    `Paths: ${(pack.paths || []).length}`,
    `Missing paths: ${pack.coverage_gaps?.missing_path_count ?? 0}`,
    "",
  ];
  const items = plan.plan_items || [];
  if (items.length) {
    lines.push("## Plan items");
    items.forEach((it, i) => {
      lines.push(`${i + 1}. [${it.action || "update"}] ${it.candidate_id || "new"} — ${it.rationale || it.summary || ""}`);
    });
    lines.push("");
  }
  if (plan.understanding_summary) {
    lines.push("## Understanding");
    lines.push(plan.understanding_summary);
  }
  return lines.filter((l) => l !== undefined).join("\n");
}

function renderCopilotDraftDiffs(diffs) {
  if (!diffs?.length) return "<p class='detail'>No drafts — click Write test cases.</p>";
  return `<div class="copilot-draft-list">${diffs
    .map((d) => {
      const noop = d.noop;
      const checked = d.default_selected !== false && !noop ? "checked" : "";
      return `<article class="copilot-draft-diff${noop ? " is-noop" : ""}">
        <header class="knowledge-diff-row__head">
          <label><input type="checkbox" class="copilot-draft-check" data-draft-index="${d.draft_index}" ${checked} ${noop ? "disabled" : ""} />
          <span class="tag ${noop ? "warning" : "high"}">${noop ? "NO-OP" : esc(d.action || "update")}</span>
          <code>${esc(d.candidate_id || "—")}</code></label>
        </header>
        ${noop ? `<p class="detail">Copilot did not change this row — review plan or regenerate write.</p>` : ""}
        <div class="knowledge-diff-grid">
          <div class="alex-io-block"><h5>Operation before</h5>${formatIoBlock(d.before?.operation || "—")}</div>
          <div class="alex-io-block"><h5>Operation after</h5>${formatIoBlock(d.after?.operation || "—")}</div>
          <div class="alex-io-block"><h5>UseCase before</h5>${formatIoBlock(d.before?.use_case || "—")}</div>
          <div class="alex-io-block"><h5>UseCase after</h5>${formatIoBlock(d.after?.use_case || "—")}</div>
          <div class="alex-io-block"><h5>Expected input before</h5>${formatIoBlock(d.before?.expected_input || "—")}</div>
          <div class="alex-io-block"><h5>Expected input after</h5>${formatIoBlock(d.after?.expected_input || "—")}</div>
          <div class="alex-io-block"><h5>Expected output before</h5>${formatIoBlock(d.before?.expected_output || "—")}</div>
          <div class="alex-io-block"><h5>Expected output after</h5>${formatIoBlock(d.after?.expected_output || "—")}</div>
        </div>
      </article>`;
    })
    .join("")}</div>`;
}

function renderCopilotWorkbench(inbox, { engineerNote = "", attachments = [], logicId = "", copilotSession = null } = {}) {
  const step = state.copilotStep?.[logicId] || "context";
  const pack = copilotSession?.context_pack || null;
  const plan = copilotSession?.plan || null;
  const diffs = copilotSession?.draft_diffs || [];
  const steps = ["context", "plan", "write", "review"];
  const stepper = steps
    .map((s) => {
      const idx = steps.indexOf(step);
      const curIdx = steps.indexOf(s);
      const cls = curIdx === idx ? "is-active" : curIdx < idx ? "is-done" : "";
      const label = { context: "1 Context", plan: "2 Plan", write: "3 Write", review: "4 Review" }[s];
      return `<span class="copilot-stepper__step ${cls}">${label}</span>`;
    })
    .join("");
  return `<div class="definition-card definition-knowledge-card">
    <div class="definition-head">
      <b>Copilot testcase session</b>
      <span class="detail">Focus term: <code>${esc(inboxFocusTerm(inbox)?.term || "—")}</code></span>
    </div>
    <p class="detail">ALEX đọc spec → Copilot hiểu footnote (*n) → plan → viết testcase → bạn review &amp; apply.</p>
    ${renderM365KnowledgeBanner()}
    ${renderM365EntitlementBanner(state.m365Status, { compact: true })}
    ${renderCopilotUnderstandingBanner(pack, plan)}
    <div class="copilot-stepper">${stepper}</div>
    <textarea id="definition-workbench-note" class="clarify-box definition-query-box" placeholder="Ghi chú / trả lời câu hỏi Copilot (range, ý nghĩa signal, footnote *1…)">${esc(engineerNote)}</textarea>
    <div class="definition-workbench-actions">
      <button class="btn secondary" id="btn-copilot-understand-spec" type="button">Hiểu spec (Copilot)</button>
      <button class="btn secondary" id="btn-copilot-write-drafts" type="button" ${m365KnowledgeReady() && step !== "context" ? "" : "disabled"}>Viết testcase</button>
      <button class="btn" id="btn-copilot-apply-selected" type="button" ${diffs.length ? "" : "disabled"}>Apply đã chọn</button>
      <label class="btn secondary upload-label">Ảnh spec<input type="file" id="logic-attachment-upload" multiple accept="image/*,.pdf,.docx,.txt,.xlsx" hidden /></label>
    </div>
    ${attachments.length ? `<div class="definition-attachments detail">${attachments.map((a) => `<div><b>${esc(a.name)}</b> · ${esc(a.kind || "file")}${a.definition_count ? ` · ${esc(String(a.definition_count))} def(s)` : ""}</div>`).join("")}</div>` : ""}
    <div data-copilot-panel="context" ${step === "context" ? "" : "hidden"}>${renderCopilotContextSummary(pack)}</div>
    <div data-copilot-panel="plan" ${step === "plan" ? "" : "hidden"}>${renderCopilotPlanTable(plan)}</div>
    <div data-copilot-panel="write" ${step === "write" ? "" : "hidden"}><p class="detail">Write runs in batches (config: copilot_write_batch_size). NO-OP drafts are retried automatically when copilot_write_retries &gt; 0.</p></div>
    <div data-copilot-panel="review" ${step === "review" ? "" : "hidden"}>${renderCopilotDraftDiffs(diffs)}</div>
    <div class="copilot-followup-box" ${m365KnowledgeReady() ? "" : "hidden"}>
      <label class="detail">Ask Copilot follow-up (same Graph conversation)
        <textarea id="copilot-followup-message" class="clarify-box" rows="3" placeholder="Refine plan or testcase wording…"></textarea>
      </label>
      <div class="review-actions">
        <button type="button" class="btn secondary" id="btn-copilot-followup">Send follow-up</button>
        <button type="button" class="btn secondary" id="btn-copilot-copy-brief">Copy M365 brief</button>
      </div>
      <p id="copilot-followup-status" class="detail"></p>
    </div>
    <div data-definition-query-status class="detail"></div>
  </div>`;
}

function renderVerificationMatrixPanel(matrix, logicId) {
  if (!matrix?.row_count) {
    return `<details class="alex-ref-panel verification-matrix-panel" style="margin-top:0.75rem">
      <summary>Verification patterns (I/O matrix)</summary>
      <p class="detail alex-ref-body">No workbook rows for this logic group yet.</p>
    </details>`;
  }
  const oneRows = (matrix.one_to_many || [])
    .map((row) => {
      const gfp = row.given_fingerprint || "";
      const variants = row.variants || [];
      const allSignals = [...new Set(variants.flatMap((v) => v.then_signals || []))];
      const allCids = [...new Set(variants.flatMap((v) => v.candidate_ids || []))];
      const variantText = variants
        .map((v) => `${esc(v.then_fingerprint || "?")} (${(v.candidate_ids || []).join(", ")})`)
        .join("<br/>");
      return `<tr>
        <td><code>${esc(gfp)}</code></td>
        <td>${variantText}</td>
        <td><button type="button" class="btn secondary btn-inline" data-promote-pattern
          data-logic-id="${esc(logicId)}"
          data-given-fingerprint="${esc(gfp)}"
          data-then-signals="${esc(JSON.stringify(allSignals))}"
          data-candidate-ids="${esc(JSON.stringify(allCids))}">Promote</button></td>
      </tr>`;
    })
    .join("");
  const partialRows = (matrix.partial_assert || [])
    .map((row) => {
      const gfp = row.given_fingerprint || "";
      const missing = (row.missing_then_signals || []).join(", ");
      return `<tr>
        <td><code>${esc(gfp)}</code></td>
        <td>${esc((row.candidate_ids || []).join(", "))}</td>
        <td>${esc(missing)}</td>
        <td><button type="button" class="btn secondary btn-inline" data-promote-pattern
          data-logic-id="${esc(logicId)}"
          data-given-fingerprint="${esc(gfp)}"
          data-then-signals="${esc(JSON.stringify(row.missing_then_signals || []))}"
          data-candidate-ids="${esc(JSON.stringify(row.candidate_ids || []))}"
          data-label="partial">Promote missing Then</button></td>
      </tr>`;
    })
    .join("");
  const saved = (matrix.saved_patterns || [])
    .map(
      (p) =>
        `<li><code>${esc(p.id || p.label || "?")}</code> · Given <code>${esc(p.given_fingerprint || "")}</code> → Then ${esc((p.then_signals || []).join(", "))}</li>`
    )
    .join("");
  return `<details class="alex-ref-panel verification-matrix-panel" style="margin-top:0.75rem" open>
    <summary>Verification patterns · ${matrix.row_count} TC(s) · ${matrix.one_to_many_count || 0} same-input · ${matrix.many_to_one_count || 0} same-output</summary>
    <div class="alex-ref-body">
      ${oneRows ? `<h5 class="detail">Same Given → different Then (1→N)</h5>
      <div class="grid-wrap"><table class="data-grid alex-table verification-matrix-table">
        <thead><tr><th>Given fingerprint</th><th>Then variants</th><th></th></tr></thead>
        <tbody>${oneRows}</tbody>
      </table></div>` : `<p class="detail">No 1→N variants detected.</p>`}
      ${partialRows ? `<h5 class="detail" style="margin-top:0.75rem">Partial assertions (missing Then signals)</h5>
      <div class="grid-wrap"><table class="data-grid alex-table">
        <thead><tr><th>Given</th><th>TC</th><th>Missing Then</th><th></th></tr></thead>
        <tbody>${partialRows}</tbody>
      </table></div>` : ""}
      ${saved ? `<h5 class="detail" style="margin-top:0.75rem">Saved patterns (Copilot context)</h5><ul class="detail">${saved}</ul>` : ""}
      <p class="detail" id="verification-matrix-status"></p>
    </div>
  </details>`;
}

function bindVerificationMatrixPromote(logicId) {
  const statusEl = $("#verification-matrix-status");
  document.querySelectorAll("[data-promote-pattern]").forEach((btn) => {
    btn.onclick = async () => {
      let thenSignals = [];
      let candidateIds = [];
      try {
        thenSignals = JSON.parse(btn.dataset.thenSignals || "[]");
        candidateIds = JSON.parse(btn.dataset.candidateIds || "[]");
      } catch (_) {
        /* ignore */
      }
      const label =
        btn.dataset.label === "partial"
          ? `Partial ${btn.dataset.givenFingerprint || ""}`.slice(0, 60)
          : `Pattern ${btn.dataset.givenFingerprint || ""}`.slice(0, 60);
      if (statusEl) statusEl.textContent = "Saving pattern…";
      btn.disabled = true;
      try {
        await api(`/api/review/promote-verification-pattern?job_id=${encodeURIComponent(state.jobId)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            logic_id: logicId,
            given_fingerprint: btn.dataset.givenFingerprint || "",
            then_signals: thenSignals,
            candidate_ids: candidateIds,
            label,
          }),
        });
        invalidateApiCache(`verify-matrix:${state.jobId}:${logicId}`);
        if (statusEl) statusEl.textContent = "Pattern saved — included in next Copilot context.";
        await renderLogicReview({ skipSummary: true });
      } catch (e) {
        if (statusEl) statusEl.textContent = e.message;
      } finally {
        btn.disabled = false;
      }
    };
  });
}

function renderDefinitionInbox(inbox, { engineerNote = "", attachments = [], assistStatus = null, logicId = "", copilotSession = null } = {}) {
  const draft = logicId ? readDefinitionDraft(logicId) : null;
  const noteText = draft?.text != null ? draft.text : engineerNote;
  if (!inbox?.terms?.length) return "<p class='detail'>No definition work items for this logic group.</p>";
  const current = inboxFocusTerm(inbox);
  state.inboxFocus[inbox.logic_id] = current?.term || "";
  const defs = (current?.definitions || [])
    .map((d) => {
      const fullSource = formatSourceReadable(d.source) || "unknown source";
      const compactSource = compactSourceLabel(d.source) || fullSource;
      return `<li><b>${esc(d.kind)}</b>${d.match_mode && d.match_mode !== "exact" ? ` · ${esc(d.match_mode)} match` : ""} · <span title="${attrTitle(fullSource)}">${esc(compactSource)}</span> — ${esc(d.definition || "")}</li>`;
    })
    .join("");
  const queryHistory = (inbox.query_history || []).slice().reverse();
  const statusCounts = inbox.terms.reduce(
    (acc, term) => {
      const key = term.resolution === "definition_found"
        ? "resolved"
        : term.resolution === "added_context_found"
          ? "added"
          : "missing";
      acc[key] += 1;
      return acc;
    },
    { resolved: 0, added: 0, missing: 0 }
  );
  const termChips = inbox.terms
    .map((term) => {
      const active = term.term === current?.term;
      return `<button type="button" class="term-chip${active ? " active" : ""}" data-definition-term="${esc(term.term)}">
        <code class="term-chip-name">${esc(term.term)}</code>
      </button>`;
    })
    .join("");
  return `<div class="definition-workbench">
    <aside class="definition-term-list">
      ${renderTermSummaryBrief(statusCounts, inbox.terms.length)}
      <div class="definition-term-chips">${termChips}</div>
      ${inbox.unused_added_definitions?.length ? `<div class="definition-card mini">
        <div class="definition-head"><b>Unused added definitions</b></div>
        <ul class="detail">${inbox.unused_added_definitions
          .map((row) => `<li><code>${esc(row.name)}</code> · ${esc(row.source)}</li>`)
          .join("")}</ul>
      </div>` : ""}
    </aside>
    <div class="definition-panel">
      ${current ? `<div class="definition-term-detail">
        <div class="definition-term-detail__head">
          <code class="definition-term-detail__name">${esc(current.term)}</code>
        </div>
        <p class="definition-term-detail__reason"><b>${esc(reasonCodeLabel(current.reason_code))}</b> · ${esc(current.reason_detail || "")}</p>
        ${defs ? `<ul class="definition-evidence-list detail">${defs}</ul>` : "<p class='detail definition-term-detail__empty'>No trusted definition attached yet.</p>"}
      </div>` : ""}
      ${renderCopilotWorkbench(inbox, { engineerNote: noteText, attachments, logicId, copilotSession })}
      ${queryHistory.length ? `<details class="definition-history-panel">
        <summary>Recent Copilot answers (${queryHistory.length})</summary>
        <div class="definition-history">${queryHistory
          .map((row) => `<div class="history-item">
            <p><b>${esc(row.term || "")}</b> · ${esc(row.question || "")}</p>
            <p>${esc(row.answer || "")}</p>
            ${row.suggested_matches?.length ? `<p class="detail">Matches: ${row.suggested_matches.map((m) => `${m.name} (${m.confidence || "low"})`).join(", ")}</p>` : ""}
            ${row.follow_up_questions?.length ? `<p class="detail">Follow-up: ${esc(row.follow_up_questions[0])}</p>` : ""}
          </div>`)
          .join("")}</div>
      </details>` : ""}
    </div>
  </div>`;
}

function formatIoBlock(text) {
  const raw = String(text ?? "").trim();
  if (!raw) return `<span class="detail">—</span>`;
  return `<pre class="alex-io-pre">${esc(raw)}</pre>`;
}

function renderWorkbookPreviewCards(rows) {
  if (!rows?.length) return "<p class='detail'>No rows to preview.</p>";
  return `<div class="alex-preview-list">${rows
    .map((row) => {
      const statusClass =
        row.review_status === "ready" || row.review_status === "approved"
          ? "high"
          : row.review_status === "blocked"
            ? "error"
            : "warning";
      return `<article class="alex-preview-card">
        <header class="alex-preview-head">
          <div><b>${esc(row.no)}</b> · ${esc(row.event || row.test_function || row.candidate_id)}</div>
          <span class="tag ${statusClass}">${esc(row.review_status || "pending")}</span>
        </header>
        <div class="alex-preview-grid">
          <div class="alex-io-block">
            <h5>Expected input</h5>
            ${formatIoBlock(row.expected_input)}
          </div>
          <div class="alex-io-block">
            <h5>Expected output</h5>
            ${formatIoBlock(row.expected_output)}
          </div>
        </div>
        ${renderEvidenceNavigation(row)}
      </article>`;
    })
    .join("")}</div>`;
}

function workbookColumns(language) {
  const cols = [
    { key: "no", label: "No", editable: false, colClass: "col-no" },
    { key: "candidate_id", label: "TestCase ID", editable: false, colClass: "col-tcid" },
    { key: "test_function", label: "Test Function", editable: true, colClass: "col-fn" },
    { key: "event", label: "Event", editable: true },
    { key: "use_case", label: "UseCase", editable: true, multiline: true, colClass: "col-usecase" },
    { key: "operation", label: "Operation", editable: true, multiline: true, colClass: "col-op" },
    {
      key: "expected_input",
      label: "Expected input",
      editable: true,
      multiline: true,
      colClass: "col-io",
    },
    {
      key: "expected_output",
      label: "Expected output",
      editable: true,
      multiline: true,
      colClass: "col-io",
    },
    { key: "review_status", label: "Status", editable: true, colClass: "col-status" },
    {
      key: "engineer_confirmation_required",
      label: "Needs answer",
      editable: true,
      colClass: "col-needs-answer",
    },
  ];
  if (language !== "EN") {
    cols.push({
      key: "open_questions",
      label: "Open questions",
      editable: true,
      multiline: true,
      colClass: "col-open-questions",
    });
  }
  return cols;
}

function currentFocusRow(rows, scope) {
  if (!rows?.length) return null;
  const selected = state.workbookFocus[scope];
  return rows.find((row) => row.candidate_id === selected) || rows[0];
}

async function saveWorkbookRow(payload) {
  const res = await api(`/api/review/workbench-row?job_id=${encodeURIComponent(state.jobId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res?.bundle_version != null) state.bundleVersion = res.bundle_version;
  return res;
}

function applyAuthTopbar(user, enabled) {
  const wrap = $("#topbar-user-wrap");
  const nameEl = $("#stat-user");
  const signOut = $("#btn-sign-out");
  if (!wrap || !nameEl || !signOut) return;
  if (enabled && user?.username) {
    wrap.hidden = false;
    signOut.hidden = false;
    nameEl.textContent = user.username;
  } else {
    wrap.hidden = true;
    signOut.hidden = true;
    nameEl.textContent = "—";
  }
}

async function ensureAuthenticated() {
  const res = await fetch("/api/auth/me", { credentials: "same-origin" });
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("Not authenticated");
  }
  const me = await res.json();
  state.teamAuthEnabled = me.enabled !== false;
  state.currentUser = me;
  applyAuthTopbar(me, state.teamAuthEnabled);
}

async function signOut() {
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch (_) {
    /* redirect anyway */
  }
  window.location.href = "/login";
}

async function loadAppConfig() {
  try {
    state.appConfig = await api("/api/app-config");
  } catch {
    state.appConfig = { features: { validator: false, add_clone_tc: false }, export: { strict: false } };
  }
}

function formatOllamaTopbarStatus(_st) {
  return "Off";
}

function formatM365TopbarStatus(st) {
  if (!st) return "Loading…";
  if (st.api_ready || st.connected) {
    const who = st.display_name || st.user_principal || "M365";
    const short = String(who).trim().split(/\s+/)[0] || "User";
    return `Signed In · ${short}`;
  }
  if (st.client_id_configured === false) return "Needs Client ID";
  if (st.client_id_configured) return "Sign In Required";
  return "Not Configured";
}

function applyOllamaTopbarStatus(_st) {
  const el = $("#stat-ollama");
  if (!el) return;
  el.textContent = "Off";
  setTopbarChipState("chip-ollama", { warn: true, ok: false });
}

function applyM365TopbarStatus(st) {
  const el = $("#stat-m365");
  if (!el) return;
  el.textContent = formatM365TopbarStatus(st);
  const ready = !!(st?.api_ready || st?.connected);
  setTopbarChipState("chip-m365", {
    ok: ready,
    err: !ready && !st?.client_id_configured,
    warn: !ready && !!st?.client_id_configured,
  });
}

async function loadOllamaStatus() {
  const el = $("#stat-ollama");
  if (!el) return;
  try {
    const st = await api("/api/llm/status?light=1");
    state.ollamaStatus = st;
    applyOllamaTopbarStatus(st);
  } catch {
    el.textContent = "Unavailable";
    setTopbarChipState("chip-ollama", { err: true });
  }
}

function refreshServiceStatusNow() {
  loadOllamaStatus().catch(() => {});
  loadM365Status().catch(() => {});
}

function startServiceStatusPolling() {
  if (state.serviceStatusTimer) clearInterval(state.serviceStatusTimer);
  refreshServiceStatusNow();
  state.serviceStatusTimer = setInterval(() => refreshServiceStatusNow(), 12000);
}

function stopServiceStatusPolling() {
  if (state.serviceStatusTimer) {
    clearInterval(state.serviceStatusTimer);
    state.serviceStatusTimer = null;
  }
}

function m365ApiSignedIn() {
  const st = state.m365Status || {};
  return !!(st.api_ready || st.connected);
}

function m365KnowledgeReady() {
  const st = state.m365Status || {};
  if (!m365ApiSignedIn()) return false;
  if (st.copilot_chat_entitled === false) return false;
  return st.copilot_api_probe_ok === true;
}

function m365KnowledgeBlockReason() {
  const st = state.m365Status || {};
  if (!m365ApiSignedIn()) {
    if (st.client_id_configured) return "Chưa sign in M365 — mở tab Review → AI sign-in → Sign in.";
    return "Chưa cấu hình M365 Client ID — liên hệ IT hoặc nhập trên tab Review.";
  }
  if (st.copilot_chat_entitled === false) {
    if (st.not_entitled_reason === "msa") {
      return "Tài khoản Microsoft cá nhân — Copilot API không khả dụng. Dùng tài khoản công ty có license Copilot.";
    }
    return "Tài khoản chưa có license Microsoft 365 Copilot — liên hệ IT.";
  }
  if (st.copilot_api_probe_ok === false) {
    return (
      st.copilot_api_probe_error ||
      "Copilot API probe thất bại — tab Review → Test Copilot API (hoặc Authorize Copilot API nếu chưa authorize)."
    );
  }
  if (st.copilot_scopes_granted === false) {
    return "Đã sign in nhưng chưa authorize Copilot API — tab Review → Authorize Copilot API.";
  }
  if (st.copilot_api_probe_ok !== true) {
    return "Đang chờ xác nhận Copilot API — tab Review → Test Copilot API (hoặc đợi vài giây sau sign in).";
  }
  return "";
}

function syncTestCodeCopilotControls() {
  const btn = $("#btn-testcode-copilot");
  if (!btn || btn.dataset.busy === "1") return;
  const ready = m365KnowledgeReady();
  btn.disabled = !ready;
  btn.title = ready ? "Gọi M365 Copilot tự động" : m365KnowledgeBlockReason();
  const hint = $("#testcode-copilot-hint");
  if (!hint) return;
  if (ready) {
    hint.hidden = true;
    hint.textContent = "";
  } else {
    hint.hidden = false;
    hint.textContent = m365KnowledgeBlockReason();
  }
}

async function runM365CopilotProbe() {
  setM365AuthMessage("Testing Copilot API (Graph conversation)…");
  const res = await api("/api/m365/copilot-probe", { method: "POST" });
  state.m365Status = { ...(state.m365Status || {}), ...res };
  applyM365TopbarStatus(state.m365Status);
  refreshReviewM365Tile();
  if (res.ok) {
    const preview = res.reply_preview ? ` — ${res.reply_preview.slice(0, 80)}` : "";
    setM365AuthMessage(`Copilot API OK${preview}`);
    return res;
  }
  const cat = res.error_category || "error";
  const action = res.user_action ? ` ${res.user_action}` : "";
  setM365AuthMessage(`[${cat}] ${res.error || res.entitlement_hint || "Copilot API probe failed"}.${action}`);
  return res;
}

function assistEnabled() {
  return m365KnowledgeReady();
}

function parseStatusClass(status) {
  if (status === "ok") return "high";
  if (status === "partial") return "warn";
  return "error";
}

function renderKnowledgeReconciliationPanel(knowledgeApply) {
  if (!knowledgeApply || knowledgeApply.status === "none") return "";
  const rec = knowledgeApply.reconciliation || {};
  const summary = rec.summary || {};
  const diffs = knowledgeApply.diffs || [];
  const pending = knowledgeApply.status === "pending";
  if (!pending && !diffs.length) return "";

  const groups = ["update_existing", "add_new", "retire", "needs_review"];
  const summaryHtml = groups
    .filter((g) => summary[g])
    .map(
      (g) =>
        `<span class="tag ${g === "needs_review" ? "error" : "warning"}">${esc(g.replace(/_/g, " "))} ${summary[g]}</span>`
    )
    .join(" ");

  const actions = rec.actions || [];
  const diffRows = diffs
    .map((d) => {
      const action = actions.find((a) => a.patch_index === d.patch_index);
      const act = action?.action || d.action || "update_existing";
      const comply = d.logic_comply || "—";
      const complyCls = comply === "pass" ? "high" : comply === "fail" ? "error" : "warning";
      const defaultOn = d.default_selected !== false;
      return `<article class="knowledge-diff-row" data-patch-index="${d.patch_index}">
        <header class="knowledge-diff-row__head">
          ${
            pending
              ? `<label class="knowledge-diff-check"><input type="checkbox" class="knowledge-patch-check" data-patch-index="${d.patch_index}" ${defaultOn ? "checked" : ""} /> Apply</label>`
              : ""
          }
          <span class="tag ${complyCls}" title="logic_compliance preview">${esc(comply)}</span>
          <span class="tag">${esc(act)}</span>
          <code>${esc(d.candidate_id || "new")}</code>
        </header>
        ${d.reason ? `<p class="detail">${esc(d.reason)}</p>` : ""}
        ${(d.missing_signals || []).length ? `<p class="detail">Still missing: ${esc(d.missing_signals.join(", "))}</p>` : ""}
        <div class="knowledge-diff-grid">
          <div class="alex-io-block"><h5>Before</h5>${formatIoBlock(d.before_expected_input || "—")}</div>
          <div class="alex-io-block"><h5>After (preview)</h5>${formatIoBlock(d.after_expected_input || "—")}</div>
        </div>
      </article>`;
    })
    .join("");

  return `<section class="definition-card knowledge-reconciliation-card" id="knowledge-reconciliation-panel">
    <div class="definition-head">
      <b>AI patch review</b>
      <span class="tag ${pending ? "warning" : "high"}">${esc(knowledgeApply.status || "unknown")}</span>
      ${knowledgeApply.provider ? `<span class="detail">${esc(knowledgeApply.provider)}</span>` : ""}
    </div>
    ${summaryHtml ? `<div class="knowledge-rec-summary">${summaryHtml}</div>` : ""}
    <div class="knowledge-diff-list">${diffRows || "<p class='detail'>No patch diffs.</p>"}</div>
    ${
      pending
        ? `<div class="definition-workbench-actions">
      <button class="btn" id="btn-knowledge-apply-selected" type="button">Apply selected</button>
      <button class="btn secondary" id="btn-knowledge-reject-all" type="button">Reject all</button>
    </div>
    <p id="knowledge-reconcile-status" class="detail"></p>`
        : ""
    }
  </section>`;
}

function renderHypothesisReviewPanel(session) {
  if (!session?.hypotheses?.length) return "";
  const latest = session.hypotheses[session.hypotheses.length - 1];
  const hyp = latest.hypothesis || {};
  const validation = latest.validation || {};
  const claims = hyp.claims || [];
  const openQs = hyp.open_questions || [];
  const patchPlan = hyp.testcase_patch_plan || [];
  if (!claims.length && !openQs.length && !patchPlan.length) return "";

  const claimsHtml = claims
    .map(
      (c, i) => `<li class="hypothesis-claim">
      <label class="hypothesis-claim-label">
        <input type="checkbox" class="hypothesis-claim-check" data-claim-index="${i}" checked />
        <code>${esc(c.term || c.signal || "")}</code> — ${esc(c.definition || c.claim || "")}
      </label>
      ${
        (c.citations || []).length
          ? `<span class="detail" title="${attrTitle(formatSourceReadable(c.citations[0]))}">${esc(compactSourceLabel(c.citations[0]) || "cited")}</span>`
          : ""
      }
    </li>`
    )
    .join("");

  const openHtml = openQs
    .map((q) => `<li>${esc(q.question || q)}</li>`)
    .join("");
  const patchHtml = patchPlan
    .map(
      (p) =>
        `<li><span class="tag">${esc(p.action || "")}</span> <code>${esc(p.candidate_id || "new")}</code> — ${esc(p.reason || p.note || "")}</li>`
    )
    .join("");

  return `<section class="definition-card hypothesis-review-card" id="hypothesis-review-panel">
    <div class="definition-head">
      <b>Hypothesis review</b>
      <span class="tag ${validation.ok ? "high" : "error"}">${validation.ok ? "valid" : "needs fix"}</span>
    </div>
    ${validation.errors?.length ? `<ul class="detail err">${validation.errors.map((e) => `<li>${esc(e)}</li>`).join("")}</ul>` : ""}
    ${claims.length ? `<h5>Claims</h5><ul class="hypothesis-claim-list">${claimsHtml}</ul>` : ""}
    ${openQs.length ? `<h5>Open questions</h5><ul class="detail">${openHtml}</ul>` : ""}
    ${patchPlan.length ? `<h5>Testcase patch plan</h5><ul class="detail">${patchHtml}</ul>` : ""}
    ${
      claims.length
        ? `<div class="definition-workbench-actions">
      <button class="btn secondary" id="btn-hypothesis-accept-claims" type="button">Accept selected claims</button>
      <button class="btn ghost" id="btn-hypothesis-paste-json" type="button">Paste hypothesis JSON</button>
    </div>
    <p id="hypothesis-review-status" class="detail"></p>`
        : ""
    }
  </section>`;
}

function formatLocalApplyStatus(res) {
  if (!res.ok && res.apply_error) return res.apply_error;
  const terms = (res.applied_terms || []).join(", ");
  let msg = `Applied locally${terms ? `: ${terms}` : ""}.`;
  if (res.definitions_applied_to_candidates) {
    msg += ` Updated ${res.definitions_applied_to_candidates} test case(s).`;
  }
  return msg + formatUnderstandingLoopStatus(res.understanding_loop);
}

function formatKnowledgeApplyStatus(res, provider) {
  if (res.apply_error && !res.apply_ok) {
    const tried = (res.providers_tried || []).length
      ? ` Tried: ${res.providers_tried.join(", ")}.`
      : "";
    return `${res.apply_error}${tried}`;
  }
  const who = res.apply_provider || provider || "AI";
  const loopSuffix = formatUnderstandingLoopStatus(res.understanding_loop);
  if (res.apply_preview) {
    const pending = res.pending_patches || 0;
    const rec = res.reconciliation?.summary || {};
    let msg = `${who}: ${pending} patch(es) ready for review.`;
    if (rec.update_existing) msg += ` ${rec.update_existing} update(s).`;
    if (rec.add_new) msg += ` ${rec.add_new} new.`;
    if (res.definitions_applied_to_candidates) {
      msg += ` Engineer definitions refreshed ${res.definitions_applied_to_candidates} TC(s).`;
    }
    return msg + loopSuffix;
  }
  let msg = `${who}: updated ${res.candidates_updated || 0} test case(s).`;
  if (res.failures_remaining) msg += ` ${res.failures_remaining} validation issue(s) remain.`;
  if ((res.providers_tried || []).length) msg += ` (after trying ${res.providers_tried.join(", ")})`;
  if (res.definitions_applied_to_candidates && !res.apply_preview) {
    msg += ` Definitions applied to ${res.definitions_applied_to_candidates} TC(s).`;
  }
  return msg + loopSuffix;
}

function formatUnderstandingLoopStatus(loop) {
  if (!loop || loop.ok === false) return "";
  const pct = loop.understanding_percent;
  const gates = loop.gate_counts || {};
  const ready = gates.ready ?? 0;
  const llm = gates.needs_llm ?? 0;
  const eng = gates.needs_engineer ?? 0;
  let msg = " Understanding refreshed";
  if (typeof pct === "number") msg += ` (${pct}% spec understood)`;
  msg += ` — gate: ${ready} ready, ${llm} LLM, ${eng} engineer`;
  if (loop.unresolved_cleared) msg += `; ${loop.unresolved_cleared} unresolved ref(s) cleared`;
  if (loop.footnote_materialized) msg += `; ${loop.footnote_materialized} footnote logic attached`;
  return msg + ".";
}

function sleepMs(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function m365ReviewStatusText(st) {
  if (!st) return "Loading…";
  if (st.api_ready || st.connected) {
    const who = st.display_name || st.user_principal || "M365";
    if (st.copilot_chat_entitled === false) {
      const reason =
        st.not_entitled_reason === "msa"
          ? "personal Microsoft account — Copilot Chat API blocked"
          : "no Microsoft 365 Copilot license assigned";
      return `Signed in: ${who} · ${reason}`;
    }
    if (st.copilot_api_probe_ok === true) {
      return `Signed in: ${who} · Copilot API OK`;
    }
    if (st.copilot_api_probe_ok === false) {
      const hint = st.copilot_api_probe_error || "Copilot API probe failed";
      return `Signed in: ${who} · ${hint.slice(0, 80)}`;
    }
    return `Signed in: ${who} · click Test Copilot API`;
  }
  if (st.client_id_configured) {
    if (st.server_managed_setup && st.client_secret_configured === false) {
      return "Azure app configured — add M365_CLIENT_SECRET to .env, restart ./dev.sh, then Sign in.";
    }
    if (st.server_managed_setup) return "Company Azure app ready. Click Sign in.";
    return "Client ID saved. Click Sign in.";
  }
  if (st.server_managed_setup) return "Azure app misconfigured — contact IT.";
  return "Need Application (client) ID from IT (Azure app registration).";
}

function setM365AuthMessage(msg) {
  const review = $("#review-m365-status");
  if (review) review.textContent = msg;
  const logic = $("#logic-copilot-status");
  if (logic) logic.textContent = msg;
}

function refreshReviewM365Tile() {
  const el = $("#review-m365-status");
  if (el) el.textContent = m365ReviewStatusText(state.m365Status);
  const badge = $("#m365-auth-badge");
  if (badge) badge.innerHTML = m365AuthBadge(state.m365Status);
  const signOut = $("#btn-m365-disconnect");
  const signIn = $("#btn-m365-connect");
  const probeBtn = $("#btn-m365-copilot-probe");
  const copilotAuthBtn = $("#btn-m365-copilot-auth");
  const signedIn = m365ApiSignedIn();
  if (signOut) signOut.hidden = !signedIn;
  if (signIn) signIn.disabled = signedIn || !!state.m365LoginInProgress;
  if (probeBtn) probeBtn.hidden = !signedIn;
  if (copilotAuthBtn) {
    copilotAuthBtn.hidden = !signedIn;
    copilotAuthBtn.disabled = !!state.m365LoginInProgress || !!state.m365Status?.copilot_scopes_granted;
  }
}

function refreshGithubAuthBadge(copilot) {
  const badge = $("#github-auth-badge");
  if (badge) badge.innerHTML = githubAuthBadge(copilot || state.copilot.status);
}

async function loadM365Status() {
  try {
    const st = await api("/api/m365/status");
    state.m365Status = st;
    applyM365TopbarStatus(st);
    applyM365ExpiredBanner(st);
  } catch {
    const el = $("#stat-m365");
    if (el) el.textContent = "Unavailable";
    setTopbarChipState("chip-m365", { err: true });
    applyM365ExpiredBanner(null);
  }
  refreshReviewM365Tile();
  populateM365SetupForm();
  syncTestCodeCopilotControls();
}

function populateM365SetupForm() {
  const st = state.m365Status || {};
  const cid = $("#m365-setup-client-id");
  const tid = $("#m365-setup-tenant-id");
  if (cid && st.local_client_id && !cid.value) cid.value = st.local_client_id;
  if (tid && st.local_tenant_id) {
    if (tid.value === "common" && st.local_tenant_id !== "common") {
      tid.value = st.local_tenant_id;
    } else if (!tid.value) {
      tid.value = st.local_tenant_id;
    }
  }
}

function renderM365SetupFields(m) {
  if (m.server_managed_setup) {
    const tid = m.tenant_id_preview || m.tenant_id || "";
    const cid = m.client_id_preview || "";
    const bits = [];
    if (cid) bits.push(`app ${esc(cid)}`);
    if (tid) bits.push(`tenant ${esc(tid)}`);
    const meta = bits.length ? ` (${bits.join(" · ")})` : "";
    return `<p class="detail">Azure app configured by IT${meta}. Sign in with your <b>work account</b> — no Client ID entry needed.</p>`;
  }
  return `<label class="detail login-compact-label">Application (client) ID
            <input type="text" id="m365-setup-client-id" class="clarify-box" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" autocomplete="off" />
          </label>
          <label class="detail login-compact-label">Tenant (Directory ID)
            <input type="text" id="m365-setup-tenant-id" class="clarify-box" placeholder="yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy" autocomplete="off" />
          </label>`;
}

function renderM365SetupActions(m) {
  const probeBtn = `<button type="button" class="btn secondary" id="btn-m365-copilot-probe" hidden>Test Copilot API</button>`;
  const copilotAuthBtn = `<button type="button" class="btn secondary" id="btn-m365-copilot-auth" hidden>Authorize Copilot API</button>`;
  if (m.server_managed_setup) {
    return `<div class="review-actions" style="margin-top:0.5rem">
            <button type="button" class="btn secondary" id="btn-m365-connect">Sign in</button>
            ${copilotAuthBtn}
            ${probeBtn}
            <button type="button" class="btn secondary" id="btn-m365-disconnect" hidden>Sign out</button>
          </div>`;
  }
  return `<div class="review-actions" style="margin-top:0.5rem">
            <button type="button" class="btn secondary" id="btn-m365-save-setup">Save</button>
            <button type="button" class="btn secondary" id="btn-m365-connect">Sign in</button>
            ${copilotAuthBtn}
            ${probeBtn}
            <button type="button" class="btn secondary" id="btn-m365-disconnect" hidden>Sign out</button>
            <button type="button" class="btn secondary" id="btn-m365-reset-setup">Clear</button>
          </div>`;
}

function renderReviewLoginHub(copilot) {
  const m = state.m365Status || {};
  const open = isAiSigninOpen();
  const copilotOn = copilotFeatureEnabled();
  const summaryHint = copilotOn
    ? "Optional · click to show Copilot / M365"
    : "Optional · M365 sign-in (GitHub Copilot CLI disabled on this server)";
  const githubTile = copilotOn
    ? `<article class="login-tile">
          <div class="login-tile-head">
            ${icon("github", "alex-icon--brand")}
            <h4>GitHub Copilot CLI</h4>
            <span id="github-auth-badge">${githubAuthBadge(copilot)}</span>
          </div>
          <div id="copilot-review-status">${copilotStatusHtml(copilot)}</div>
          <div class="review-actions" style="margin-top:0.75rem">
            <button type="button" class="btn secondary" id="btn-copilot-login">Login</button>
            <button type="button" class="btn secondary" id="btn-copilot-check" ${state.copilot.loginCommand?.status === "running" ? "disabled" : ""}>Check</button>
            <button type="button" class="btn secondary" id="btn-copilot-test-prompt" ${state.copilot.loginCommand?.status === "running" ? "disabled" : ""}>Test</button>
          </div>
          <div data-copilot-login style="margin-top:0.5rem"></div>
        </article>`
    : "";
  return `<details class="card login-hub-details" id="ai-signin-details"${open ? " open" : ""}>
      <summary class="login-hub-summary">
        <span class="login-hub-summary__title">AI sign-in</span>
        <span class="login-hub-summary__hint detail">${summaryHint}</span>
      </summary>
      <div class="login-hub-body">
      <div class="login-hub-grid">
        ${githubTile}
        <article class="login-tile">
          <div class="login-tile-head">
            ${icon("microsoft", "alex-icon--brand")}
            <h4>Microsoft 365 Copilot</h4>
            <span id="m365-auth-badge">${m365AuthBadge(m)}</span>
          </div>
          <p id="review-m365-status" class="detail">${esc(m365ReviewStatusText(m))}</p>
          ${renderM365EntitlementBanner(m, { compact: true })}
          ${renderM365SetupFields(m)}
          ${renderM365SetupActions(m)}
          <div id="m365-login-panel" class="m365-login-panel" hidden>
            <p class="detail">1. Open the sign-in page (use this Mac — do not scan QR on phone):
              <a id="m365-login-link" href="https://login.microsoft.com/device" target="_blank" rel="noopener noreferrer">login.microsoft.com/device</a>
              <button type="button" class="btn secondary" id="btn-m365-open-login">Open sign-in page</button>
            </p>
            <p class="detail">2. Enter this code: <code id="m365-login-code" class="m365-user-code">—</code>
              <button type="button" class="btn secondary" id="btn-m365-copy-code">Copy</button></p>
            <p class="detail" id="m365-login-expires">Code expires in —</p>
            <p class="detail" id="m365-login-wait">Waiting for sign-in…</p>
          </div>
          <p id="m365-setup-hint" class="detail err" hidden></p>
        </article>
      </div>
      </div>
    </details>`;
}

function bindReviewLoginHub() {
  const details = $("#ai-signin-details");
  if (details) {
    details.addEventListener("toggle", () => setAiSigninOpen(details.open));
  }
  populateM365SetupForm();
  const m365SaveSetupBtn = $("#btn-m365-save-setup");
  if (m365SaveSetupBtn) {
    m365SaveSetupBtn.onclick = async () => {
      try {
        await saveM365Setup();
        setM365AuthMessage("Client ID saved. Click Sign in.");
        refreshReviewM365Tile();
      } catch (e) {
        showM365SetupError(e.message);
        setM365AuthMessage(e.message);
      }
    };
  }
  const m365ResetSetupBtn = $("#btn-m365-reset-setup");
  if (m365ResetSetupBtn) {
    m365ResetSetupBtn.onclick = async () => {
      try {
        await resetM365Setup();
        setM365AuthMessage("M365 configuration cleared.");
        refreshReviewM365Tile();
      } catch (e) {
        setM365AuthMessage(e.message);
      }
    };
  }
  const m365CopyCodeBtn = $("#btn-m365-copy-code");
  if (m365CopyCodeBtn) {
    m365CopyCodeBtn.onclick = async () => {
      const code = $("#m365-login-code")?.textContent || "";
      if (code && code !== "—") {
        await navigator.clipboard.writeText(code);
        const wait = $("#m365-login-wait");
        if (wait) wait.textContent = "Code copied. Paste it at login.microsoft.com/device";
      }
    };
  }
  const m365OpenLoginBtn = $("#btn-m365-open-login");
  if (m365OpenLoginBtn) {
    m365OpenLoginBtn.onclick = () => {
      const uri = state.m365LoginOpenUri || "https://login.microsoft.com/device";
      window.open(uri, "_blank", "noopener,noreferrer");
    };
  }
  const m365ConnectBtn = $("#btn-m365-connect");
  if (m365ConnectBtn) {
    m365ConnectBtn.onclick = async () => {
      if (state.m365LoginInProgress) return;
      try {
        await signInM365();
        refreshReviewM365Tile();
      } catch (e) {
        setM365AuthMessage(e.message);
      }
    };
  }
  const m365DisconnectBtn = $("#btn-m365-disconnect");
  if (m365DisconnectBtn) {
    m365DisconnectBtn.onclick = async () => {
      try {
        await disconnectM365();
        setM365AuthMessage("Signed out of M365.");
        refreshReviewM365Tile();
      } catch (e) {
        setM365AuthMessage(e.message);
      }
    };
  }
  const m365ProbeBtn = $("#btn-m365-copilot-probe");
  if (m365ProbeBtn) {
    m365ProbeBtn.onclick = async () => {
      m365ProbeBtn.disabled = true;
      try {
        await runM365CopilotProbe();
      } catch (e) {
        setM365AuthMessage(e.message);
      } finally {
        m365ProbeBtn.disabled = false;
      }
    };
  }
  const m365CopilotAuthBtn = $("#btn-m365-copilot-auth");
  if (m365CopilotAuthBtn) {
    m365CopilotAuthBtn.onclick = async () => {
      try {
        await signInM365Copilot();
        refreshReviewM365Tile();
      } catch (e) {
        setM365AuthMessage(e.message);
      }
    };
  }
}

function stopM365LoginTimer() {
  if (state.m365LoginTimer) {
    clearInterval(state.m365LoginTimer);
    state.m365LoginTimer = null;
  }
}

function startM365LoginCountdown(deadlineMs) {
  stopM365LoginTimer();
  const expiresEl = $("#m365-login-expires");
  const tick = () => {
    const left = Math.max(0, Math.ceil((deadlineMs - Date.now()) / 1000));
    if (expiresEl) {
      const mins = Math.floor(left / 60);
      const secs = left % 60;
      expiresEl.textContent = left > 0 ? `Code expires in ${mins}:${String(secs).padStart(2, "0")}` : "Code expired — click Sign in again";
    }
    if (left <= 0) stopM365LoginTimer();
  };
  tick();
  state.m365LoginTimer = setInterval(tick, 1000);
}

function showM365LoginPanel(start) {
  const panel = $("#m365-login-panel");
  const link = $("#m365-login-link");
  const codeEl = $("#m365-login-code");
  const wait = $("#m365-login-wait");
  const uri =
    start.verification_uri_complete ||
    start.verification_uri ||
    "https://login.microsoft.com/device";
  state.m365LoginOpenUri = uri;
  const code = start.user_code || "";
  if (panel) panel.hidden = false;
  if (link) {
    link.href = uri;
    link.textContent = uri.replace(/^https:\/\//, "").split("?")[0];
  }
  if (codeEl) codeEl.textContent = code || "—";
  if (wait) {
    wait.textContent = "Enter the code on this Mac, then approve sign-in. Do not click Sign in again.";
  }
  const deadline = Date.now() + Number(start.expires_in || 900) * 1000;
  startM365LoginCountdown(deadline);
  state.m365LoginInProgress = true;
  refreshReviewM365Tile();
}

function hideM365LoginPanel() {
  const panel = $("#m365-login-panel");
  if (panel) panel.hidden = true;
  stopM365LoginTimer();
  state.m365LoginInProgress = false;
  state.m365LoginOpenUri = null;
  refreshReviewM365Tile();
}

async function cancelM365Login() {
  try {
    await api("/api/m365/login/cancel", { method: "POST" });
  } catch (_) {
    /* ignore */
  }
}

async function saveM365Setup() {
  const clientId = $("#m365-setup-client-id")?.value?.trim() || "";
  const tenantId = $("#m365-setup-tenant-id")?.value?.trim() || "";
  if (!clientId) throw new Error("Paste the Application (client) ID from Azure.");
  await api("/api/m365/setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, tenant_id: tenantId || "common" }),
  });
  const hint = $("#m365-setup-hint");
  if (hint) {
    hint.hidden = true;
    hint.textContent = "";
  }
  await loadM365Status();
}

async function resetM365Setup() {
  await api("/api/m365/setup/reset", { method: "POST" });
  const inp = $("#m365-setup-client-id");
  const tid = $("#m365-setup-tenant-id");
  if (inp) inp.value = "";
  if (tid) tid.value = "";
  await loadM365Status();
}

function showM365SetupError(message) {
  const hint = $("#m365-setup-hint");
  if (hint) {
    hint.hidden = false;
    hint.textContent = message;
  }
}

async function signInM365Copilot() {
  await loadM365Status();
  if (state.m365Status?.setup_required) {
    throw new Error("Save the M365 Client ID on the Review tab before signing in.");
  }
  if (state.m365LoginInProgress) {
    throw new Error("Sign-in already in progress.");
  }
  const generation = (state.m365SignInGeneration = (state.m365SignInGeneration || 0) + 1);
  setM365AuthMessage("Starting Copilot API authorization (7 Graph scopes)…");
  await cancelM365Login();
  const start = await api("/api/m365/login/copilot-start", { method: "POST" });
  if (generation !== state.m365SignInGeneration) return null;
  showM365LoginPanel(start);
  const intervalMs = Math.max(3, Number(start.interval || 5)) * 1000;
  const deadline = Date.now() + Number(start.expires_in || 900) * 1000;
  await sleepMs(intervalMs);
  while (Date.now() < deadline) {
    if (generation !== state.m365SignInGeneration) {
      hideM365LoginPanel();
      return null;
    }
    const poll = await api("/api/m365/login/poll", { method: "POST" });
    if (poll.ok && poll.status === "completed") {
      hideM365LoginPanel();
      await loadM365Status();
      setM365AuthMessage("Copilot scopes authorized. Running API probe…");
      refreshReviewM365Tile();
      try {
        await runM365CopilotProbe();
      } catch (_) {
        setM365AuthMessage("Authorized — probe failed. Click Test Copilot API.");
      }
      return poll;
    }
    if (poll.status === "failed") {
      hideM365LoginPanel();
      throw new Error(poll.error || "Copilot authorization failed.");
    }
    await sleepMs(poll.interval ? poll.interval * 1000 : intervalMs);
  }
  hideM365LoginPanel();
  throw new Error("Copilot authorization timed out.");
}

async function signInM365() {
  await loadM365Status();
  if (state.m365Status?.setup_required) {
    throw new Error("Save the M365 Client ID on the Review tab before signing in.");
  }
  if (state.m365LoginInProgress) {
    throw new Error("Sign-in already in progress. Enter the code shown below.");
  }
  const generation = (state.m365SignInGeneration = (state.m365SignInGeneration || 0) + 1);
  const pollStatus = (msg) => setM365AuthMessage(msg);
  pollStatus("Starting M365 sign-in…");
  await cancelM365Login();
  let start;
  try {
    start = await api("/api/m365/login/start", { method: "POST" });
  } catch (e) {
    showM365SetupError(e.message || String(e));
    throw e;
  }
  if (generation !== state.m365SignInGeneration) return null;
  showM365LoginPanel(start);
  const code = start.user_code || "";
  pollStatus(`Open sign-in page and enter code ${code} (one attempt only)`);
  const intervalMs = Math.max(3, Number(start.interval || 5)) * 1000;
  const deadline = Date.now() + Number(start.expires_in || 900) * 1000;
  await sleepMs(intervalMs);
  while (Date.now() < deadline) {
    if (generation !== state.m365SignInGeneration) {
      hideM365LoginPanel();
      return null;
    }
    const poll = await api("/api/m365/login/poll", { method: "POST" });
    if (poll.ok && poll.status === "completed") {
      hideM365LoginPanel();
      await loadM365Status();
      pollStatus(`Signed in: ${poll.display_name || "M365 user"}. Đang kiểm tra Copilot API…`);
      refreshReviewM365Tile();
      if (!m365KnowledgeReady()) {
        try {
          await runM365CopilotProbe();
        } catch (_) {
          pollStatus(
            `Signed in: ${poll.display_name || "M365 user"}. Probe chưa OK — tab Review → Test Copilot API.`
          );
        }
      }
      syncTestCodeCopilotControls();
      return poll;
    }
    if (poll.status === "failed") {
      hideM365LoginPanel();
      const msg = poll.error || "M365 sign-in failed.";
      showM365SetupError(msg);
      throw new Error(msg);
    }
    const wait = $("#m365-login-wait");
    if (wait) {
      wait.textContent = `Waiting… enter code ${code} at login.microsoft.com/device`;
    }
    const nextInterval = poll.interval ? poll.interval * 1000 : intervalMs;
    await sleepMs(nextInterval);
  }
  hideM365LoginPanel();
  throw new Error("Sign-in timed out. Click Sign in once and enter the new code immediately.");
}

async function disconnectM365() {
  state.m365SignInGeneration = (state.m365SignInGeneration || 0) + 1;
  await cancelM365Login();
  hideM365LoginPanel();
  await api("/api/m365/disconnect", { method: "POST" });
  await loadM365Status();
}

function featureOn(name) {
  return !!(state.appConfig?.features?.[name]);
}

function renderFieldSourceBadge(row, fieldLabel) {
  const touched = String(row?.ai_touched_fields || "")
    .split(",")
    .map((s) => s.trim());
  const provider = String(row?.ai_provider || "").toLowerCase();
  if (touched.includes(fieldLabel)) {
    if (provider.includes("copilot") || provider.includes("m365")) {
      return `<span class="tag high field-source-badge field-source-badge--copilot">Copilot</span>`;
    }
    return `<span class="tag warning field-source-badge field-source-badge--manual">Manual</span>`;
  }
  return `<span class="tag field-source-badge field-source-badge--auto">Auto</span>`;
}

function workbookFieldLabel(colKey) {
  const map = {
    use_case: "UseCase",
    operation: "Operation",
    expected_input: "ExpectedInput",
    expected_output: "ExpectedOutput",
  };
  return map[colKey] || "";
}

function fieldHighlightClass(row, fieldLabel) {
  const touched = String(row?.ai_touched_fields || "")
    .split(",")
    .map((s) => s.trim());
  if (!touched.includes(fieldLabel)) return "";
  const provider = String(row?.ai_provider || "").toLowerCase();
  return provider.includes("copilot") || provider.includes("m365")
    ? "field-copilot-changed"
    : "field-manual-changed";
}

function renderCopilotRowDiffPanel(diffs, scope) {
  if (!diffs?.length) return "";
  const d = diffs[0];
  return `<div class="copilot-row-diff-panel" id="${scope}-copilot-row-diff">
    <p class="detail"><b>Copilot row preview</b> — ${esc(d.candidate_id || "")}</p>
    <div class="knowledge-diff-grid">
      <div class="alex-io-block"><h5>Operation before</h5>${formatIoBlock(d.before?.operation || "—")}</div>
      <div class="alex-io-block"><h5>Operation after</h5>${formatIoBlock(d.after?.operation || "—")}</div>
      <div class="alex-io-block"><h5>UseCase before</h5>${formatIoBlock(d.before?.use_case || "—")}</div>
      <div class="alex-io-block"><h5>UseCase after</h5>${formatIoBlock(d.after?.use_case || "—")}</div>
      <div class="alex-io-block"><h5>Expected input before</h5>${formatIoBlock(d.before?.expected_input || "—")}</div>
      <div class="alex-io-block"><h5>Expected input after</h5>${formatIoBlock(d.after?.expected_input || "—")}</div>
      <div class="alex-io-block"><h5>Expected output before</h5>${formatIoBlock(d.before?.expected_output || "—")}</div>
      <div class="alex-io-block"><h5>Expected output after</h5>${formatIoBlock(d.after?.expected_output || "—")}</div>
    </div>
    <div class="review-actions">
      <button type="button" class="btn" id="${scope}-copilot-row-apply">Apply Copilot row</button>
      <button type="button" class="btn secondary" id="${scope}-copilot-row-discard">Discard</button>
    </div>
  </div>`;
}

function renderValidationBadge(row) {
  const val = row?.validation;
  if (!val || !featureOn("validator")) return "";
  const score = val.quality_score ?? 0;
  const cls = val.ok ? "high" : score >= 50 ? "warning" : "error";
  const tips = (val.issues || [])
    .slice(0, 6)
    .map((i) => `${i.severity}: ${i.message}`)
    .join("\n");
  const logic = row?.logic_compliance || val.logic_compliance;
  const logicBadge =
    logic?.logic_comply && logic.logic_comply !== "pass"
      ? `<span class="tag warning io-quality-badge" title="${attrTitle(
          `Missing: ${(logic.missing_signals || []).join(", ")}`
        )}">Logic ${logic.logic_comply}</span>`
      : logic?.logic_comply === "pass"
        ? `<span class="tag high io-quality-badge">Logic ok</span>`
        : "";
  return `<span class="tag ${cls} io-quality-badge" title="${attrTitle(tips || val.summary || "")}">I/O ${score}</span>${logicBadge}`;
}

function renderTermRoleHint(row) {
  if (!featureOn("term_roles")) return "";
  const roles = state.bundle?.term_roles || {};
  const ctrl = row?.control_name;
  if (!ctrl) return "";
  const role = (roles[ctrl] || roles[String(ctrl).toUpperCase()] || {}).role;
  if (!role) return "";
  return `<span class="tag" title="Term role from spec index">${esc(ctrl)}: ${esc(role)}</span>`;
}

async function createTestCandidate({ logic_id = "", control_name = "" } = {}) {
  return api(`/api/review/test-candidates?job_id=${encodeURIComponent(state.jobId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ logic_id: logic_id || null, control_name: control_name || null, template: "blank" }),
  });
}

async function cloneTestCandidate({ source_candidate_id, logic_id = "" } = {}) {
  return api(`/api/review/test-candidates/clone?job_id=${encodeURIComponent(state.jobId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_candidate_id, logic_id: logic_id || null }),
  });
}

async function deleteTestCandidate(candidate_id) {
  return api(
    `/api/review/test-candidates/${encodeURIComponent(candidate_id)}?job_id=${encodeURIComponent(state.jobId)}`,
    { method: "DELETE" }
  );
}

function renderWorkbookTestcaseBar(rows, scope) {
  if (!rows?.length) return "";
  const activeId = currentFocusRow(rows, scope)?.candidate_id;
  return `<div class="tcase-bar tcase-bar--compact" data-tcase-scope="${esc(scope)}" aria-label="Test cases">
    <label class="detail tcase-select-label">Test case (${rows.length})
      <select class="clarify-box tcase-select" data-tcase-select="${esc(scope)}">
        ${rows
          .map((row) => {
            const label = `${row.candidate_id || `Row ${row.no}`} · ${row.event || row.test_function || ""}`.trim();
            return `<option value="${esc(row.candidate_id || "")}" ${row.candidate_id === activeId ? "selected" : ""}>${esc(label)}</option>`;
          })
          .join("")}
      </select>
    </label>
  </div>`;
}

function renderWorkbookFocusEditor(rows, { language = "EN", scope = "export", title = "Test case editor" } = {}) {
  const baseRow = currentFocusRow(rows, scope);
  if (!baseRow) return "<p class='detail'>No final workbook rows yet.</p>";
  const row = mergeRowWithDraft(baseRow, scope);
  state.workbookFocus[scope] = row.candidate_id;
  const ucCls = fieldHighlightClass(row, "UseCase");
  const opCls = fieldHighlightClass(row, "Operation");
  const inCls = fieldHighlightClass(row, "ExpectedInput");
  const outCls = fieldHighlightClass(row, "ExpectedOutput");
  return `<div class="card workbook-focus-card" id="${scope}-workbook-anchor">
    <div class="focus-head">
      <div>
        <h4>${esc(title)}</h4>
        <p class="detail">${renderValidationBadge(row)} ${renderTermRoleHint(row)}</p>
      </div>
    </div>
    <div class="focus-grid focus-grid--identity">
      <label>TestCase ID<input id="${scope}-focus-candidate_id" class="gtest-input" value="${esc(row.candidate_id || "")}" /></label>
      <label>Test Function<input id="${scope}-focus-test_function" class="gtest-input" value="${esc(row.test_function || "")}" /></label>
      <label>Event<input id="${scope}-focus-event" class="gtest-input" value="${esc(row.event || "")}" /></label>
    </div>
    <div class="focus-grid focus-grid--workbook">
      <label class="focus-span-2">UseCase ${renderFieldSourceBadge(row, "UseCase")}<textarea id="${scope}-focus-use_case" class="focus-text focus-text--wide ${ucCls}">${esc(row.use_case || "")}</textarea></label>
      <label class="focus-span-2">Operation ${renderFieldSourceBadge(row, "Operation")}<textarea id="${scope}-focus-operation" class="focus-text focus-text--wide ${opCls}">${esc(row.operation || "")}</textarea></label>
      <label class="focus-span-2">Expected input ${renderFieldSourceBadge(row, "ExpectedInput")}<textarea id="${scope}-focus-expected_input" class="focus-text focus-text focus-text--io ${inCls}" rows="14">${esc(row.expected_input || "")}</textarea></label>
      <label class="focus-span-2">Expected output ${renderFieldSourceBadge(row, "ExpectedOutput")}<textarea id="${scope}-focus-expected_output" class="focus-text focus-text--io focus-text--io-out ${outCls}" rows="6">${esc(row.expected_output || "")}</textarea></label>
    </div>
    <label class="detail"><input type="checkbox" id="${scope}-focus-remember-io" /> Remember I/O → code variable map on save</label>
    <div class="focus-meta">
      <label>Status
        <select id="${scope}-focus-review_status">
          ${["pending", "review_required", "approved", "blocked", "ready"].map((opt) => `<option value="${opt}" ${String(row.review_status) === opt ? "selected" : ""}>${opt}</option>`).join("")}
        </select>
      </label>
      <label>Needs answer
        <select id="${scope}-focus-engineer_confirmation_required">
          <option value="yes" ${String(row.engineer_confirmation_required).toLowerCase() === "yes" ? "selected" : ""}>yes</option>
          <option value="no" ${String(row.engineer_confirmation_required).toLowerCase() === "no" ? "selected" : ""}>no</option>
        </select>
      </label>
    </div>
    ${renderEvidenceNavigation(row)}
    ${language !== "EN" ? `<label>Open questions<textarea id="${scope}-focus-open_questions" class="focus-text small">${esc(row.open_questions || "")}</textarea></label>` : ""}
    <div class="review-actions workbook-focus-actions">
      <button class="btn" id="${scope}-focus-save">Save row</button>
      <button type="button" class="btn secondary" id="${scope}-focus-open-testcode">Open in Test Code</button>
      ${
        assistEnabled()
          ? `<button type="button" class="btn secondary" id="${scope}-focus-improve-io">Improve I/O (AI)</button>
             <button type="button" class="btn secondary" id="${scope}-focus-copilot-row">Copilot improve row</button>`
          : ""
      }
      ${
        featureOn("add_clone_tc")
          ? `<button type="button" class="btn secondary" id="${scope}-focus-add">+ Add test case</button>
      <button type="button" class="btn secondary" id="${scope}-focus-clone">Clone</button>
      <button type="button" class="btn secondary" id="${scope}-focus-delete">Delete</button>`
          : ""
      }
    </div>
    <div id="${scope}-copilot-row-diff-slot">${state.copilotRowDraft?.[scope]?.candidate_id === row.candidate_id ? renderCopilotRowDiffPanel(state.copilotRowDraft[scope].diffs, scope) : ""}</div>
  </div>`;
}

function renderEvidenceNavigation(row) {
  const binding = row?.evidence_binding || {};
  const logicButtons = (binding.logic_blocks || []).map((item) => `
    <button class="btn secondary btn-inline nav-chip" data-nav-logic="${esc(item.id || "")}">
      Logic · ${esc(item.name || item.id || "logic")}
    </button>
  `).join("");
  const transitionButtons = (binding.transitions || []).map((item, idx) => `
    <button class="btn secondary btn-inline nav-chip" data-nav-transition="${idx}">
      Transition · ${esc(item.from_state || "?")} → ${esc(item.to_state || "?")}
    </button>
  `).join("");
  const outputButtons = (binding.state_outputs || []).map((item, idx) => `
    <button class="btn secondary btn-inline nav-chip" data-nav-output="${idx}">
      Output · ${esc(item.state || "?")}
    </button>
  `).join("");
  if (!logicButtons && !transitionButtons && !outputButtons) return "";
  return `<details class="alex-ev-notes alex-ev-notes--nav">
    <summary class="alex-ev-notes__summary">Jump to source</summary>
    <div class="alex-ev-notes__body evidence-nav-card">
      <div class="evidence-nav-groups">
      ${logicButtons ? `<div><div class="detail evidence-nav-label">Logic</div><div class="evidence-nav-actions">${logicButtons}</div></div>` : ""}
      ${transitionButtons ? `<div><div class="detail evidence-nav-label">Transitions</div><div class="evidence-nav-actions">${transitionButtons}</div></div>` : ""}
      ${outputButtons ? `<div><div class="detail evidence-nav-label">Outputs</div><div class="evidence-nav-actions">${outputButtons}</div></div>` : ""}
      </div>
    </div>
  </details>`;
}

function renderWorkbookCellPreview(value, { maxLen = 140 } = {}) {
  const raw = String(value ?? "").trim();
  if (!raw) return `<span class="detail">—</span>`;
  const short = raw.length > maxLen ? `${raw.slice(0, maxLen)}…` : raw;
  return `<span class="wb-cell-preview" title="${attrTitle(raw)}">${esc(short)}</span>`;
}

function renderWorkbookValue(row, col, editable, rowIndex, { spreadsheet = false } = {}) {
  const value = row[col.key] ?? "";
  if (!editable || !col.editable) {
    if (col.key === "expected_input" || col.key === "expected_output") {
      return spreadsheet ? renderWorkbookCellPreview(value, { maxLen: 1200 }) : formatIoBlock(value);
    }
    return esc(value);
  }
  if (spreadsheet && col.multiline) {
    const maxLen =
      col.key === "expected_input" || col.key === "expected_output"
        ? 800
        : col.key === "use_case" || col.key === "operation"
          ? 400
          : 220;
    return renderWorkbookCellPreview(value, { maxLen });
  }
  if (col.key === "review_status") {
    const options = ["pending", "review_required", "approved", "blocked", "ready"];
    return `<select data-row-edit="${rowIndex}" data-field="${col.key}">${options
      .map((opt) => `<option value="${opt}" ${String(value) === opt ? "selected" : ""}>${opt}</option>`)
      .join("")}</select>`;
  }
  if (col.key === "engineer_confirmation_required") {
    return `<select data-row-edit="${rowIndex}" data-field="${col.key}">
      <option value="yes" ${String(value).toLowerCase() === "yes" ? "selected" : ""}>yes</option>
      <option value="no" ${String(value).toLowerCase() === "no" ? "selected" : ""}>no</option>
    </select>`;
  }
  return `<textarea class="inline-edit ${col.multiline ? "multiline" : ""}" data-row-edit="${rowIndex}" data-field="${col.key}">${esc(value)}</textarea>`;
}

const WORKBOOK_SPREADSHEET_COL_WIDTHS = {
  no: "3rem",
  candidate_id: "7.5rem",
  test_function: "9rem",
  event: "9rem",
  use_case: "12%",
  operation: "12%",
  expected_input: "18%",
  expected_output: "18%",
  review_status: "7rem",
  engineer_confirmation_required: "7.75rem",
  open_questions: "11rem",
  save: "4.5rem",
};

function renderWorkbookTable(
  rows,
  { language = "EN", editable = false, tableId = "workbench", spreadsheet = false } = {}
) {
  if (!rows?.length) return "<p class='detail'>No final workbook rows yet.</p>";
  const cols = workbookColumns(language);
  const tableClass = spreadsheet ? "data-grid workbook-grid workbook-grid--spreadsheet" : "data-grid workbook-grid";
  const colgroup = spreadsheet
    ? `<colgroup>${cols
        .map((col) => {
          const w = WORKBOOK_SPREADSHEET_COL_WIDTHS[col.key];
          return `<col data-col="${esc(col.key)}"${w ? ` style="width:${w}"` : ""} />`;
        })
        .join("")}${editable ? `<col data-col="save" style="width:${WORKBOOK_SPREADSHEET_COL_WIDTHS.save}" />` : ""}</colgroup>`
    : "";
  return `<div class="grid-wrap workbook-grid-wrap">
    <table class="${tableClass}" data-table-id="${esc(tableId)}">${colgroup}<thead><tr>
    ${cols
      .map(
        (col) =>
          `<th class="${col.colClass || ""}" data-col="${esc(col.key)}">${esc(col.label)}${
            spreadsheet ? "" : '<span class="col-resize-grip" aria-hidden="true"></span>'
          }</th>`
      )
      .join("")}
    ${editable ? '<th class="col-save" data-col="save">Save</th>' : ""}
  </tr></thead><tbody>${rows
    .map((row, idx) => `<tr class="workbook-row" data-row-index="${idx}" data-candidate-id="${esc(row.candidate_id || "")}">
      ${cols
        .map((col) => {
          const hi = fieldHighlightClass(row, workbookFieldLabel(col.key));
          return `<td class="${col.colClass || ""}${hi ? ` ${hi}` : ""}" data-col="${esc(col.key)}">${renderWorkbookValue(row, col, editable, idx, {
              spreadsheet,
            })}</td>`;
        })
        .join("")}
      ${editable ? `<td class="col-save" data-col="save"><button class="btn secondary btn-row-save" data-row-save="${idx}">Save</button></td>` : ""}
    </tr>`)
    .join("")}</tbody></table></div>`;
}

function bindWorkbookColumnResize(tableId) {
  const table = document.querySelector(`table.workbook-grid[data-table-id="${tableId}"]`);
  if (!table) return;
  table.querySelectorAll("thead th .col-resize-grip").forEach((grip) => {
    const th = grip.parentElement;
    if (!th || th.dataset.col === "save") return;
    grip.onmousedown = (e) => {
      e.preventDefault();
      const startX = e.clientX;
      const startW = th.offsetWidth;
      const colKey = th.dataset.col;
      const onMove = (ev) => {
        const w = Math.max(48, startW + (ev.clientX - startX));
        th.style.width = `${w}px`;
        table.querySelectorAll(`td[data-col="${colKey}"]`).forEach((td) => {
          td.style.width = `${w}px`;
        });
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    };
  });
}

function bindCopilotRowDiffActions(scope, rows, onReload, statusElSelector) {
  const pending = state.copilotRowDraft?.[scope];
  const applyBtn = document.getElementById(`${scope}-copilot-row-apply`);
  const discardBtn = document.getElementById(`${scope}-copilot-row-discard`);
  if (!pending || !applyBtn) return;
  applyBtn.onclick = async () => {
    const statusEl = statusElSelector ? document.querySelector(statusElSelector) : null;
    if (statusEl) statusEl.textContent = "Applying Copilot row…";
    try {
      const res = await api(`/api/review/copilot/apply-row?job_id=${encodeURIComponent(state.jobId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_id: pending.candidate_id,
          draft: pending.draft,
          language: state.exportLanguage || "EN",
        }),
      });
      if (!res.ok) throw new Error(res.error || "Apply failed");
      delete state.copilotRowDraft[scope];
      invalidateApiCache(`workbench:${state.jobId}:${state.exportLanguage || "EN"}`);
      if (statusEl) statusEl.textContent = `Applied Copilot changes to ${pending.candidate_id}.`;
      state.workbookFocus[scope] = pending.candidate_id;
      onReload();
      document.getElementById(`${scope}-workbook-anchor`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      if (statusEl) statusEl.textContent = e.message;
    }
  };
  if (discardBtn) {
    discardBtn.onclick = () => {
      delete state.copilotRowDraft[scope];
      onReload();
    };
  }
}

function bindWorkbookEditors(rows, language, statusElSelector) {
  document.querySelectorAll(".btn-row-save").forEach((btn) => {
    btn.onclick = async () => {
      const idx = Number(btn.dataset.rowSave);
      const row = rows[idx];
      if (!row) return;
      const payload = {
        candidate_id: row.candidate_id,
        language,
      };
      document.querySelectorAll(`[data-row-edit="${idx}"]`).forEach((input) => {
        payload[input.dataset.field] = input.value;
      });
      const statusEl = statusElSelector ? document.querySelector(statusElSelector) : null;
      if (statusEl) statusEl.textContent = `Saving ${row.candidate_id}…`;
      try {
        await saveWorkbookRow(payload);
        await refreshJobSummary();
        if (statusEl) statusEl.textContent = `${row.candidate_id} saved.`;
      } catch (e) {
        if (statusEl) statusEl.textContent = e.message;
      }
    };
  });
}

function bindWorkbookTestcaseBar(rows, scope, onReload) {
  const select = document.querySelector(`[data-tcase-select="${scope}"]`);
  if (!select) return;
  select.onchange = () => {
    const id = select.value;
    if (!id) return;
    state.workbookFocus[scope] = id;
    if (scope === "testcode") {
      switchTestCodeCandidate(id, rows);
      return;
    }
    onReload();
  };
}

function bindWorkbookTableRowFocus(rows, scope, tableId, onReload) {
  const table = document.querySelector(`table.workbook-grid[data-table-id="${tableId}"]`);
  if (!table) return;
  const activeId = currentFocusRow(rows, scope)?.candidate_id;
  table.querySelectorAll("tbody tr.workbook-row").forEach((tr) => {
    tr.classList.toggle("is-focused", tr.dataset.candidateId === activeId);
    tr.onclick = (e) => {
      if (e.target.closest("input,select,textarea,button,a")) return;
      const id = tr.dataset.candidateId;
      if (!id) return;
      state.workbookFocus[scope] = id;
      onReload();
    };
  });
}

function bindWorkbookFocusEditor(rows, language, scope, onReload, statusElSelector) {
  bindWorkbookTestcaseBar(rows, scope, onReload);
  const saveBtn = document.getElementById(`${scope}-focus-save`);
  if (!saveBtn) return;
  saveBtn.onclick = async () => {
    const row = currentFocusRow(rows, scope);
    if (!row) return;
    const statusEl = statusElSelector ? document.querySelector(statusElSelector) : null;
    if (statusEl) {
      statusEl.dataset.busy = "1";
      statusEl.textContent = `Saving ${row.candidate_id}…`;
    }
    const payload = {
      candidate_id: row.candidate_id,
      new_candidate_id: document.getElementById(`${scope}-focus-candidate_id`)?.value?.trim() || row.candidate_id,
      test_function: document.getElementById(`${scope}-focus-test_function`)?.value ?? "",
      event: document.getElementById(`${scope}-focus-event`)?.value ?? "",
      language,
      use_case: document.getElementById(`${scope}-focus-use_case`)?.value || "",
      operation: document.getElementById(`${scope}-focus-operation`)?.value || "",
      expected_input: document.getElementById(`${scope}-focus-expected_input`)?.value || "",
      expected_output: document.getElementById(`${scope}-focus-expected_output`)?.value || "",
      review_status: document.getElementById(`${scope}-focus-review_status`)?.value || "pending",
      engineer_confirmation_required: document.getElementById(`${scope}-focus-engineer_confirmation_required`)?.value || "yes",
      remember_io_mapping: !!document.getElementById(`${scope}-focus-remember-io`)?.checked,
    };
    if (language !== "EN") {
      payload.open_questions = document.getElementById(`${scope}-focus-open_questions`)?.value || "";
    }
    try {
      const res = await saveWorkbookRow(payload);
      clearWorkbookDraft(scope, row.candidate_id);
      if (res?.candidate_id && res.candidate_id !== row.candidate_id) {
        state.workbookFocus[scope] = res.candidate_id;
      }
      await refreshJobSummary();
      if (statusEl) statusEl.textContent = `${res?.candidate_id || row.candidate_id} saved.`;
      onReload();
    } catch (e) {
      if (statusEl) statusEl.textContent = e.message;
    } finally {
      if (statusEl) delete statusEl.dataset.busy;
    }
  };
  const row = currentFocusRow(rows, scope);
  if (!row) return;
  bindWorkbookDraftAutosave(scope, row.candidate_id, statusElSelector);
  const binding = row.evidence_binding || {};
  document.querySelectorAll("[data-nav-logic]").forEach((btn) => {
    btn.onclick = () => {
      const logicId = btn.dataset.navLogic;
      if (!logicId) return;
      state.selectedLogicId = logicId;
      showPage("logic-review");
    };
  });
  document.querySelectorAll("[data-nav-transition]").forEach((btn) => {
    btn.onclick = () => {
      const idx = Number(btn.dataset.navTransition);
      const transition = (binding.transitions || [])[idx];
      const edge = (binding.diagram_edges || []).find((item) => {
        if (transition?.id && (item.transition_ids || []).includes(transition.id)) return true;
        return (
          String(item.from_state || "") === String(transition?.from_state || "") &&
          String(item.to_state || "") === String(transition?.to_state || "") &&
          String(item.event || "") === String(transition?.event || "")
        );
      });
      state.diagramFocus.state = transition?.to_state || transition?.from_state || null;
      state.diagramFocus.edgeKey = null;
      state.diagramFocus.match = edge || transition || null;
      showPage("diagram-graph");
    };
  });
  document.querySelectorAll("[data-nav-output]").forEach((btn) => {
    btn.onclick = () => {
      const idx = Number(btn.dataset.navOutput);
      const output = (binding.state_outputs || [])[idx];
      state.diagramFocus.state = output?.state || null;
      state.diagramFocus.edgeKey = null;
      state.diagramFocus.match = output ? { to_state: output.state } : null;
      showPage("diagram-graph");
    };
  });

  const openTestCodeBtn = document.getElementById(`${scope}-focus-open-testcode`);
  if (openTestCodeBtn) {
    openTestCodeBtn.onclick = () => {
      const focusRow = currentFocusRow(rows, scope);
      if (!focusRow?.candidate_id) return;
      openTestCodeForCandidate(focusRow.candidate_id, focusRow.logic_id);
    };
  }

  const improveIoBtn = document.getElementById(`${scope}-focus-improve-io`);
  if (improveIoBtn) {
    improveIoBtn.onclick = async () => {
      const focusRow = currentFocusRow(rows, scope);
      if (!focusRow) return;
      const statusEl = statusElSelector ? document.querySelector(statusElSelector) : null;
      if (statusEl) statusEl.textContent = "M365 Copilot improving I/O…";
      try {
        const res = await api(`/api/assist/improve-io?job_id=${encodeURIComponent(state.jobId)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            candidate_id: focusRow.candidate_id,
            expected_input: document.getElementById(`${scope}-focus-expected_input`)?.value || "",
            expected_output: document.getElementById(`${scope}-focus-expected_output`)?.value || "",
            issues: focusRow.validation?.issues || [],
          }),
        });
        if (!res.ok) {
          const action = res.user_action ? ` — ${res.user_action}` : "";
          if (statusEl) statusEl.textContent = `[${res.error_category || "error"}] ${res.error || "M365 Copilot assist failed"}${action}`;
          return;
        }
        const patch = res.result || {};
        if (patch.expected_input) {
          document.getElementById(`${scope}-focus-expected_input`).value = patch.expected_input;
        }
        if (patch.expected_output) {
          document.getElementById(`${scope}-focus-expected_output`).value = patch.expected_output;
        }
        if (statusEl) statusEl.textContent = "Review Copilot suggestion, then Save row.";
      } catch (e) {
        if (statusEl) statusEl.textContent = e.message;
      }
    };
  }

  const copilotRowBtn = document.getElementById(`${scope}-focus-copilot-row`);
  if (copilotRowBtn) {
    copilotRowBtn.onclick = async () => {
      const focusRow = currentFocusRow(rows, scope);
      if (!focusRow?.candidate_id) return;
      const statusEl = statusElSelector ? document.querySelector(statusElSelector) : null;
      if (!m365KnowledgeReady()) {
        if (statusEl) statusEl.textContent = "Authorize Copilot API trước.";
        return;
      }
      try {
        await startM365Task({
          kind: "write_from_row",
          label: `Row ${focusRow.candidate_id}`,
          candidateId: focusRow.candidate_id,
          targetPage: scope === "logic" ? "logic-review" : "export",
          payload: {
            candidate_id: focusRow.candidate_id,
            engineer_note: "",
            language: state.exportLanguage || language || "EN",
            scope,
          },
        });
        if (statusEl) statusEl.textContent = "Copilot row chạy nền — xem banner trên cùng.";
      } catch (e) {
        if (statusEl) statusEl.textContent = e.message;
      }
    };
  }

  bindCopilotRowDiffActions(scope, rows, onReload, statusElSelector);

  if (!featureOn("add_clone_tc")) return;

  const logicId = scope === "logic" ? state.selectedLogicId || row.logic_id || "" : row.logic_id || "";
  const controlName = row.control_name || "";

  const addBtn = document.getElementById(`${scope}-focus-add`);
  if (addBtn) {
    addBtn.onclick = async () => {
      const statusEl = statusElSelector ? document.querySelector(statusElSelector) : null;
      try {
        const res = await createTestCandidate({ logic_id: logicId, control_name: controlName });
        if (res.candidate_id) state.workbookFocus[scope] = res.candidate_id;
        if (statusEl) statusEl.textContent = `Created ${res.candidate_id}.`;
        onReload();
      } catch (e) {
        if (statusEl) statusEl.textContent = e.message;
      }
    };
  }

  const cloneBtn = document.getElementById(`${scope}-focus-clone`);
  if (cloneBtn) {
    cloneBtn.onclick = async () => {
      const current = currentFocusRow(rows, scope);
      if (!current?.candidate_id) return;
      const statusEl = statusElSelector ? document.querySelector(statusElSelector) : null;
      try {
        const res = await cloneTestCandidate({
          source_candidate_id: current.candidate_id,
          logic_id: logicId,
        });
        if (res.candidate_id) state.workbookFocus[scope] = res.candidate_id;
        if (statusEl) statusEl.textContent = `Cloned to ${res.candidate_id}.`;
        onReload();
      } catch (e) {
        if (statusEl) statusEl.textContent = e.message;
      }
    };
  }

  const deleteBtn = document.getElementById(`${scope}-focus-delete`);
  if (deleteBtn) {
    deleteBtn.onclick = async () => {
      const current = currentFocusRow(rows, scope);
      if (!current?.candidate_id) return;
      if (!window.confirm(`Remove test case ${current.candidate_id}?`)) return;
      const statusEl = statusElSelector ? document.querySelector(statusElSelector) : null;
      try {
        await deleteTestCandidate(current.candidate_id);
        state.workbookFocus[scope] = null;
        if (statusEl) statusEl.textContent = `${current.candidate_id} removed.`;
        onReload();
      } catch (e) {
        if (statusEl) statusEl.textContent = e.message;
      }
    };
  }
}

async function fetchWorkbench(language = state.exportLanguage) {
  return cachedApi(
    `workbench:${state.jobId}:${language}`,
    () => api(`/api/review/workbench?job_id=${encodeURIComponent(state.jobId)}&language=${encodeURIComponent(language)}`),
    API_CACHE_TTL.workbench
  );
}

function semanticEdgeKey(edge, idx) {
  return `${edge.from_state || "?"}|${edge.to_state || "?"}|${edge.event || ""}|${edge.semantic_type || ""}|${idx}`;
}

function semanticTypeLabel(kind) {
  return {
    explicit_arrow: "explicit arrow",
    explicit_transition: "explicit transition",
    rule_inferred: "rule inferred",
    state_rule: "state rule",
    mention_pair: "text mention",
  }[kind] || kind || "transition";
}

function semanticTypeTag(kind) {
  if (kind === "explicit_arrow" || kind === "explicit_transition") return "high";
  if (kind === "rule_inferred" || kind === "state_rule") return "warning";
  return "medium";
}

function semanticSummaryValue(summary, key, fallback = 0) {
  return summary && typeof summary[key] !== "undefined" ? summary[key] : fallback;
}

function currentDiagramEdge(edges) {
  if (!edges?.length) return null;
  const wanted = state.diagramFocus.edgeKey;
  const byKey = edges.find((edge) => edge.__edge_key === wanted);
  if (byKey) return byKey;
  const match = state.diagramFocus.match || {};
  if (match && Object.keys(match).length) {
    const byMatch = edges.find((edge) => {
      const transitionIds = edge.transition_ids || [];
      if (match.id && transitionIds.includes(match.id)) return true;
      return (
        (!match.from_state || String(edge.from_state || "") === String(match.from_state || "")) &&
        (!match.to_state || String(edge.to_state || "") === String(match.to_state || "")) &&
        (!match.event || String(edge.event || "") === String(match.event || ""))
      );
    });
    if (byMatch) return byMatch;
  }
  return edges[0];
}

function renderDiagramFlow(edges) {
  if (!edges?.length) return "<p class='detail'>No semantic transitions yet.</p>";
  const lines = edges.map((edge) => {
    const event = edge.event ? ` [${edge.event}]` : "";
    const kind = edge.semantic_type ? ` {${semanticTypeLabel(edge.semantic_type)}}` : "";
    return `${edge.from_state || "?"} -> ${edge.to_state || "?"}${event}${kind}`;
  });
  return `<pre class="tree-view logic-tree-pre">${esc(lines.join("\n"))}</pre>`;
}

function renderDiagramEdgeList(edges) {
  if (!edges?.length) return "<p class='detail'>No transition edges match this filter.</p>";
  return `<div class="diagram-edge-list">${edges
    .map((edge) => `<button class="diagram-edge-card ${edge.__edge_key === state.diagramFocus.edgeKey ? "active" : ""}" data-edge-pick="${esc(edge.__edge_key)}">
      <div class="diagram-edge-top">
        <span class="tag ${semanticTypeTag(edge.semantic_type)}">${esc(semanticTypeLabel(edge.semantic_type))}</span>
        ${edge.event ? `<span class="diagram-edge-event">${esc(edge.event)}</span>` : ""}
      </div>
      <div class="diagram-edge-path"><b>${esc(edge.from_state || "?")}</b><span>→</span><b>${esc(edge.to_state || "?")}</b></div>
      ${edge.conditions?.length ? `<div class="diagram-edge-conditions">${esc(edge.conditions.slice(0, 3).join(" · "))}${edge.conditions.length > 3 ? "…" : ""}</div>` : ""}
    </button>`)
    .join("")}</div>`;
}

function renderDiagramEvidenceList(values, emptyLabel) {
  if (!values?.length) return `<p class="detail">${esc(emptyLabel)}</p>`;
  const chips = values.map((value, idx) => {
    if (typeof value === "object" && value !== null) {
      const label = formatSourceReadable(value) || "source";
      return {
        kind: "source",
        label: label.length > 40 ? `${label.slice(0, 37)}…` : label,
        detail: label,
      };
    }
    const text = String(value || "");
    return {
      kind: idx === 0 ? "source" : "note",
      label: text.length > 40 ? `${text.slice(0, 37)}…` : text,
      detail: text,
    };
  });
  return renderEvidenceChips(chips);
}

function basename(value) {
  return String(value || "").split(/[\\/]/).pop();
}

function isImagePath(value) {
  return /\.(png|jpg|jpeg|gif|webp|bmp|svg)$/i.test(String(value || ""));
}

function sourcePreviewUrl(path) {
  return `/api/files/preview?path=${encodeURIComponent(path)}`;
}

function lineLooksRelevant(line, terms) {
  const text = String(line || "").toUpperCase();
  return terms.some((term) => term && text.includes(term.toUpperCase()));
}

function collectDiagramOverlay(edge, transitions, diagrams) {
  const rawTransitions = (transitions || []).filter((row) => {
    if (edge.transition_ids?.length && row.id) {
      return edge.transition_ids.includes(String(row.id));
    }
    return row.from_state === edge.from_state && row.to_state === edge.to_state && String(row.event || "") === String(edge.event || "");
  });
  const sourceNames = new Set();
  [...(edge.evidence_refs || []), ...rawTransitions.map((row) => row.source?.file || "")]
    .filter(Boolean)
    .forEach((value) => {
      sourceNames.add(basename(value));
      sourceNames.add(String(value));
    });
  const terms = [
    edge.from_state,
    edge.to_state,
    edge.event,
    ...(edge.conditions || []),
  ].filter(Boolean);
  const matchedDiagrams = (diagrams || []).filter((row) => {
    const names = [row.file, row.name, row.parent_document, row.embedded_name].filter(Boolean).map(basename);
    return names.some((name) => sourceNames.has(name)) || lineLooksRelevant(row.ocr_text || "", [edge.from_state, edge.to_state, edge.event]);
  }).map((row) => {
    const lines = String(row.ocr_text || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    const relevant = lines.filter((line) => lineLooksRelevant(line, terms)).slice(0, 8);
    return {
      ...row,
      preview_lines: relevant.length ? relevant : lines.slice(0, 6),
    };
  });
  return { rawTransitions, matchedDiagrams };
}

function renderRawTransitions(rawTransitions) {
  if (!rawTransitions?.length) return `<p class="detail">No raw transition records matched this semantic edge.</p>`;
  const chips = rawTransitions.map((row) => {
    const label = `${row.from_state || "?"} → ${row.to_state || "?"}`;
    const detail = [row.id, row.event, row.raw_condition, formatSourceReadable(row.source), row.derivation]
      .filter(Boolean)
      .join("\n");
    return { kind: "transition", label, detail: detail || label };
  });
  return renderEvidenceChips(chips);
}

function renderDiagramSourceCards(diagrams) {
  if (!diagrams?.length) return `<p class="detail">No OCR snippets matched this edge yet.</p>`;
  return `<div class="diagram-source-list">${diagrams.map((row) => {
    const fileLabel = row.parent_document || row.name || basename(row.file || "");
    const canPreviewImage = row.file && isImagePath(row.file);
    return `<div class="diagram-source-card">
      <div class="diagram-source-head">
        <div>
          <b>${esc(fileLabel || "diagram source")}</b>
          <p class="detail">${esc([row.source_kind || "diagram_ocr", row.embedded_name || "", row.page ? `page ${row.page}` : ""].filter(Boolean).join(" · "))}</p>
        </div>
        ${canPreviewImage ? `<a class="btn secondary btn-inline" href="${sourcePreviewUrl(row.file)}" target="_blank" rel="noreferrer">Open image</a>` : ""}
      </div>
      ${canPreviewImage ? `<img class="diagram-source-image" src="${sourcePreviewUrl(row.file)}" alt="${esc(fileLabel || "diagram")}" />` : ""}
      <pre class="tree-view diagram-ocr-preview">${esc((row.preview_lines || []).join("\n") || row.note || "No OCR text available.")}</pre>
    </div>`;
  }).join("")}</div>`;
}

function renderDiagramFocus(edge, overlay, logicItems = []) {
  if (!edge) return `<div class="card"><h4>Transition focus</h4><p class="detail">Select a transition edge to inspect its evidence.</p></div>`;
  const conditionChips = (edge.conditions || []).map((text) => {
    const value = String(text || "");
    return {
      kind: "note",
      label: value.length > 36 ? `${value.slice(0, 33)}…` : value,
      detail: value,
    };
  });
  const logicOptions = (logicItems || [])
    .map(
      (row) =>
        `<option value="${esc(row.logic_id)}">${esc(row.control_name)} · ${esc(row.parse_status || "")}</option>`
    )
    .join("");
  return `<div class="diagram-focus-card">
    <div class="diagram-focus-head">
      <div>
        <h4>${esc(edge.from_state || "?")} → ${esc(edge.to_state || "?")}</h4>
        <p class="detail">${edge.event ? `Event: ${esc(edge.event)} · ` : ""}${esc(semanticTypeLabel(edge.semantic_type))}${(edge.confidence_levels || []).length ? ` · ${esc(edge.confidence_levels.join(", "))}` : ""}</p>
      </div>
      <span class="tag ${semanticTypeTag(edge.semantic_type)}">${esc(semanticTypeLabel(edge.semantic_type))}</span>
    </div>
    ${conditionChips.length ? `<div style="margin:0.75rem 0"><h5>Conditions</h5>${renderEvidenceChips(conditionChips)}</div>` : ""}
    <div style="margin:0.75rem 0">
      <h5>Source evidence</h5>
      ${renderDiagramEvidenceList(edge.evidence_refs || [], "No source references attached.")}
    </div>
    ${
      logicOptions
        ? `<div class="diagram-overlay-grid">
            <div>
              <h5>Link to logic control</h5>
              <p class="detail">Confirm this diagram edge as structured overlay on a logic group.</p>
              <label class="detail">Logic group
                <select id="diagram-link-logic" class="clarify-box">${logicOptions}</select>
              </label>
              <button type="button" class="btn secondary" id="btn-diagram-link-confirm" data-edge-key="${esc(edge.__edge_key || "")}">Confirm link</button>
              <p id="diagram-link-status" class="detail"></p>
            </div>
            <div>
              <h5>OCR snippets</h5>
              ${renderDiagramSourceCards(overlay?.matchedDiagrams || [])}
            </div>
          </div>`
        : ""
    }
    <details class="alex-ref-panel">
      <summary>Linked transitions (${(overlay?.rawTransitions || []).length})</summary>
      <div class="alex-ref-body">${renderRawTransitions(overlay?.rawTransitions || [])}</div>
    </details>
  </div>`;
}

function renderDiagramStateList(states, activeState) {
  if (!states?.length) return "<p class='detail'>No states detected yet.</p>";
  return `<div class="alex-state-grid">${states
    .map((name) => `<button type="button" class="alex-state-card ${name === activeState ? "is-active" : ""}" data-state-pick="${esc(name)}"><span class="alex-state-card__name">${esc(name)}</span></button>`)
    .join("")}</div>`;
}


/* ──────────────────────────────────────────────────────────────
 * Tab 4 — Library (Polarion-style trace canvas)
 *
 * Layout: one focus card on the left + relationship rows on the right.
 * Each row has a free-form label, N empty/filled slots, and a "+" button
 * to add another empty slot. A separate "+ Add relationship" button appends
 * a new row. Slots accept OS drag-drop or click-to-pick from the library
 * root folder.
 * ────────────────────────────────────────────────────────────── */

const LIBRARY_FILE_ICON = {
  docx: "file-doc",
  pdf: "file-doc",
  md: "file-doc",
  txt: "file-doc",
  csv: "csv",
  xlsx: "excel",
  xlsm: "excel",
  xls: "excel",
  png: "diagram",
  jpg: "diagram",
  jpeg: "diagram",
  gif: "diagram",
  webp: "diagram",
  bmp: "diagram",
  svg: "diagram",
};

function libraryFileIcon(name) {
  const ext = String(name || "").toLowerCase().split(".").pop();
  return LIBRARY_FILE_ICON[ext] || "file-doc";
}

function libraryFileName(absPath) {
  if (!absPath) return "";
  return String(absPath).split(/[\\/]/).pop();
}

function libraryItemById(id) {
  return (state.library.items || []).find((it) => it.id === id) || null;
}

function libraryFocusItem() {
  const id = state.library.focusId;
  if (!id) return null;
  return libraryItemById(id);
}

function libraryGroupedSpokes() {
  // Returns [{ label, links: [{link, target}] }] grouped per label, preserving
  // first-seen order. Only outgoing links from the focus item are shown.
  const focus = libraryFocusItem();
  if (!focus) return [];
  const groups = new Map();
  for (const link of state.library.links) {
    if (link.source !== focus.id) continue;
    if (!groups.has(link.label)) groups.set(link.label, []);
    const target = libraryItemById(link.target);
    groups.get(link.label).push({ link, target });
  }
  return Array.from(groups.entries()).map(([label, entries]) => ({ label, entries }));
}

async function fetchLibrary() {
  const data = await api("/api/library");
  applyLibraryState(data);
  if (!state.library.rootInputDraft) {
    state.library.rootInputDraft = state.library.root;
  }
}

function applyLibraryState(data) {
  state.library.root = data.root || "";
  state.library.rootExists = !!data.root_exists;
  state.library.focusId = data.focus_id || "";
  state.library.items = data.items || [];
  state.library.links = data.links || [];
}

async function setLibraryRoot(path) {
  state.library.rootError = null;
  try {
    const data = await api("/api/library/root", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    applyLibraryState(data);
    state.library.rootInputDraft = state.library.root;
    try {
      localStorage.setItem("alex.library.lastRoot", path);
    } catch (_) {
      /* ignore */
    }
  } catch (err) {
    state.library.rootError = err.message || String(err);
  }
  await renderLibrary();
}

async function libraryAddItem({ file } = {}) {
  const data = await api("/api/library/items", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file: file || null }),
  });
  applyLibraryState(data.state);
  return data.item;
}

async function libraryUpdateItemFile(itemId, file) {
  const data = await api(`/api/library/items/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file: file || null }),
  });
  applyLibraryState(data.state);
}

async function libraryDeleteItem(itemId) {
  const data = await api(`/api/library/items/${itemId}`, { method: "DELETE" });
  applyLibraryState(data.state);
}

async function librarySetFocus(itemId) {
  const data = await api("/api/library/focus", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_id: itemId }),
  });
  applyLibraryState(data);
}

async function libraryAddRow(label) {
  // Creates a new empty target item + a link from focus → that item with the
  // provided label.
  const data = await api("/api/library/links", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label, source_id: state.library.focusId || null, target_id: null }),
  });
  applyLibraryState(data.state);
}

async function libraryUpdateLinkLabel(linkId, label) {
  const data = await api(`/api/library/links/${linkId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label }),
  });
  applyLibraryState(data.state);
}

async function libraryDeleteLink(linkId) {
  const data = await api(`/api/library/links/${linkId}`, { method: "DELETE" });
  applyLibraryState(data.state);
}

async function libraryUploadFile(file, { itemId } = {}) {
  const form = new FormData();
  form.append("file", file);
  const url = itemId
    ? `/api/library/upload?item_id=${encodeURIComponent(itemId)}`
    : "/api/library/upload";
  const res = await fetch(url, { method: "POST", body: form });
  if (!res.ok) {
    let msg = `Upload failed: ${res.status}`;
    try { const j = await res.json(); msg = j.detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  const data = await res.json();
  applyLibraryState(data.state);
  return data.item_id;
}

function renderLibrarySlot({ item, link, modifier = "" }) {
  const filled = !!(item && item.file);
  const name = filled ? libraryFileName(item.file) : "";
  const previewUrl = filled
    ? `/api/files/preview?path=${encodeURIComponent(item.file)}`
    : "";
  const inner = filled
    ? `<span class="library-slot__icon">${icon(libraryFileIcon(name))}</span>
       <span class="library-slot__name" title="${esc(item.file)}">${esc(name)}</span>`
    : `<span class="library-slot__plus">＋</span><span class="library-slot__hint">Drop or pick</span>`;
  return `<div class="library-slot ${modifier} ${filled ? "is-filled" : "is-empty"}"
              data-library-slot
              data-library-item-id="${esc(item ? item.id : "")}"
              data-library-link-id="${esc(link ? link.id : "")}"
              data-library-preview-url="${esc(previewUrl)}"
              title="${esc(filled ? item.file + " — click to open" : "Drop a file or click to pick from the library folder")}">
    ${inner}
    <div class="library-slot__actions">
      ${filled ? `<button class="library-slot__action" data-library-clear="${esc(item.id)}" title="Clear file">×</button>` : ""}
      ${link ? `<button class="library-slot__action" data-library-remove-link="${esc(link.id)}" title="Remove slot">🗑</button>` : ""}
    </div>
  </div>`;
}

function renderLibraryFocusCard() {
  const focus = libraryFocusItem();
  if (!focus) {
    return `<div class="library-slot library-slot--focus is-empty" data-library-create-focus>
      <span class="library-slot__plus">＋</span>
      <span class="library-slot__hint">Drop or pick focus file</span>
    </div>`;
  }
  return renderLibrarySlot({ item: focus, link: null, modifier: "library-slot--focus" });
}

function renderLibraryRow(group) {
  const slots = group.entries
    .map((entry) =>
      `<div class="library-row__slot-wrap">${renderLibrarySlot({ item: entry.target, link: entry.link })}</div>`
    )
    .join("");
  return `<div class="library-row" data-library-row-label="${esc(group.label)}">
    <div class="library-row__label">
      <input class="library-row__label-input" value="${esc(group.label)}" data-library-row-rename="${esc(group.label)}" />
      <span class="library-row__arrow">→</span>
    </div>
    <div class="library-row__slots">
      ${slots}
      <button class="library-row__add" data-library-row-add="${esc(group.label)}" title="Add slot">＋</button>
    </div>
  </div>`;
}

function renderLibraryAddRow() {
  if (!state.library.addRowMode) {
    return `<button class="library-add-row" data-library-add-row>＋ Add relationship</button>`;
  }
  const draft = state.library.addRowDraft || "";
  return `<div class="library-add-row library-add-row--editing">
    <input class="library-add-row__input" id="library-new-row" placeholder="e.g. Satisfies, Validated By, Implements" value="${esc(draft)}" />
    <button class="btn" id="library-new-row-save">Add row</button>
    <button class="btn ghost" id="library-new-row-cancel">Cancel</button>
  </div>`;
}

function renderLibraryPicker() {
  if (!state.library.pickerOpenItemId) return "";
  const listing = state.library.pickerListing;
  const error = state.library.pickerError;
  const loading = state.library.pickerLoading;
  let body = "";
  if (loading) {
    body = `<p class="detail">Loading…</p>`;
  } else if (error) {
    body = `<p class="detail" style="color:var(--red)">${esc(error)}</p>`;
  } else if (!listing) {
    body = `<p class="detail">Pick a file or open a sub-folder.</p>`;
  } else {
    const parent = listing.parent
      ? `<button class="library-picker__entry library-picker__entry--up" data-library-picker-dir="${esc(listing.parent)}">⬆ ..</button>`
      : "";
    const dirs = (listing.dirs || [])
      .map(
        (d) =>
          `<button class="library-picker__entry library-picker__entry--dir" data-library-picker-dir="${esc(d.path)}">📁 ${esc(d.name)}</button>`
      )
      .join("");
    const files = (listing.files || [])
      .map(
        (f) =>
          `<button class="library-picker__entry library-picker__entry--file" data-library-picker-file="${esc(f.path)}"><span class="library-picker__icon">${icon(libraryFileIcon(f.name), "alex-icon--xs")}</span> ${esc(f.name)}</button>`
      )
      .join("");
    body = `<div class="library-picker__cwd" title="${esc(listing.cwd)}">${esc(listing.cwd)}</div>
            <div class="library-picker__list">${parent}${dirs}${files || (parent || dirs ? "" : `<p class="detail">Folder is empty.</p>`)}</div>`;
  }
  return `<div class="library-picker-backdrop" data-library-picker-close>
    <div class="library-picker">
      <header class="library-picker__head">
        <strong>Pick a file from the library folder</strong>
        <button class="btn ghost btn-xs" data-library-picker-close>Close</button>
      </header>
      <div class="library-picker__body">${body}</div>
    </div>
  </div>`;
}

function renderLibraryTopbar() {
  const draft = state.library.rootInputDraft ?? state.library.root ?? "";
  try {
    if (!draft && !state.library.root) {
      const saved = localStorage.getItem("alex.library.lastRoot");
      if (saved) state.library.rootInputDraft = saved;
    }
  } catch (_) {
    /* ignore */
  }
  const displayPath = state.library.rootInputDraft ?? state.library.root ?? draft;
  return `<div class="library-topbar">
    <div class="library-topbar__root">
      <span class="detail library-topbar__label">Library folder</span>
      <button type="button" class="btn secondary" id="btn-library-browse-root">Browse folder…</button>
      <input class="library-topbar__path" id="library-root-input" placeholder="/path/to/specs" value="${esc(displayPath)}" aria-label="Library folder path" />
      <button class="btn" id="btn-library-set-root">${state.library.root ? "Update" : "Set folder"}</button>
      <button class="btn secondary" id="btn-library-refresh" ${state.library.root ? "" : "disabled"}>Refresh</button>
    </div>
    ${state.library.rootError ? `<p class="detail library-topbar__error">${esc(state.library.rootError)}</p>` : ""}
    ${!state.library.root ? `<p class="detail">Browse for the folder that holds your spec files, or type an absolute path. Drag-drops on slots copy files into this folder.</p>` : ""}
  </div>`;
}

function renderLibraryRootPicker() {
  if (!state.library.rootPickerOpen) return "";
  const listing = state.library.rootPickerListing;
  const cwd = listing?.cwd || "Quick locations";
  const dirs = listing?.dirs || [];
  const specCount = listing?.spec_file_count;
  const body = state.library.rootPickerLoading
    ? `<p class="detail">Loading folders…</p>`
    : state.library.rootPickerError
      ? `<p class="detail" style="color:var(--status-error)">${esc(state.library.rootPickerError)}</p>`
      : `<ul class="library-root-picker__list">${dirs
          .map(
            (d) =>
              `<li><button type="button" data-library-root-dir="${esc(d.path)}">${esc(d.label || d.name || d.path)}</button></li>`
          )
          .join("")}</ul>`;
  return `<div class="library-root-picker-backdrop" data-library-root-backdrop>
    <div class="library-root-picker" role="dialog" aria-modal="true" aria-label="Choose library folder">
      <header class="library-root-picker__head">
        <strong>Choose library folder</strong>
        <button type="button" class="btn ghost btn-xs" data-library-root-close>Close</button>
      </header>
      <div class="library-root-picker__body">
        <div class="library-root-picker__cwd">${esc(cwd)}${specCount != null && listing?.cwd ? ` · ${specCount} spec file(s) here` : ""}</div>
        ${listing?.parent ? `<button type="button" class="btn secondary btn-xs" data-library-root-up>↑ Up</button>` : ""}
        ${body}
      </div>
      <footer class="library-root-picker__foot">
        <button type="button" class="btn secondary" data-library-root-close>Cancel</button>
        <button type="button" class="btn" data-library-root-use ${listing?.cwd ? "" : "disabled"}>Use this folder</button>
      </footer>
    </div>
  </div>`;
}

async function openLibraryRootPicker(path = "") {
  state.library.rootPickerOpen = true;
  state.library.rootPickerLoading = true;
  state.library.rootPickerError = null;
  await renderLibrary();
  try {
    const q = path ? `?path=${encodeURIComponent(path)}` : "";
    state.library.rootPickerListing = await api(`/api/library/browse-root${q}`);
    state.library.rootPickerCwd = state.library.rootPickerListing?.cwd || "";
  } catch (err) {
    state.library.rootPickerError = err.message || String(err);
  } finally {
    state.library.rootPickerLoading = false;
    await renderLibrary();
  }
}

function bindLibraryRootPicker() {
  document.querySelector("[data-library-root-backdrop]")?.addEventListener("click", (ev) => {
    if (ev.target?.matches("[data-library-root-backdrop]")) {
      state.library.rootPickerOpen = false;
      renderLibrary();
    }
  });
  document.querySelectorAll("[data-library-root-close]").forEach((btn) => {
    btn.onclick = () => {
      state.library.rootPickerOpen = false;
      renderLibrary();
    };
  });
  document.querySelector("[data-library-root-up]")?.addEventListener("click", () => {
    const parent = state.library.rootPickerListing?.parent;
    if (parent) openLibraryRootPicker(parent);
  });
  document.querySelectorAll("[data-library-root-dir]").forEach((btn) => {
    btn.onclick = () => openLibraryRootPicker(btn.dataset.libraryRootDir || "");
  });
  document.querySelector("[data-library-root-use]")?.addEventListener("click", () => {
    const cwd = state.library.rootPickerListing?.cwd;
    if (!cwd) return;
    state.library.rootInputDraft = cwd;
    state.library.rootPickerOpen = false;
    try {
      localStorage.setItem("alex.library.lastRoot", cwd);
    } catch (_) {
      /* ignore */
    }
    setLibraryRoot(cwd);
  });
}

async function renderLibrary() {
  if (!state.library.root && !state.library.rootInputDraft && !state.library.rootError) {
    try { await fetchLibrary(); } catch (err) { state.library.error = err.message || String(err); }
  }
  const groups = libraryGroupedSpokes();
  const canEdit = !!state.library.root && state.library.rootExists;

  content().innerHTML = `<header class="page-header library-header"><h2>Library</h2></header>
    ${renderLibraryTopbar()}
    ${canEdit
      ? `<div class="library-canvas">
          <div class="library-focus-col">
            ${renderLibraryFocusCard()}
            ${state.library.focusId ? `<button class="library-add-row library-add-row--side" data-library-add-row>＋ Add</button>` : ""}
          </div>
          <div class="library-rows">
            ${groups.map(renderLibraryRow).join("") || `<p class="detail library-rows__empty">No relationships yet — click ＋ Add to start.</p>`}
            ${state.library.focusId ? renderLibraryAddRow() : ""}
          </div>
        </div>`
      : `<p class="detail">Set a library folder above to start building the trace map.</p>`
    }
    ${renderLibraryPicker()}
    ${renderLibraryRootPicker()}`;

  bindLibraryTopbar();
  bindLibraryCanvas();
  bindLibraryPicker();
  bindLibraryRootPicker();
  bindTabHelpLinks();
}

function bindLibraryTopbar() {
  const setBtn = $("#btn-library-set-root");
  const input = $("#library-root-input");
  if (input) {
    input.oninput = (ev) => { state.library.rootInputDraft = ev.target.value; };
    input.onkeydown = (ev) => {
      if (ev.key === "Enter") {
        ev.preventDefault();
        setBtn?.click();
      }
    };
  }
  if (setBtn) {
    setBtn.onclick = () => {
      const value = (input?.value || "").trim();
      if (!value) {
        state.library.rootError = "Enter an absolute path to a local folder.";
        renderLibrary();
        return;
      }
      setLibraryRoot(value);
    };
  }
  const refresh = $("#btn-library-refresh");
  if (refresh) {
    refresh.onclick = async () => {
      try { await fetchLibrary(); } catch (err) { state.library.rootError = err.message || String(err); }
      renderLibrary();
    };
  }
  const browseRoot = $("#btn-library-browse-root");
  if (browseRoot) {
    browseRoot.onclick = () => openLibraryRootPicker(state.library.rootInputDraft || state.library.root || "");
  }
}

function bindLibraryCanvas() {
  // Drag-and-drop + click-to-pick for every slot.
  content().querySelectorAll("[data-library-slot]").forEach((el) => {
    el.addEventListener("dragover", (ev) => {
      ev.preventDefault();
      el.classList.add("is-dragging");
    });
    el.addEventListener("dragleave", () => el.classList.remove("is-dragging"));
    el.addEventListener("drop", async (ev) => {
      ev.preventDefault();
      el.classList.remove("is-dragging");
      const file = ev.dataTransfer?.files?.[0];
      if (!file) return;
      const itemId = el.dataset.libraryItemId;
      try {
        state.library.busy = true;
        await libraryUploadFile(file, { itemId });
      } catch (err) {
        alert(err.message || String(err));
      } finally {
        state.library.busy = false;
        renderLibrary();
      }
    });
    el.addEventListener("click", (ev) => {
      // Ignore clicks bubbling from action buttons.
      if (ev.target.closest("[data-library-clear],[data-library-remove-link]")) return;
      const itemId = el.dataset.libraryItemId;
      if (!itemId) return;
      const previewUrl = el.dataset.libraryPreviewUrl;
      if (previewUrl) {
        // Filled slot → open the file in a new browser tab.
        window.open(previewUrl, "_blank", "noopener,noreferrer");
        return;
      }
      openLibraryPicker(itemId);
    });
  });

  // Focus placeholder (no item yet) — clicking creates the focus item then opens picker.
  const createFocus = content().querySelector("[data-library-create-focus]");
  if (createFocus) {
    createFocus.onclick = async () => {
      try {
        const item = await libraryAddItem();
        await librarySetFocus(item.id);
        openLibraryPicker(item.id);
      } catch (err) {
        alert(err.message || String(err));
      }
      renderLibrary();
    };
    createFocus.addEventListener("dragover", (ev) => { ev.preventDefault(); createFocus.classList.add("is-dragging"); });
    createFocus.addEventListener("dragleave", () => createFocus.classList.remove("is-dragging"));
    createFocus.addEventListener("drop", async (ev) => {
      ev.preventDefault();
      createFocus.classList.remove("is-dragging");
      const file = ev.dataTransfer?.files?.[0];
      if (!file) return;
      try {
        const newId = await libraryUploadFile(file);
        await librarySetFocus(newId);
      } catch (err) {
        alert(err.message || String(err));
      }
      renderLibrary();
    });
  }

  content().querySelectorAll("[data-library-clear]").forEach((btn) => {
    btn.onclick = async (ev) => {
      ev.stopPropagation();
      const id = btn.dataset.libraryClear;
      try { await libraryUpdateItemFile(id, ""); } catch (err) { alert(err.message); }
      renderLibrary();
    };
  });
  content().querySelectorAll("[data-library-remove-link]").forEach((btn) => {
    btn.onclick = async (ev) => {
      ev.stopPropagation();
      const id = btn.dataset.libraryRemoveLink;
      try { await libraryDeleteLink(id); } catch (err) { alert(err.message); }
      renderLibrary();
    };
  });
  content().querySelectorAll("[data-library-stop]").forEach((el) => {
    el.addEventListener("click", (ev) => ev.stopPropagation());
  });

  // Row rename (label) on Enter / blur.
  content().querySelectorAll("[data-library-row-rename]").forEach((input) => {
    const original = input.dataset.libraryRowRename;
    const commit = async () => {
      const next = (input.value || "").trim();
      if (!next || next === original) return;
      // Rename every link in this row in parallel.
      const linkIds = state.library.links
        .filter((l) => l.source === state.library.focusId && l.label === original)
        .map((l) => l.id);
      try {
        await Promise.all(linkIds.map((id) => libraryUpdateLinkLabel(id, next)));
      } catch (err) {
        alert(err.message);
      }
      renderLibrary();
    };
    input.addEventListener("blur", commit);
    input.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") { ev.preventDefault(); input.blur(); }
      else if (ev.key === "Escape") { input.value = original; input.blur(); }
    });
  });

  // Add another slot to an existing row.
  content().querySelectorAll("[data-library-row-add]").forEach((btn) => {
    btn.onclick = async () => {
      try { await libraryAddRow(btn.dataset.libraryRowAdd); } catch (err) { alert(err.message); }
      renderLibrary();
    };
  });

  // + Add relationship.
  const addRowBtn = content().querySelector("[data-library-add-row]");
  if (addRowBtn) {
    addRowBtn.onclick = () => {
      state.library.addRowMode = true;
      state.library.addRowDraft = "";
      renderLibrary().then(() => $("#library-new-row")?.focus());
    };
  }
  const saveNewRow = $("#library-new-row-save");
  const cancelNewRow = $("#library-new-row-cancel");
  const newRowInput = $("#library-new-row");
  if (newRowInput) {
    newRowInput.oninput = (ev) => { state.library.addRowDraft = ev.target.value; };
    newRowInput.onkeydown = (ev) => {
      if (ev.key === "Enter") { ev.preventDefault(); saveNewRow?.click(); }
      else if (ev.key === "Escape") { cancelNewRow?.click(); }
    };
  }
  if (saveNewRow) {
    saveNewRow.onclick = async () => {
      const label = (newRowInput?.value || "").trim();
      if (!label) { newRowInput?.focus(); return; }
      try { await libraryAddRow(label); } catch (err) { alert(err.message); return; }
      state.library.addRowMode = false;
      state.library.addRowDraft = "";
      renderLibrary();
    };
  }
  if (cancelNewRow) {
    cancelNewRow.onclick = () => {
      state.library.addRowMode = false;
      state.library.addRowDraft = "";
      renderLibrary();
    };
  }
}

async function openLibraryPicker(itemId) {
  state.library.pickerOpenItemId = itemId;
  state.library.pickerError = null;
  state.library.pickerCwd = state.library.root;
  state.library.pickerListing = null;
  state.library.pickerLoading = true;
  await renderLibrary();
  try {
    const data = await api("/api/library/browse");
    state.library.pickerListing = data;
  } catch (err) {
    state.library.pickerError = err.message || String(err);
  } finally {
    state.library.pickerLoading = false;
  }
  await renderLibrary();
}

async function loadPickerDir(path) {
  state.library.pickerLoading = true;
  state.library.pickerError = null;
  await renderLibrary();
  try {
    const data = await api(`/api/library/browse?path=${encodeURIComponent(path)}`);
    state.library.pickerListing = data;
    state.library.pickerCwd = data.cwd;
  } catch (err) {
    state.library.pickerError = err.message || String(err);
  } finally {
    state.library.pickerLoading = false;
  }
  await renderLibrary();
}

async function pickLibraryFile(filePath) {
  const itemId = state.library.pickerOpenItemId;
  if (!itemId) return;
  try {
    await libraryUpdateItemFile(itemId, filePath);
  } catch (err) {
    alert(err.message || String(err));
    return;
  }
  closeLibraryPicker();
  await renderLibrary();
}

function closeLibraryPicker() {
  state.library.pickerOpenItemId = null;
  state.library.pickerListing = null;
  state.library.pickerError = null;
}

function bindLibraryPicker() {
  if (!state.library.pickerOpenItemId) return;
  content().querySelectorAll("[data-library-picker-close]").forEach((el) => {
    el.onclick = (ev) => {
      if (el === ev.target || el.classList.contains("library-picker-backdrop")) {
        closeLibraryPicker();
        renderLibrary();
      }
    };
  });
  // Stop propagation inside the modal so clicking the dialog body doesn't dismiss.
  const dialog = content().querySelector(".library-picker");
  if (dialog) dialog.addEventListener("click", (ev) => ev.stopPropagation());
  content().querySelectorAll("[data-library-picker-dir]").forEach((btn) => {
    btn.onclick = () => loadPickerDir(btn.dataset.libraryPickerDir);
  });
  content().querySelectorAll("[data-library-picker-file]").forEach((btn) => {
    btn.onclick = () => pickLibraryFile(btn.dataset.libraryPickerFile);
  });
}


async function renderDiagramGraph() {
  if (!state.jobId) {
    content().innerHTML = requireJobHtml("no_job");
    bindNoJob();
    return;
  }
  await refreshJobSummary();
  try {
    const data = await cachedApi(
      `states:${state.jobId}`,
      () => api(`/api/review/states?job_id=${encodeURIComponent(state.jobId)}`),
      API_CACHE_TTL.states
    );
    const logicData = await cachedApi(
      `logic-review:${state.jobId}`,
      () => api(`/api/review/logic-review?job_id=${encodeURIComponent(state.jobId)}`),
      API_CACHE_TTL.logicReview
    ).catch(() => ({}));
    const logicItems = logicData.logic_review_items || [];
    const semantics = data.diagram_semantics || {};
    const rawTransitions = data.transitions || [];
    const diagrams = data.diagrams || [];
    const rawStates = semantics.states?.length ? semantics.states : data.states || [];
    const states = rawStates
      .map((row) => {
        if (typeof row === "string") return row;
        return row?.state || row?.name || "";
      })
      .filter(Boolean);
    const edges = (semantics.edges || []).map((edge, idx) => ({ ...edge, __edge_key: semanticEdgeKey(edge, idx) }));
    const summary = semantics.summary || {};
    const activeState = states.includes(state.diagramFocus.state) ? state.diagramFocus.state : (states[0] || null);
    state.diagramFocus.state = activeState;
    const filteredEdges = activeState
      ? edges.filter((edge) => edge.from_state === activeState || edge.to_state === activeState)
      : edges;
    const activeEdge = currentDiagramEdge(filteredEdges);
    state.diagramFocus.edgeKey = activeEdge?.__edge_key || null;
    if (activeEdge) {
      state.diagramFocus.match = null;
    }
    const overlay = activeEdge ? collectDiagramOverlay(activeEdge, rawTransitions, diagrams) : null;
    content().innerHTML = `<header class="page-header">
        <h2>State machine</h2>
        <p class="lead">Select a state, then a transition. Evidence and conditions appear in the detail panel.</p>
      </header>
      ${renderMetaStats([
        ["States", states.length],
        ["Edges", edges.length],
        ["Explicit", semanticSummaryValue(summary, "explicit_edges", filteredEdges.filter((e) => e.semantic_type === "explicit_arrow" || e.semantic_type === "explicit_transition").length)],
        ["Inferred", semanticSummaryValue(summary, "rule_inferred_edges", filteredEdges.filter((e) => e.semantic_type === "rule_inferred" || e.semantic_type === "state_rule").length)],
        ["OCR mentions", semanticSummaryValue(summary, "ocr_state_mentions", semanticSummaryValue(summary, "state_mentions", 0))],
      ], { compact: true })}
      <div class="review-actions" style="margin-bottom:1rem">
        <button class="btn secondary" id="btn-diagram-logic">Logic &amp; definitions</button>
        <button class="btn secondary" id="btn-diagram-jump-logic" ${activeEdge ? "" : "disabled"}>Jump to linked logic</button>
        <button class="btn secondary" id="btn-diagram-export">Final file</button>
      </div>
      <h3 class="alex-primary-panel__label" style="margin-bottom:0.5rem">States</h3>
      ${renderDiagramStateList(states, activeState)}
      <div class="alex-diagram-main">
        <div class="card alex-diagram-list">
          <h4>Transitions${activeState ? ` · ${esc(activeState)}` : ""}</h4>
          ${renderDiagramEdgeList(filteredEdges)}
        </div>
        <div class="card alex-diagram-detail">
          ${renderDiagramFocus(activeEdge, overlay, logicItems)}
        </div>
      </div>
      <details class="alex-flow-panel alex-ref-panel">
        <summary>Transition flow map (compact)</summary>
        <div class="alex-ref-body">${renderDiagramFlow(filteredEdges)}</div>
      </details>`;
    $("#btn-diagram-logic").onclick = () => showPage("logic-review");
    const jumpLogicBtn = $("#btn-diagram-jump-logic");
    if (jumpLogicBtn && activeEdge) {
      jumpLogicBtn.onclick = () => {
        const linked = (overlay?.logic_blocks || [])[0]?.id || logicItems[0]?.logic_id;
        if (linked) state.selectedLogicId = linked;
        showPage("logic-review");
      };
    }
    $("#btn-diagram-export").onclick = () => showPage("export");
    content().querySelectorAll("[data-state-pick]").forEach((btn) => {
      btn.onclick = () => {
        state.diagramFocus.state = btn.dataset.statePick;
        state.diagramFocus.edgeKey = null;
        renderDiagramGraph();
      };
    });
    content().querySelectorAll("[data-edge-pick]").forEach((btn) => {
      btn.onclick = () => {
        state.diagramFocus.edgeKey = btn.dataset.edgePick;
        renderDiagramGraph();
      };
    });
    const linkBtn = $("#btn-diagram-link-confirm");
    if (linkBtn && activeEdge) {
      linkBtn.onclick = async () => {
        const logicId = $("#diagram-link-logic")?.value;
        if (!logicId) return;
        const statusEl = $("#diagram-link-status");
        if (statusEl) statusEl.textContent = "Linking…";
        try {
          const res = await api(`/api/review/diagram-link?job_id=${encodeURIComponent(state.jobId)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              logic_id: logicId,
              from_state: activeEdge.from_state,
              to_state: activeEdge.to_state,
              event: activeEdge.event || "",
              conditions: activeEdge.conditions || [],
              edge_key: activeEdge.__edge_key || "",
            }),
          });
          if (statusEl) {
            statusEl.textContent =
              "Linked to logic overlay. Open Logic & Definitions to review." +
              formatUnderstandingLoopStatus(res.understanding_loop);
          }
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        }
      };
    }
    bindTabHelpLinks();
  } catch (e) {
    content().innerHTML = `<p class="detail" style="color:var(--red)">${esc(e.message)}</p>`;
  }
}

async function renderLogicReview(opts = {}) {
  if (!state.jobId) {
    content().innerHTML = requireJobHtml("no_job");
    bindNoJob();
    return;
  }
  if (opts.skipShell && document.querySelector(".alex-layout-logic")) {
    refreshM365TaskBanner();
    return;
  }
  const loading = !document.querySelector(".alex-layout-logic");
  if (loading) {
    content().innerHTML = `<p class="detail">Loading logic review…</p>`;
  }
  try {
    if (opts.force) invalidateApiCache(`logic-review:${state.jobId}`);
    const summaryPromise = opts.skipSummary
      ? Promise.resolve(null)
      : refreshJobSummary(opts.force).catch(() => null);
    const [data] = await Promise.all([
      cachedApi(
        `logic-review:${state.jobId}`,
        () => api(`/api/review/logic-review?job_id=${state.jobId}`),
        API_CACHE_TTL.logicReview
      ),
      summaryPromise,
    ]);
    state.bundle = {
      ...(state.bundle || {}),
      term_roles: data.term_roles || state.bundle?.term_roles || {},
    };
    const items = data.logic_review_items || [];
    if (!items.length) {
      const src = jobBootstrapSource(state._summaryCache?.summary);
      const hint =
        src.startsWith("imported")
          ? "Imported job has synthetic logic groups — open Export or Test Code to edit test cases. Run diagnostic for parser details."
          : "No logic blocks detected. Try Import TestSpec or run Review specification. Parser may not match your docx table headers.";
      content().innerHTML = `<h2>Logic Review</h2><p class="detail">${esc(hint)}</p>
        <button class="btn secondary" id="btn-logic-diagnostic" type="button">Run job diagnostic</button>
        <pre id="logic-diagnostic-out" class="detail" style="white-space:pre-wrap;margin-top:0.75rem"></pre>`;
      $("#btn-logic-diagnostic").onclick = async () => {
        try {
          const d = await api(`/api/jobs/${encodeURIComponent(state.jobId)}/diagnostic`);
          $("#logic-diagnostic-out").textContent = JSON.stringify(d.diagnostic, null, 2);
        } catch (e) {
          $("#logic-diagnostic-out").textContent = e.message;
        }
      };
      return;
    }
    const sel = state.selectedLogicId || items[0].logic_id;
    const item = items.find((x) => x.logic_id === sel) || items[0];
    const assistStatus =
      state.assistStatus ||
      state.ollamaStatus || {
        providers_available: {
          ollama: !!(state.ollamaStatus?.ollama?.reachable || state.ollamaStatus?.providers_available?.ollama),
          m365: m365KnowledgeReady(),
          copilot: false,
        },
      };
    const [inbox, workbench, knowledgeApply, reasoningRes, overviewRes, footnoteMat, pathMatrix, copilotSessionRes, verifyMatrixRes] =
      await Promise.all([
      cachedApi(
        `inbox:${state.jobId}:${item.logic_id}`,
        () =>
          api(
            `/api/review/definition-inbox?job_id=${encodeURIComponent(state.jobId)}&logic_id=${encodeURIComponent(item.logic_id)}`
          ),
        8000
      ),
      fetchWorkbench(state.exportLanguage),
      cachedApi(
        `knowledge:${state.jobId}:${item.logic_id}`,
        () =>
          api(
            `/api/review/knowledge-apply?job_id=${encodeURIComponent(state.jobId)}&logic_id=${encodeURIComponent(item.logic_id)}`
          ),
        8000
      ).catch(() => ({ status: "none", diffs: [] })),
      cachedApi(
        `reasoning:${state.jobId}:${item.logic_id}`,
        () => api(`/api/reasoning/${encodeURIComponent(item.logic_id)}?job_id=${encodeURIComponent(state.jobId)}`),
        8000
      ).catch(() => null),
      cachedApi(`overview:${state.jobId}`, () => api(`/api/review/overview?job_id=${encodeURIComponent(state.jobId)}`), 15000).catch(
        () => null
      ),
      cachedApi(
        `footnote:${state.jobId}:${item.logic_id}`,
        () =>
          api(
            `/api/review/footnote-materializations?job_id=${encodeURIComponent(state.jobId)}&logic_id=${encodeURIComponent(item.logic_id)}`
          ),
        8000
      ).catch(() => null),
      cachedApi(
        `path-matrix:${state.jobId}:${item.logic_id}`,
        () =>
          api(
            `/api/review/path-tc-matrix?job_id=${encodeURIComponent(state.jobId)}&logic_id=${encodeURIComponent(item.logic_id)}`
          ),
        8000
      ).catch(() => null),
      cachedApi(
        `copilot-session:${state.jobId}:${item.logic_id}`,
        () =>
          api(
            `/api/review/copilot/session?job_id=${encodeURIComponent(state.jobId)}&logic_id=${encodeURIComponent(item.logic_id)}`
          ),
        8000
      ).catch(() => ({ session: {} })),
      cachedApi(
        `verify-matrix:${state.jobId}:${item.logic_id}`,
        () =>
          api(
            `/api/review/verification-matrix?job_id=${encodeURIComponent(state.jobId)}&logic_id=${encodeURIComponent(item.logic_id)}`
          ),
        8000
      ).catch(() => null),
    ]);
    const copilotSession = copilotSessionRes?.session || {};
    if (!state.copilotStep) state.copilotStep = {};
    state.assistStatus = assistStatus;
    const queueByLogic = Object.fromEntries(((data.ai_queue?.logic_groups) || []).map((row) => [row.logic_id, row]));
    const queueItem = queueByLogic[item.logic_id] || {};
    const engineerNote = (data.ai_assists?.engineer_notes || {})[item.logic_id] || "";
    const attachments = (data.ai_assists?.logic_attachments || {})[item.logic_id] || [];
    const relatedCandidateIds = new Set((item.candidates || []).map((row) => row.id));
    const logicRows = (workbench.rows || []).filter(
      (row) => row.logic_id === item.logic_id || relatedCandidateIds.has(row.candidate_id)
    );
    const simResult = state.pathSimResult?.[item.logic_id] || null;
    const highlightTerms = state.logicTreeFocus?.highlightTerms || [];
    const highlightRowNos = state.logicTreeFocus?.highlightRowNos || [];
    const treeHtml = renderInteractiveLogicTree(item, simResult?.active_node_ids || []);
    const pathSimHtml = renderPathSimulatorPanel(item, simResult);
    const overviewHtml = renderSpecOverviewPanel(overviewRes?.overview);
    const formalSpecHtml = renderFormalSpecContextPanel(data, item);
    const semanticsBadges = renderLogicSemanticsBadges(item);
    const footnoteAttachHtml = renderFootnoteAttachmentsPanel(footnoteMat);
    const pathMatrixHtml = renderPathTcMatrixPanel(pathMatrix?.matrix, state.pathRegenProposal?.[item.logic_id]);
    const verifyMatrixHtml = renderVerificationMatrixPanel(verifyMatrixRes || {}, item.logic_id);
    const listHtml = items
      .map(
        (it) =>
          `<option value="${esc(it.logic_id)}" ${it.logic_id === item.logic_id ? "selected" : ""}>${esc(
            it.control_name
          )}</option>`
      )
      .join("");
    const tableRows = (item.table_rows || []).map((r) => [
      r.row_no,
      esc(r.raw_condition),
      r.depth,
      esc(r.detected_type),
      esc(r.parser_reason || ""),
    ]);
    const parserNotes = (item.parser_notes || []).map((n) =>
      esc(n.parser_reason || n.message || n.type || "parser note")
    );
    const sourceEvidenceHtml = item.source_evidence
      ? typeof item.source_evidence === "object"
        ? renderEvidenceNotes(
            [
              {
                kind: "source",
                label: compactSourceLabel(item.source_evidence) || basename(item.source_evidence.file || "source"),
                detail: formatSourceReadable(item.source_evidence),
              },
            ],
            { label: "Source file" }
          )
        : renderEvidenceNotes(parseLegacyEvidenceString(item.source_evidence), { label: "Source file" })
      : "";
    content().innerHTML = `<div class="alex-layout-logic">
      ${overviewHtml}
      ${formalSpecHtml}
      <div class="logic-pick-bar logic-pick-bar--compact">
        <label class="detail logic-picker-label">Logic group (${items.length})
          <select id="logic-group-select" class="clarify-box logic-group-select">${listHtml}</select>
        </label>
      </div>
      <header class="alex-hero">
        <div>
          <h2 class="alex-hero__title">${esc(item.outcome_label || item.control_name)}</h2>
          <p class="alex-hero__sub">${item.outcome_label ? esc(item.control_name) + " · " : ""}Read the logic tree first, then trace terms and fix definitions.</p>
          ${semanticsBadges}
        </div>
        <span class="tag ${item.parse_status === "ok" ? "high" : item.parse_status === "partial" ? "warning" : "error"}">${esc(item.parse_status || "unknown")}</span>
      </header>
      ${sourceEvidenceHtml}
      ${item.unresolved_refs?.length ? `<p class="detail" style="margin-bottom:1rem"><b>Missing definitions:</b> ${esc(item.unresolved_refs.join(", "))}</p>` : ""}
      <section class="alex-primary-panel">
        <h3 class="alex-primary-panel__label">Logic structure</h3>
        <p class="detail" style="margin-top:0">Source table is the reference — click a tree node to highlight the matching row.</p>
        <div class="logic-compare-grid logic-evidence-workspace">
          <div class="logic-compare-panel">
            <h4 class="logic-compare__label">Tree logic</h4>
            <div class="logic-compare-panel__body">
              <div class="gate-diagram logic-tree-interactive-host">${treeHtml}</div>
              ${pathSimHtml}
            </div>
          </div>
          <div class="logic-compare-panel">
            <h4 class="logic-compare__label">Source table (linked)</h4>
            <div class="logic-compare-panel__body">
              ${renderVisualSourcePreview(item.visual_source, tableRows, highlightTerms, highlightRowNos)}
            </div>
          </div>
        </div>
        <details class="alex-ref-panel" style="margin-top:0.75rem">
          <summary>Parser notes (${parserNotes.length})</summary>
          <div class="alex-ref-body">
            ${parserNotes.length ? `<ul class="detail">${parserNotes.map((n) => `<li>${n}</li>`).join("")}</ul>` : `<p class="detail">No parser notes.</p>`}
          </div>
        </details>
      </section>
      ${footnoteAttachHtml}
      ${pathMatrixHtml}
      ${verifyMatrixHtml}
      <details class="alex-ref-panel alex-evidence-panel" style="margin-top:1rem">
        <summary>Evidence &amp; dependency trace</summary>
        <div class="alex-ref-body">
          <details class="alex-ref-panel" style="margin-bottom:1rem">
            <summary>Excel source rows (${tableRows.length})</summary>
            <div class="alex-ref-body grid-wrap">
              <table class="data-grid alex-table"><thead><tr>
                <th>Row</th><th>Condition</th><th>Depth</th><th>Type</th>
              </tr></thead><tbody>${tableRows.map((r) => `<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td></tr>`).join("")}</tbody></table>
            </div>
          </details>
          <h4>Dependency trace</h4>
          ${renderTraceRows(item.trace_rows || [])}
          ${(item.issues || []).length ? `<div style="margin-top:1rem"><h4>Linked issues</h4>${renderIssueList(item.issues || [])}</div>` : ""}
        </div>
      </details>
      <section class="alex-definitions-section">
        <h3 class="alex-section-title">Definitions</h3>
        ${renderDefinitionInbox(inbox, { engineerNote, attachments, assistStatus, logicId: item.logic_id, copilotSession })}
      </section>
      ${renderKnowledgeReconciliationPanel(knowledgeApply)}
      ${renderHypothesisReviewPanel(reasoningRes?.session)}
      <section class="workbook-workspace workbook-workspace--logic" style="margin-top:1rem">
        <h4>Final workbook rows (this logic group)</h4>
        ${renderWorkbookTestcaseBar(logicRows, "logic")}
        ${renderWorkbookFocusEditor(logicRows, { language: state.exportLanguage, scope: "logic" })}
        <p id="logic-row-save-status" class="detail"></p>
      </section>
    </div>`;
    document.querySelectorAll("[data-definition-term]").forEach((btn) => {
      btn.onclick = () => {
        state.inboxFocus[item.logic_id] = btn.getAttribute("data-definition-term") || "";
        renderLogicReview({ skipSummary: true });
      };
    });
    const logicSelect = $("#logic-group-select");
    if (logicSelect) {
      logicSelect.onchange = () => {
        state.selectedLogicId = logicSelect.value;
        state.logicTreeFocus = { nodeId: null, highlightTerms: [], highlightRowNos: [] };
        renderLogicReview({ skipSummary: true });
      };
    }
    bindLogicTreeSourceNavigation(item);
    const simBtn = $("#btn-logic-sim-run");
    if (simBtn) {
      simBtn.onclick = async () => {
        const assignments = {};
        content().querySelectorAll(".logic-sim-input").forEach((inp) => {
          assignments[inp.dataset.simSignal] = inp.value;
        });
        state.pathSimAssignments[item.logic_id] = assignments;
        try {
          const res = await api(`/api/review/logic-simulate?job_id=${encodeURIComponent(state.jobId)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ logic_id: item.logic_id, assignments }),
          });
          state.pathSimResult[item.logic_id] = res;
          const host = document.querySelector(".logic-tree-interactive-host");
          if (host) {
            host.innerHTML = renderInteractiveLogicTree(item, res.active_node_ids || []);
            bindLogicTreeSourceNavigation(item);
            const statusEl = $("#logic-sim-status");
            if (statusEl) {
              const st = res.status || "unknown";
              statusEl.textContent =
                st === "active" ? "Logic path ACTIVE" : st === "inactive" ? "Logic path INACTIVE" : "Partial / unknown";
              statusEl.className = `tag ${st === "active" ? "high" : st === "inactive" ? "error" : "warning"}`;
            }
          } else {
            await renderLogicReview({ skipSummary: true });
          }
        } catch (e) {
          alert(e.message);
        }
      };
    }
    const refUpload = $("#reference-file-upload");
    if (refUpload) {
      refUpload.onchange = async () => {
        if (!refUpload.files.length) return;
        const statusEl = $("#reference-file-status");
        if (statusEl) statusEl.textContent = "Merging reference file…";
        const fd = new FormData();
        for (const f of refUpload.files) fd.append("files", f);
        try {
          const res = await fetch(
            `/api/review/attach-reference-file?job_id=${encodeURIComponent(state.jobId)}&logic_id=${encodeURIComponent(item.logic_id)}`,
            { method: "POST", body: fd }
          );
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          if (statusEl) {
            statusEl.textContent =
              `Merged ${(data.saved || []).length} file(s).` + formatUnderstandingLoopStatus(data.understanding_loop);
          }
          await renderLogicReview();
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        }
        refUpload.value = "";
      };
    }
    const pathProposeBtn = $("#btn-path-tc-propose");
    if (pathProposeBtn) {
      pathProposeBtn.onclick = async () => {
        const statusEl = $("#path-tc-propose-status");
        if (statusEl) statusEl.textContent = "Building proposals…";
        pathProposeBtn.disabled = true;
        try {
          const res = await api(
            `/api/review/path-tc-propose?job_id=${encodeURIComponent(state.jobId)}&logic_id=${encodeURIComponent(item.logic_id)}`,
            { method: "POST" }
          );
          state.pathRegenProposal[item.logic_id] = res;
          if (statusEl) {
            statusEl.textContent = `Proposed ${res.proposed_count || 0} TC(s) for missing paths — review in Knowledge reconciliation when applied.`;
          }
          await renderLogicReview();
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        } finally {
          pathProposeBtn.disabled = false;
        }
      };
    }
    const applyKnowledge = async (statusMessage = "Saving knowledge…", { localOnly = false } = {}) => {
      const note = $("#definition-workbench-note")?.value || "";
      const current = inboxFocusTerm(inbox);
      const statusEl = document.querySelector("[data-definition-query-status]");
      if (statusEl) statusEl.textContent = statusMessage;
      return api(`/api/review/logic-clarification?job_id=${encodeURIComponent(state.jobId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          logic_id: item.logic_id,
          note,
          term: current?.term || "",
          provider: "m365",
          local_only: localOnly,
        }),
      });
    };
    bindOnChange("#logic-attachment-upload", async () => {
      const inp = $("#logic-attachment-upload");
      if (!inp.files.length) return;
      const fd = new FormData();
      for (const f of inp.files) fd.append("files", f);
      const attachStatus = document.querySelector("[data-definition-query-status]");
      if (attachStatus) attachStatus.textContent = "Uploading attachment(s)…";
      try {
        const res = await fetch(`/api/review/logic-attachments?job_id=${encodeURIComponent(state.jobId)}&logic_id=${encodeURIComponent(item.logic_id)}`, {
          method: "POST",
          body: fd,
        });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        if (attachStatus) {
          attachStatus.textContent =
            "Attachment(s) saved." + formatUnderstandingLoopStatus(data.understanding_loop);
        }
        renderLogicReview({ skipSummary: true });
      } catch (e) {
        if (attachStatus) attachStatus.textContent = e.message;
      }
      inp.value = "";
    });
    const localApplyBtn = $("#btn-definition-local-apply");
    if (localApplyBtn) {
      localApplyBtn.onclick = async () => {
        const note = $("#definition-workbench-note")?.value || "";
        const statusEl = document.querySelector("[data-definition-query-status]");
        if (!note.trim()) {
          if (statusEl) statusEl.textContent = "Enter a basic constraint first (e.g. HUY >= 1, < 5).";
          return;
        }
        if (statusEl) statusEl.textContent = "Applying locally…";
        localApplyBtn.disabled = true;
        try {
          const res = await applyKnowledge("Applying locally…", { localOnly: true });
          clearDefinitionDraft(item.logic_id);
          if (statusEl) statusEl.textContent = formatLocalApplyStatus(res);
          await renderLogicReview();
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        } finally {
          localApplyBtn.disabled = false;
        }
      };
    }
    const understandSpecBtn = $("#btn-copilot-understand-spec");
    if (understandSpecBtn) {
      understandSpecBtn.onclick = async () => {
        const note = $("#definition-workbench-note")?.value || "";
        const term = inboxFocusTerm(inbox)?.term || "";
        const statusEl = document.querySelector("[data-definition-query-status]");
        if (!m365KnowledgeReady()) {
          if (statusEl) statusEl.textContent = "Authorize Copilot API trước (Review → Test Copilot API).";
          return;
        }
        understandSpecBtn.disabled = true;
        try {
          await startM365Task({
            kind: "copilot_context_plan",
            label: `Hiểu spec ${item.logic_id}`,
            logicId: item.logic_id,
            targetPage: "logic-review",
            payload: { logic_id: item.logic_id, note, term },
          });
          if (statusEl) statusEl.textContent = "Copilot chạy nền (context + plan) — xem banner trên cùng.";
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        } finally {
          understandSpecBtn.disabled = !m365KnowledgeReady();
        }
      };
    }
    const buildContextBtn = $("#btn-copilot-build-context");
    if (buildContextBtn) {
      buildContextBtn.onclick = async () => {
        const note = $("#definition-workbench-note")?.value || "";
        const term = inboxFocusTerm(inbox)?.term || "";
        const statusEl = document.querySelector("[data-definition-query-status]");
        if (statusEl) statusEl.textContent = "Building context pack…";
        buildContextBtn.disabled = true;
        try {
          const q = new URLSearchParams({
            job_id: state.jobId,
            logic_id: item.logic_id,
            note,
            term,
          });
          const res = await api(`/api/review/copilot/context?${q}`);
          if (res.ok === false) {
            if (statusEl) statusEl.textContent = `[${res.error_category || "error"}] ${res.error || "Build context failed"}`;
            return;
          }
          state.copilotStep[item.logic_id] = "context";
          invalidateApiCache(`copilot-session:${state.jobId}:${item.logic_id}`);
          if (statusEl) statusEl.textContent = "Context ready — review summary, then Generate plan.";
          await renderLogicReview({ skipSummary: true });
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        } finally {
          buildContextBtn.disabled = false;
        }
      };
    }
    const generatePlanBtn = $("#btn-copilot-generate-plan");
    if (generatePlanBtn) {
      generatePlanBtn.onclick = async () => {
        const note = $("#definition-workbench-note")?.value || "";
        const term = inboxFocusTerm(inbox)?.term || "";
        const statusEl = document.querySelector("[data-definition-query-status]");
        if (!m365KnowledgeReady()) {
          if (statusEl) statusEl.textContent = "Sign in to M365 Copilot first.";
          return;
        }
        generatePlanBtn.disabled = true;
        try {
          await startM365Task({
            kind: "copilot_plan",
            label: `Plan ${item.logic_id}`,
            logicId: item.logic_id,
            targetPage: "logic-review",
            payload: { logic_id: item.logic_id, note, term },
          });
          if (statusEl) statusEl.textContent = "Copilot plan chạy nền — xem banner trên cùng.";
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        } finally {
          generatePlanBtn.disabled = !m365KnowledgeReady();
        }
      };
    }
    const savePlanBtn = $("#btn-copilot-save-plan");
    if (savePlanBtn) {
      savePlanBtn.onclick = async () => {
        const statusEl = document.querySelector("[data-definition-query-status]");
        const plan = collectCopilotPlanFromDom();
        if (!plan.plan_items.length) {
          if (statusEl) statusEl.textContent = "No plan rows to save.";
          return;
        }
        if (statusEl) statusEl.textContent = "Saving plan…";
        savePlanBtn.disabled = true;
        try {
          const session = copilotSession || {};
          const merged = { ...(session.plan || {}), ...plan };
          await api(`/api/review/copilot/plan?job_id=${encodeURIComponent(state.jobId)}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ logic_id: item.logic_id, plan: merged }),
          });
          invalidateApiCache(`copilot-session:${state.jobId}:${item.logic_id}`);
          if (statusEl) statusEl.textContent = "Plan saved — you can Write test cases.";
          await renderLogicReview({ skipSummary: true });
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        } finally {
          savePlanBtn.disabled = false;
        }
      };
    }
    const writeDraftsBtn = $("#btn-copilot-write-drafts");
    if (writeDraftsBtn) {
      writeDraftsBtn.onclick = async () => {
        const statusEl = document.querySelector("[data-definition-query-status]");
        if (!m365KnowledgeReady()) {
          if (statusEl) statusEl.textContent = "Sign in to M365 Copilot first.";
          return;
        }
        writeDraftsBtn.disabled = true;
        try {
          await startM365Task({
            kind: "copilot_write",
            label: `Viết testcase ${item.logic_id}`,
            logicId: item.logic_id,
            targetPage: "logic-review",
            payload: { logic_id: item.logic_id },
          });
          if (statusEl) statusEl.textContent = "Copilot viết testcase chạy nền — xem banner trên cùng.";
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        } finally {
          writeDraftsBtn.disabled = !m365KnowledgeReady();
        }
      };
    }
    const followUpBtn = $("#btn-copilot-followup");
    if (followUpBtn) {
      followUpBtn.onclick = async () => {
        const msg = $("#copilot-followup-message")?.value?.trim() || "";
        const statusEl = $("#copilot-followup-status") || document.querySelector("[data-definition-query-status]");
        if (!msg) {
          if (statusEl) statusEl.textContent = "Enter a follow-up message.";
          return;
        }
        if (!m365KnowledgeReady()) {
          if (statusEl) statusEl.textContent = "Authorize Copilot API first.";
          return;
        }
        if (statusEl) statusEl.textContent = "Sending follow-up to Copilot…";
        followUpBtn.disabled = true;
        try {
          const res = await api(`/api/review/copilot/follow-up?job_id=${encodeURIComponent(state.jobId)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ logic_id: item.logic_id, message: msg, reuse_conversation: true }),
          });
          if (!res.ok) {
            const action = res.user_action ? ` — ${res.user_action}` : "";
            if (statusEl) statusEl.textContent = `[${res.error_category || "error"}] ${res.error || "Follow-up failed"}${action}`;
            return;
          }
          const preview = res.reply || res.reply_preview || res.message || "";
          if (statusEl) {
            statusEl.textContent = preview
              ? `Copilot: ${preview.slice(0, 280)}${preview.length > 280 ? "…" : ""}`
              : "Follow-up sent — Copilot replied (see conversation).";
          }
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        } finally {
          followUpBtn.disabled = !m365KnowledgeReady();
        }
      };
    }
    const copyBriefBtn = $("#btn-copilot-copy-brief");
    if (copyBriefBtn) {
      copyBriefBtn.onclick = async () => {
        const note = $("#definition-workbench-note")?.value || "";
        const brief = buildCopilotM365Brief({ engineerNote: note, copilotSession, logicId: item.logic_id });
        const statusEl = $("#copilot-followup-status");
        try {
          await navigator.clipboard.writeText(brief);
          if (statusEl) statusEl.textContent = "M365 brief copied to clipboard.";
        } catch (_) {
          if (statusEl) statusEl.textContent = "Copy failed — select text manually.";
        }
      };
    }
    const applyCopilotBtn = $("#btn-copilot-apply-selected");
    if (applyCopilotBtn) {
      applyCopilotBtn.onclick = async () => {
        const statusEl = document.querySelector("[data-definition-query-status]");
        const indices = [...document.querySelectorAll(".copilot-draft-check:checked")].map((el) =>
          Number(el.dataset.draftIndex)
        );
        if (!indices.length) {
          if (statusEl) statusEl.textContent = "Select at least one draft (non no-op).";
          return;
        }
        if (statusEl) statusEl.textContent = "Applying selected drafts…";
        applyCopilotBtn.disabled = true;
        try {
          const res = await api(`/api/review/copilot/confirm?job_id=${encodeURIComponent(state.jobId)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ logic_id: item.logic_id, draft_indices: indices }),
          });
          if (!res.ok) throw new Error((res.errors || []).join("; ") || "Apply failed");
          if (statusEl) {
            statusEl.textContent =
              `Applied ${res.applied_count || indices.length} draft(s); updated ${res.candidates_updated || 0}, added ${res.candidates_added || 0}.` +
              formatUnderstandingLoopStatus(res.understanding_loop);
          }
          invalidateApiCache(`copilot-session:${state.jobId}:${item.logic_id}`);
          await renderLogicReview();
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        } finally {
          applyCopilotBtn.disabled = false;
        }
      };
    }
    const styleSampleUpload = $("#style-sample-upload");
    if (styleSampleUpload) {
      styleSampleUpload.onchange = async () => {
        if (!styleSampleUpload.files.length) return;
        const statusEl = document.querySelector("[data-definition-query-status]");
        try {
          const text = await styleSampleUpload.files[0].text();
          let samples = [];
          try {
            const parsed = JSON.parse(text);
            samples = Array.isArray(parsed) ? parsed : parsed.samples || [parsed];
          } catch {
            samples = [{ label: "upload", expected_input: text.slice(0, 2000) }];
          }
          await api(`/api/review/style-samples?job_id=${encodeURIComponent(state.jobId)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ samples }),
          });
          if (statusEl) statusEl.textContent = `Saved ${samples.length} style sample(s). Rebuild context before Write.`;
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        }
        styleSampleUpload.value = "";
      };
    }
    const applySelectedBtn = $("#btn-knowledge-apply-selected");
    if (applySelectedBtn) {
      applySelectedBtn.onclick = async () => {
        const statusEl = $("#knowledge-reconcile-status");
        const indices = [...document.querySelectorAll(".knowledge-patch-check:checked")].map((el) =>
          Number(el.dataset.patchIndex)
        );
        if (!indices.length) {
          if (statusEl) statusEl.textContent = "Select at least one patch.";
          return;
        }
        if (statusEl) statusEl.textContent = "Applying selected patches…";
        applySelectedBtn.disabled = true;
        try {
          const res = await api(
            `/api/review/knowledge-apply/confirm?job_id=${encodeURIComponent(state.jobId)}`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ logic_id: item.logic_id, patch_indices: indices }),
            }
          );
          const firstCid = (knowledgeApply.diffs || []).find((d) => indices.includes(d.patch_index))?.candidate_id;
          if (firstCid) state.workbookFocus.logic = firstCid;
          if (statusEl) {
            statusEl.textContent =
              `Applied ${res.applied_patch_count || indices.length} patch(es); updated ${res.candidates_updated || 0} TC(s).` +
              formatUnderstandingLoopStatus(res.understanding_loop);
          }
          await renderLogicReview();
          document.querySelector(".workbook-row.is-focused")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        } finally {
          applySelectedBtn.disabled = false;
        }
      };
    }
    const rejectAllBtn = $("#btn-knowledge-reject-all");
    if (rejectAllBtn) {
      rejectAllBtn.onclick = async () => {
        const statusEl = $("#knowledge-reconcile-status");
        if (statusEl) statusEl.textContent = "Rejecting pending patches…";
        try {
          await api(`/api/review/knowledge-apply/reject?job_id=${encodeURIComponent(state.jobId)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ logic_id: item.logic_id, patch_indices: [] }),
          });
          if (statusEl) statusEl.textContent = "Pending patches rejected.";
          await renderLogicReview();
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        }
      };
    }
    const acceptClaimsBtn = $("#btn-hypothesis-accept-claims");
    if (acceptClaimsBtn) {
      acceptClaimsBtn.onclick = async () => {
        const statusEl = $("#hypothesis-review-status");
        const indices = [...document.querySelectorAll(".hypothesis-claim-check:checked")].map((el) =>
          Number(el.dataset.claimIndex)
        );
        if (!indices.length) {
          if (statusEl) statusEl.textContent = "Select at least one claim.";
          return;
        }
        if (statusEl) statusEl.textContent = "Applying accepted claims…";
        try {
          const res = await api(`/api/reasoning/accept-claims?job_id=${encodeURIComponent(state.jobId)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ logic_id: item.logic_id, claim_indices: indices }),
          });
          if (statusEl) {
            statusEl.textContent =
              `Applied ${(res.applied_terms || []).length} term(s); refreshed ${res.definitions_applied || 0} TC(s).` +
              formatUnderstandingLoopStatus(res.understanding_loop);
          }
          await renderLogicReview();
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        }
      };
    }
    const pasteHypothesisBtn = $("#btn-hypothesis-paste-json");
    if (pasteHypothesisBtn) {
      pasteHypothesisBtn.onclick = async () => {
        const raw = window.prompt("Paste hypothesis JSON (claims, open_questions, testcase_patch_plan):");
        if (!raw?.trim()) return;
        const statusEl = $("#hypothesis-review-status");
        try {
          const hypothesis = JSON.parse(raw);
          await api(`/api/reasoning/hypothesis?job_id=${encodeURIComponent(state.jobId)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ logic_id: item.logic_id, hypothesis, provider: "manual" }),
          });
          if (statusEl) statusEl.textContent = "Hypothesis saved for review.";
          await renderLogicReview();
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message || "Invalid JSON.";
        }
      };
    }
    bindWorkbookFocusEditor(logicRows, state.exportLanguage, "logic", renderLogicReview, "#logic-row-save-status");
    bindVerificationMatrixPromote(item.logic_id);
    bindDefinitionDraftAutosave(item.logic_id);
    bindTabHelpLinks();
  } catch (e) {
    content().innerHTML = `<p class="detail" style="color:var(--red)">${esc(e.message)}</p>`;
  }
}

function exportFormatCard(title, desc, iconName, url, lang) {
  return `<article class="export-format-card">
    <span class="export-format-card__check" aria-hidden="true">${icon("check-circle", "alex-icon--export")}</span>
    ${icon(iconName, "alex-icon--export")}
    <h4 class="export-format-card__title">${esc(title)}</h4>
    <p class="export-format-card__desc">${esc(desc)}</p>
    <button type="button" class="btn secondary btn-with-icon export-dl" data-url="${esc(url)}">${icon("download", "alex-icon--btn")} Download ${esc(lang)}</button>
  </article>`;
}

function downloadLink(label, url) {
  return `<button type="button" class="btn export-dl btn-with-icon" data-url="${esc(url)}">${icon("download", "alex-icon--btn")} ${esc(label)}</button>`;
}

async function triggerDownload(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error((await r.text()) || `HTTP ${r.status}`);
  const blob = await r.blob();
  const cd = r.headers.get("content-disposition") || "";
  const m = cd.match(/filename="?([^";]+)"?/);
  const name = m ? m[1] : "download";
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function renderExport() {
  if (!state.jobId) {
    content().innerHTML = requireJobHtml("no_job");
    bindNoJob();
    return;
  }
  await refreshJobSummary();
  const [dash, preview] = await Promise.all([
    api(`/api/review/dashboard?job_id=${encodeURIComponent(state.jobId)}`).catch(() => ({})),
    fetchWorkbench(state.exportLanguage),
  ]);
  const moduleName = dash.module_name || "Module";
  const overlayCount = dash.copilot_overlay_count || 0;
  const summary = preview.summary || {};
  const q = encodeURIComponent(state.jobId);
  const rows = preview.rows || [];
  content().innerHTML = `<div class="alex-export-page">
    <header class="alex-hero alex-export-hero">
      <div>
        <h2 class="alex-hero__title">Final TestSpec</h2>
        <p class="alex-hero__sub">${esc(moduleName)} · ${rows.length} test case(s) · ${esc(preview.language || state.exportLanguage)}</p>
      </div>
      <div class="alex-hero__actions">
        <button type="button" class="btn secondary btn-with-icon" id="btn-translate-workbook-jp" ${assistEnabled() ? "" : "disabled"} title="Experimental: translate all rows to Japanese via M365 Copilot (may be slow)">${icon("translate", "alex-icon--btn")} Translate to Japanese</button>
      </div>
    </header>
    ${renderMetricCards([
      ["Rows ready", summary.rows_ready ?? 0, "ok"],
      ["Blocked", summary.rows_blocked ?? 0, "error"],
      ["Needs review", summary.rows_needing_review ?? 0, "warn"],
      ["Missing terms", summary.missing_terms ?? 0, "warn"],
      ["AI overlays", overlayCount, "cyan"],
      ...(preview.validation_summary && featureOn("validator")
        ? [
            ["I/O avg score", preview.validation_summary.avg_quality_score ?? "—", "cyan"],
            ["I/O failed rows", preview.validation_summary.rows_failed ?? 0, "error"],
          ]
        : []),
    ])}
    <div data-copilot-assist></div>
    <section class="workbook-workspace workbook-workspace--export">
      ${renderWorkbookTestcaseBar(rows, "export")}
      ${renderWorkbookFocusEditor(rows, { language: preview.language || state.exportLanguage, scope: "export" })}
      <p id="export-row-save-status" class="detail"></p>
      <div class="workbook-review-panel">
        <div class="workbook-review-panel__head">
          <h4 class="workbook-review-panel__title">Review all rows (${rows.length})</h4>
          <label class="workbook-review-panel__lang detail">View language
            <select id="export-draft-language">
              <option value="EN" ${state.exportLanguage === "EN" ? "selected" : ""}>English</option>
              <option value="JP" ${state.exportLanguage === "JP" ? "selected" : ""}>Japanese</option>
            </select>
          </label>
        </div>
        <p class="detail workbook-review-panel__hint">Click a row to edit in the editor above. Hover cells for full text.</p>
        ${renderWorkbookTable(rows, {
          language: preview.language || state.exportLanguage,
          editable: true,
          tableId: "export-workbook",
          spreadsheet: true,
        })}
      </div>
    </section>
    <section class="export-format-section">
      <h3 class="section-kicker">Export format</h3>
      <div class="export-format-grid">
        ${exportFormatCard(
          "Excel (.xlsx)",
          "Full structured export with all sheets",
          "excel",
          `/api/export/customer-testspec-xlsx?job_id=${q}&language=EN`,
          "EN"
        )}
        ${exportFormatCard(
          "Excel (.xlsx)",
          "Full structured export — Japanese workbook",
          "excel",
          `/api/export/customer-testspec-xlsx?job_id=${q}&language=JP`,
          "JP"
        )}
      </div>
    </section>
    <p id="export-status" class="detail"></p>
  </div>`;
  content().querySelectorAll(".export-dl").forEach((btn) => {
    btn.onclick = async () => {
      $("#export-status").textContent = "Downloading…";
      try {
        await triggerDownload(btn.dataset.url);
        $("#export-status").textContent = "OK";
      } catch (e) {
        $("#export-status").textContent = "Failed: " + e.message;
      }
    };
  });
  bindOnChange("#export-draft-language", (e) => {
    state.exportLanguage = e.target.value;
    renderExport();
  });
  const translateBtn = $("#btn-translate-workbook-jp");
  if (translateBtn) {
    translateBtn.onclick = async () => {
      if (!assistEnabled()) {
        $("#export-status").textContent = "Sign in to Microsoft 365 Copilot on the Review tab to translate.";
        return;
      }
      translateBtn.disabled = true;
      $("#export-status").textContent = `Translating ${rows.length} row(s) to Japanese via M365 Copilot…`;
      try {
        const res = await api(
          `/api/review/translate-workbook?job_id=${encodeURIComponent(state.jobId)}&target_language=JP`,
          { method: "POST" }
        );
        const errCount = (res.errors || []).length;
        $("#export-status").textContent = res.ok
          ? `Translated ${res.rows_updated ?? 0} of ${res.rows_total ?? rows.length} row(s) to Japanese.${errCount ? ` ${errCount} failed.` : ""}`
          : res.error || "Translation failed.";
        state.exportLanguage = "JP";
        await renderExport();
      } catch (e) {
        $("#export-status").textContent = e.message;
        translateBtn.disabled = false;
      }
    };
  }
  bindWorkbookEditors(rows, state.exportLanguage, "#export-row-save-status");
  bindWorkbookColumnResize("export-workbook");
  bindWorkbookTableRowFocus(rows, "export", "export-workbook", renderExport);
  bindWorkbookFocusEditor(rows, state.exportLanguage, "export", renderExport, "#export-row-save-status");
  bindTabHelpLinks();
}

function openTestCodeForCandidate(candidateId, logicId) {
  state.testCode.selectedCandidateId = candidateId || null;
  if (logicId) state.testCode.selectedLogicId = logicId;
  state.workbookFocus.testcode = candidateId;
  showPage("test-code");
}

async function fetchGtestWorkspace(force = false) {
  const lang = state.exportLanguage || "EN";
  const key = `gtest-ws:${state.jobId}:${lang}`;
  if (force) invalidateApiCache(key);
  const data = await cachedApi(
    key,
    () =>
      api(
        `/api/review/gtest-workspace?job_id=${encodeURIComponent(state.jobId)}&language=${encodeURIComponent(lang)}`
      ),
    API_CACHE_TTL.gtestWorkspace
  );
  state.testCode.workspace = data;
  state.testCode.variableMapDraft = { ...(data.code_variable_map || {}) };
  state.testCode.harnessDraft = { ...(data.harness || {}) };
  state.testCode.codeStyleSamples = data.code_style_samples || [];
  if (data.copilot_batch?.last_results) state.testCode.batchResults = data.copilot_batch.last_results;
  return data;
}

function applyTestCodeDraftToUi(draft, row) {
  const commentEl = $("#testcode-spec-comments");
  const codeEl = $("#testcode-code-editor");
  if (commentEl && draft) commentEl.value = draft.spec_comment_block || "";
  if (codeEl && draft) {
    state._suppressTestCodeEditorInput = true;
    codeEl.value = draft.full_snippet || draft.code_body || "";
    state._suppressTestCodeEditorInput = false;
  }
  const strip = document.getElementById("testcode-io-context");
  if (strip && row) strip.outerHTML = renderTestCodeIoContext(row);
  const logicSel = $("#testcode-logic-select");
  if (logicSel && state.testCode.selectedLogicId) logicSel.value = state.testCode.selectedLogicId;
  const headName = document.querySelector(".alex-testcode-editor__head > .detail");
  if (headName && draft) {
    headName.textContent = draft.test_name || row?.candidate_id || "TEST_F snippet";
  }
  document.querySelector(".alex-testcode-editor__head .tag.warning")?.remove();
  if (draft?.unmapped_signals?.length) {
    document.querySelector(".alex-testcode-editor__head")?.insertAdjacentHTML(
      "beforeend",
      `<span class="tag warning">Unmapped: ${draft.unmapped_signals.map((s) => esc(s)).join(", ")}</span>`
    );
  }
  patchTestCodeCaseStatusUi();
}

async function switchTestCodeCandidate(candidateId, rows = state.testCode.rows || []) {
  if (!candidateId || state.testCode.switching) return;
  const prevId = state.testCode.selectedCandidateId;
  if (prevId && prevId !== candidateId) {
    stashTestCodeEditor(prevId);
    if (state.testCode.dirtyMap?.[prevId]) {
      const ok = window.confirm(
        `Unsaved changes on ${prevId}. Switch testcase anyway? Edits stay stashed for that testcase.`
      );
      if (!ok) return;
    }
  }
  if (candidateId === prevId && state.testCode.draft != null && !state.testCode.dirtyMap?.[prevId]) {
    return;
  }
  state.testCode.switching = true;
  state.testCode.selectedCandidateId = candidateId;
  state.workbookFocus.testcode = candidateId;
  const row = rows.find((r) => r.candidate_id === candidateId);
  if (row?.logic_id) state.testCode.selectedLogicId = row.logic_id;
  const statusEl = $("#testcode-status");
  if (statusEl) statusEl.textContent = "Loading…";
  try {
    const draft = resolveDraftForCandidate(candidateId);
    state.testCode.draft = draft;
    state.testCode.lastDraftKey = candidateId;
    applyTestCodeDraftToUi(draft, row);
    patchTestCodeCaseStatusUi();
    refreshTestCodePromptPreview(rows);
    if (statusEl) {
      const wf = computeTestCodeWorkflowStatus(candidateId);
      statusEl.textContent = `Selected ${candidateId} [${wf}]. Steps 2–3 → generate → Step 4 Save.`;
    }
  } catch (e) {
    if (statusEl) statusEl.textContent = e.message;
  } finally {
    state.testCode.switching = false;
  }
}

function renderTestCodeHelpCard(title, bodyHtml, primaryLabel, primaryAction) {
  return `<div class="card alex-testcode-empty">
    <h3>${esc(title)}</h3>
    ${bodyHtml}
    <div class="review-actions" style="margin-top:1rem">
      <button class="btn" type="button" id="${primaryAction}">${esc(primaryLabel)}</button>
    </div>
  </div>`;
}

function bindTestCodeHelp(actionId, fn) {
  const btn = document.getElementById(actionId);
  if (btn) btn.onclick = fn;
}

function explainTestCodeError(message) {
  const msg = String(message || "");
  if (msg === "Not Found") {
    return `<p class="detail">The Test Code API is unavailable. This usually means the ALEX server is running an older build.</p>
      <ul class="alex-guide-steps">
        <li>Stop the server and restart: <code>python -m uvicorn web.main:app --host 127.0.0.1 --port 8765</code></li>
        <li>Hard refresh the browser (Cmd+Shift+R)</li>
      </ul>`;
  }
  if (/job not found|no analysis bundle/i.test(msg)) {
    return `<p class="detail">This review job no longer exists or analysis has not finished.</p>
      <ul class="alex-guide-steps">
        <li>Open <b>Review</b> and run <b>Review specification</b> again</li>
        <li>Wait until progress completes, then return to Test Code</li>
      </ul>`;
  }
  return `<p class="detail">${esc(msg)}</p>`;
}

async function regenerateGtestDraft(force = false) {
  const tc = state.testCode;
  const cacheKey = `${tc.selectedCandidateId || ""}:${tc.selectedLogicId || ""}:${JSON.stringify(tc.variableMapDraft || {})}`;
  if (!force && tc.draftCache[cacheKey]) {
    tc.draft = tc.draftCache[cacheKey];
    return tc.draft;
  }
  const body = {
    candidate_id: tc.selectedCandidateId || null,
    logic_id: tc.selectedLogicId || null,
    variable_map: tc.variableMapDraft || {},
  };
  if (!body.candidate_id && !body.logic_id) return null;
  const res = await api(`/api/review/gtest-generate?job_id=${encodeURIComponent(state.jobId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  tc.draft = res.draft || null;
  if (tc.draft) tc.draftCache[cacheKey] = tc.draft;
  return tc.draft;
}

function renderTestCodeVariableMapRows(map) {
  const entries = Object.entries(map || {}).sort(([a], [b]) => a.localeCompare(b));
  if (!entries.length) {
    return `<tr><td colspan="3" class="detail gtest-map-empty">Empty — defaults use <code>in.SIG</code> / <code>out.SIG</code>. Click <b>Suggest</b> only when spec name ≠ code symbol.</td></tr>`;
  }
  return entries
    .map(
      ([spec, code], idx) => `<tr data-var-row="${idx}">
      <td><input class="gtest-input gtest-map-spec" data-var-idx="${idx}" value="${esc(spec)}" placeholder="SPEC_SIG" /></td>
      <td><input class="gtest-input gtest-map-code" data-var-idx="${idx}" value="${esc(code)}" placeholder="in.SPEC_SIG" /></td>
      <td class="gtest-map-del"><button type="button" class="btn secondary btn-inline gtest-map-del-btn" data-var-remove="${idx}" title="Remove">×</button></td>
    </tr>`
    )
    .join("");
}

function pickPreferredTestCodeRow(rows) {
  if (!rows?.length) return null;
  return (
    rows.find((r) => r.review_status === "approved") ||
    rows.find((r) => r.review_status === "ready") ||
    rows[0]
  );
}

const TC_WF = {
  NO_CODE: "NO_CODE",
  DRAFT: "DRAFT",
  SAVED: "SAVED",
  MODIFIED_UNSAVED: "MODIFIED_UNSAVED",
  NEEDS_REVIEW: "NEEDS_REVIEW",
  ERROR: "ERROR",
};

function getTestCodeDraftRecord(cid) {
  return (state.testCode.workspace?.drafts || {})[cid] || {};
}

function isLegacyTestCodeDraft(cid) {
  const draft = getTestCodeDraftRecord(cid);
  const has = String(draft.full_snippet || draft.code_body || "").trim().length > 0;
  return has && !String(draft.code_status || "").trim();
}

function formatTestCodeTimestamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function hydrateTestCodeWorkflowFromWorkspace(ws, { fullReset = false } = {}) {
  const tc = state.testCode;
  if (fullReset) {
    tc.dirtyMap = {};
    tc.stashedEdits = {};
    tc.savedSnapshot = {};
    tc.generationSource = {};
  }
  if (!tc.generationSource) tc.generationSource = {};
  if (!tc.savedSnapshot) tc.savedSnapshot = {};
  for (const [cid, draft] of Object.entries(ws?.drafts || {})) {
    if (draft?.generation_source) tc.generationSource[cid] = draft.generation_source;
    const text = String(draft?.full_snippet || draft?.code_body || "");
    if (text && fullReset) tc.savedSnapshot[cid] = text;
  }
}

function renderTestCodeCaseMeta(cid, row) {
  if (!cid) return "";
  const draft = getTestCodeDraftRecord(cid);
  const wf = computeTestCodeWorkflowStatus(cid);
  const event = row?.event || row?.test_function || "";
  const parts = [
    `<p class="alex-testcode-case-title"><code>${esc(cid)}</code> ${esc(event)} <span class="tag ${testCodeWorkflowTagClass(wf)} testcode-wf-badge">[${esc(testCodeWorkflowLabel(wf))}]</span></p>`,
  ];
  if (draft.last_saved_at) {
    parts.push(`<p class="detail testcode-case-meta-line">Last saved: ${esc(formatTestCodeTimestamp(draft.last_saved_at))}</p>`);
  }
  if (draft.generation_source) {
    parts.push(`<p class="detail testcode-case-meta-line">Source: ${esc(draft.generation_source)}</p>`);
  }
  if (isLegacyTestCodeDraft(cid) && !state.testCode.dirtyMap?.[cid]) {
    parts.push(`<p class="detail testcode-legacy-hint">Legacy draft — click Save Code to mark as SAVED.</p>`);
  }
  return `<div class="alex-testcode-case-meta" id="testcode-case-meta">${parts.join("")}</div>`;
}

function mergedExportFilename(preview) {
  const job = String(state.jobId || "job").replace(/[^\w.-]+/g, "_");
  const ts = String(preview?.timestamp || new Date().toISOString()).replace(/[:.]/g, "-").slice(0, 19);
  return `ALEX_GTest_${job}_${ts}.cpp`;
}

function getTestCodeEditorContent(cid) {
  if (!cid) return "";
  const tc = state.testCode;
  if (cid === tc.selectedCandidateId) {
    return String($("#testcode-code-editor")?.value || "").trim();
  }
  if (tc.stashedEdits && tc.stashedEdits[cid] != null) {
    return String(tc.stashedEdits[cid]).trim();
  }
  const draft = getTestCodeDraftRecord(cid);
  return String(draft.full_snippet || draft.code_body || "").trim();
}

function computeTestCodeWorkflowStatus(cid) {
  if (!cid) return TC_WF.NO_CODE;
  const tc = state.testCode;
  if (tc.errorMap?.[cid]?.length) return TC_WF.ERROR;
  if (tc.dirtyMap?.[cid]) {
    const codeStatus = String(getTestCodeDraftRecord(cid).code_status || "").toUpperCase();
    return codeStatus === "SAVED" ? TC_WF.MODIFIED_UNSAVED : TC_WF.DRAFT;
  }

  const content = getTestCodeEditorContent(cid);
  const draft = getTestCodeDraftRecord(cid);
  const persisted = String(draft.full_snippet || draft.code_body || "").trim();
  const codeStatus = String(draft.code_status || "").toUpperCase();

  if (!content && !persisted) return TC_WF.NO_CODE;

  const syncSt = testCodeSyncStatusFor(cid);
  if (codeStatus === "SAVED") {
    if (syncSt === "stale_comment" || syncSt === "stale_body" || syncSt === "orphan_code") {
      return TC_WF.NEEDS_REVIEW;
    }
    return TC_WF.SAVED;
  }
  if (syncSt === "stale_comment" || syncSt === "stale_body") return TC_WF.NEEDS_REVIEW;
  if (isLegacyTestCodeDraft(cid)) return TC_WF.DRAFT;
  if (content || persisted) return TC_WF.DRAFT;
  return TC_WF.NO_CODE;
}

function testCodeWorkflowLabel(wf) {
  return wf || TC_WF.NO_CODE;
}

function testCodeWorkflowTagClass(wf) {
  if (wf === TC_WF.SAVED) return "ok";
  if (wf === TC_WF.MODIFIED_UNSAVED || wf === TC_WF.NEEDS_REVIEW) return "warning";
  if (wf === TC_WF.ERROR) return "error";
  return "testcode-wf-neutral";
}

function testCodeFilterMatches(wf, filter) {
  if (filter === "all") return true;
  if (filter === "no_code") return wf === TC_WF.NO_CODE;
  if (filter === "has_code") return [TC_WF.SAVED, TC_WF.DRAFT, TC_WF.MODIFIED_UNSAVED].includes(wf);
  if (filter === "needs_review") return wf === TC_WF.NEEDS_REVIEW;
  if (filter === "unsaved") return wf === TC_WF.MODIFIED_UNSAVED;
  return true;
}

function computeTestCodeProgress(rows) {
  const c = { total: rows.length, saved: 0, draft: 0, no_code: 0, unsaved: 0, review: 0 };
  for (const row of rows || []) {
    const wf = computeTestCodeWorkflowStatus(row.candidate_id);
    if (wf === TC_WF.SAVED) c.saved++;
    else if (wf === TC_WF.DRAFT) c.draft++;
    else if (wf === TC_WF.NO_CODE) c.no_code++;
    else if (wf === TC_WF.MODIFIED_UNSAVED) c.unsaved++;
    else if (wf === TC_WF.NEEDS_REVIEW) c.review++;
  }
  return c;
}

function renderTestCodeProgressSummaryText(rows) {
  const c = computeTestCodeProgress(rows);
  return `Code progress: Total: ${c.total} | Saved: ${c.saved} | Draft: ${c.draft} | No code: ${c.no_code} | Unsaved: ${c.unsaved} | Review: ${c.review}`;
}

function stashTestCodeEditor(cid) {
  if (!cid) return;
  const text = $("#testcode-code-editor")?.value ?? "";
  if (!state.testCode.stashedEdits) state.testCode.stashedEdits = {};
  state.testCode.stashedEdits[cid] = text;
}

function markTestCodeDirty() {
  if (state._suppressTestCodeEditorInput) return;
  const cid = state.testCode.selectedCandidateId;
  if (!cid) return;
  if (!state.testCode.dirtyMap) state.testCode.dirtyMap = {};
  state.testCode.dirtyMap[cid] = true;
  stashTestCodeEditor(cid);
  patchTestCodeCaseStatusUi();
}

function clearTestCodeDirty(cid, savedText) {
  if (!state.testCode.dirtyMap) state.testCode.dirtyMap = {};
  state.testCode.dirtyMap[cid] = false;
  if (!state.testCode.stashedEdits) state.testCode.stashedEdits = {};
  state.testCode.stashedEdits[cid] = savedText;
  if (!state.testCode.savedSnapshot) state.testCode.savedSnapshot = {};
  state.testCode.savedSnapshot[cid] = savedText;
  patchTestCodeCaseStatusUi();
}

function resolveDraftForCandidate(cid) {
  const saved = getTestCodeDraftRecord(cid);
  const stashed = state.testCode.stashedEdits?.[cid];
  const full = stashed != null ? stashed : String(saved.full_snippet || saved.code_body || "");
  const bodyStart = full.indexOf("TEST_F(");
  const testStart = full.indexOf("TEST(");
  const idx = bodyStart >= 0 ? bodyStart : testStart >= 0 ? testStart : -1;
  return {
    ...saved,
    test_name: saved.test_name || cid,
    full_snippet: full,
    code_body: idx >= 0 ? full.slice(idx) : full,
  };
}

function inferGenerationSourceForSave(key) {
  const tc = state.testCode;
  if (tc.generationSource?.[key]) return tc.generationSource[key];
  if (tc.copilotDraft?.full_snippet && $("#testcode-code-editor")?.value === tc.copilotDraft.full_snippet) {
    return "COPILOT_WEB";
  }
  if (tc.apiGenStatus === "done") return "API";
  return "MANUAL";
}

function testCodeStatusIcon(status) {
  const wf = typeof status === "string" && status.includes("_") ? status : computeTestCodeWorkflowStatus(status);
  if (wf === TC_WF.SAVED) return "✓";
  if (wf === TC_WF.NEEDS_REVIEW) return "⚠";
  if (wf === TC_WF.MODIFIED_UNSAVED) return "●";
  if (wf === TC_WF.DRAFT) return "◐";
  if (wf === TC_WF.ERROR) return "!";
  return "○";
}

function testCodeStatusKind(status) {
  const wf = typeof status === "string" && Object.values(TC_WF).includes(status) ? status : computeTestCodeWorkflowStatus(status);
  if (wf === TC_WF.NO_CODE) return "no_code";
  if (wf === TC_WF.NEEDS_REVIEW) return "needs_review";
  if (wf === TC_WF.MODIFIED_UNSAVED) return "unsaved";
  if ([TC_WF.SAVED, TC_WF.DRAFT, TC_WF.MODIFIED_UNSAVED].includes(wf)) return "has_code";
  return "no_code";
}

function testCodeStatusLabel(status) {
  const wf = typeof status === "string" && Object.values(TC_WF).includes(status) ? status : computeTestCodeWorkflowStatus(status);
  return testCodeWorkflowLabel(wf);
}

function testCodeStatusTagClass(status) {
  const wf = typeof status === "string" && Object.values(TC_WF).includes(status) ? status : computeTestCodeWorkflowStatus(status);
  return testCodeWorkflowTagClass(wf);
}

function testCodeRowsForFilter(rows) {
  const filter = state.testCode.caseFilter || "all";
  const ordered = testCodeRowOrder(rows);
  if (filter === "all") return ordered;
  return ordered.filter((row) => testCodeFilterMatches(computeTestCodeWorkflowStatus(row.candidate_id), filter));
}

function navigateTestCodeCase(rows, delta) {
  const pool = testCodeRowsForFilter(rows);
  const cid = state.testCode.selectedCandidateId;
  const idx = pool.findIndex((r) => r.candidate_id === cid);
  if (idx < 0 && pool.length) {
    switchTestCodeCandidate(pool[0].candidate_id, rows);
    return;
  }
  const next = pool[idx + delta];
  if (next?.candidate_id) switchTestCodeCandidate(next.candidate_id, rows);
}

function showTestCodeValidationResult(val) {
  const valEl = document.getElementById("testcode-validation");
  if (!valEl) return;
  valEl.hidden = false;
  valEl.innerHTML = renderTestCodeValidation(val);
}

function applyImportedCopilotToEditor(rows) {
  const tc = state.testCode;
  const statusEl = $("#testcode-status");
  const paste = $("#testcode-copilot-import")?.value || "";
  const { code, assumptions } = parseCopilotCppPaste(paste);
  if (!code) {
    if (statusEl) statusEl.textContent = "Paste a Copilot cpp block in Step 3 first.";
    return;
  }
  const cid = tc.selectedCandidateId;
  const editor = $("#testcode-code-editor");
  if (editor) {
    editor.value = code;
    editor.classList.add("field-copilot-changed");
  }
  if (cid) {
    if (!tc.generationSource) tc.generationSource = {};
    tc.generationSource[cid] = "COPILOT_WEB";
    if (!tc.stashedEdits) tc.stashedEdits = {};
    tc.stashedEdits[cid] = code;
    if (!tc.dirtyMap) tc.dirtyMap = {};
    tc.dirtyMap[cid] = true;
  }
  tc.copilotDraft = { full_snippet: code, assumptions, provider: "manual_import" };
  const sampleSnippet = tc.codeStyleSamples?.[0]?.snippet || tc.workspace?.code_style_samples?.[0]?.snippet || "";
  showTestCodeValidationResult(validateGtestBeforeSave(code, tc.selectedCandidateId, sampleSnippet));
  const assumeNote = assumptions.length ? ` Assumptions: ${assumptions.slice(0, 2).join("; ")}` : "";
  if (statusEl) statusEl.textContent = `Imported to editor.${assumeNote} Review in Step 4 → Save Code.`;
  patchTestCodeCaseStatusUi();
}

function setTestCodeApiStatus(status, message = "") {
  state.testCode.apiGenStatus = status;
  const el = $("#testcode-api-status");
  if (!el) return;
  const labels = { idle: "Idle", running: "Running…", failed: "Failed", done: "Done" };
  const cls = { idle: "", running: "warning", failed: "error", done: "ok" };
  el.innerHTML = `<span class="tag ${cls[status] || ""}">${esc(labels[status] || status)}</span>${message ? ` <span class="detail">${esc(message)}</span>` : ""}`;
}

function renderTestCodeEditorStatusBadge(candidateId) {
  const wf = computeTestCodeWorkflowStatus(candidateId);
  const label = testCodeWorkflowLabel(wf);
  const cls = testCodeWorkflowTagClass(wf);
  const dirty = state.testCode.dirtyMap?.[candidateId];
  const unsavedNote = dirty ? `<span class="tag warning testcode-unsaved-hint">Unsaved changes</span>` : "";
  return `<span class="testcode-editor-status-wrap" id="testcode-editor-status-wrap"><span class="tag ${cls} testcode-editor-status testcode-wf-badge" id="testcode-editor-status">[${esc(label)}]</span>${unsavedNote}</span>`;
}

function renderTestCodeCaseBar(rows) {
  if (!rows?.length) return "";
  const activeId = state.testCode.selectedCandidateId || currentFocusRow(rows, "testcode")?.candidate_id;
  const activeWf = computeTestCodeWorkflowStatus(activeId);
  const caseFilter = state.testCode.caseFilter || "all";
  const dirty = state.testCode.dirtyMap?.[activeId];
  return `<p class="detail alex-testcode-progress" id="testcode-code-progress">${esc(renderTestCodeProgressSummaryText(rows))}</p>
  <div class="alex-testcode-step1-controls" data-tcase-scope="testcode">
    <label class="tcase-select-label">Test case
      <select class="clarify-box tcase-select" data-tcase-select="testcode">
        ${rows
          .map((row) => {
            const cid = row.candidate_id || "";
            const wf = computeTestCodeWorkflowStatus(cid);
            const event = row.event || row.test_function || "";
            const label = `${cid} ${event} [${wf}]`.trim();
            return `<option value="${esc(cid)}" ${cid === activeId ? "selected" : ""}>${esc(label)}</option>`;
          })
          .join("")}
      </select>
    </label>
    <span class="tag ${testCodeWorkflowTagClass(activeWf)} testcode-wf-badge" id="testcode-case-status-badge">[${esc(testCodeWorkflowLabel(activeWf))}]</span>
    ${dirty ? `<span class="tag warning testcode-unsaved-hint" id="testcode-unsaved-hint">Unsaved changes</span>` : `<span id="testcode-unsaved-hint" hidden></span>`}
  </div>
  ${renderTestCodeCaseMeta(activeId, rows.find((r) => r.candidate_id === activeId))}
  <div class="alex-testcode-step1-nav">
    <button type="button" class="btn secondary btn-inline" id="btn-testcode-prev-case">Previous case</button>
    <button type="button" class="btn secondary btn-inline" id="btn-testcode-next-case">Next case</button>
    <div class="alex-testcode-filters">
      <button type="button" class="btn secondary btn-inline testcode-case-filter ${caseFilter === "all" ? "active" : ""}" data-case-filter="all">All</button>
      <button type="button" class="btn secondary btn-inline testcode-case-filter ${caseFilter === "no_code" ? "active" : ""}" data-case-filter="no_code">No code</button>
      <button type="button" class="btn secondary btn-inline testcode-case-filter ${caseFilter === "has_code" ? "active" : ""}" data-case-filter="has_code">Has code</button>
      <button type="button" class="btn secondary btn-inline testcode-case-filter ${caseFilter === "unsaved" ? "active" : ""}" data-case-filter="unsaved">Unsaved</button>
      <button type="button" class="btn secondary btn-inline testcode-case-filter ${caseFilter === "needs_review" ? "active" : ""}" data-case-filter="needs_review">Needs review</button>
    </div>
  </div>`;
}

function renderTestCodeIoContext(row) {
  if (!row) {
    return `<p class="detail">Select a test case to view Before / After context.</p>`;
  }
  return `<div class="alex-testcode-io-context" id="testcode-io-context">
    <label class="alex-testcode-io-block">Before (expected input)
      <textarea class="gtest-input alex-testcode-io-readonly" rows="10" readonly spellcheck="false">${esc(row.expected_input || "")}</textarea>
    </label>
    <label class="alex-testcode-io-block">After (expected output)
      <textarea class="gtest-input alex-testcode-io-readonly" rows="8" readonly spellcheck="false">${esc(row.expected_output || "")}</textarea>
    </label>
  </div>`;
}

function renderTestCodeSamplePanel(samples) {
  const list = samples || [];
  const first = list[0] || {};
  const loaded = list.length > 0;
  const snippet = String(first.snippet || state.testCode.samplePasteDraft || "").trim();
  const statusText = loaded
    ? `Sample loaded: ${first.label || first.source_file || first.test_name || "sample.cpp"}`
    : "Sample not loaded";
  return `<div class="alex-testcode-context-panel alex-testcode-context-panel--sample">
    <h4 class="alex-testcode-panel-title">Sample C++ Style</h4>
    <p class="detail gtest-sample-status">${esc(statusText)}</p>
    <div class="alex-testcode-sample-actions">
      <label class="btn secondary btn-inline upload-label">Load Sample .cpp<input type="file" id="testcode-cpp-upload" accept=".cpp,.h,.hpp,.cc,.txt" hidden /></label>
    </div>
    <label class="detail">Paste sample code (optional)
      <textarea id="testcode-sample-paste" class="gtest-input gtest-note" rows="6" placeholder="Paste a reference TEST_F snippet…">${esc(state.testCode.samplePasteDraft || "")}</textarea>
    </label>
    <button type="button" class="btn secondary btn-inline" id="btn-testcode-save-sample-paste">Use pasted sample</button>
    ${
      snippet
        ? `<details class="alex-testcode-sample-preview">
            <summary>Preview sample code</summary>
            <pre class="alex-testcode-sample-pre">${esc(snippet.slice(0, 4000))}${snippet.length > 4000 ? "\n…" : ""}</pre>
          </details>`
        : ""
    }
  </div>`;
}

function renderTestCodePromptPreviewPlaceholder() {
  return `<p class="detail">Open to see the exact context package sent to Copilot / API.</p>`;
}

function renderTestCodePromptPreviewBody(summary, row) {
  const s = summary || {};
  const clip = (text, max = 2000) => {
    const flat = String(text || "").trim();
    return flat.length > max ? `${flat.slice(0, max)}…` : flat || "—";
  };
  return `<dl class="alex-testcode-context-dl">
    <dt>Testcase ID</dt><dd><code>${esc(s.candidate_id || row?.candidate_id || "—")}</code></dd>
    <dt>Before</dt><dd><pre class="alex-testcode-context-pre">${esc(clip(s.expected_input || row?.expected_input))}</pre></dd>
    <dt>After</dt><dd><pre class="alex-testcode-context-pre">${esc(clip(s.expected_output || row?.expected_output))}</pre></dd>
    <dt>Coding rule</dt><dd><pre class="alex-testcode-context-pre">${esc(s.code_rule || "—")}</pre></dd>
    <dt>Sample C++</dt><dd>${s.sample_loaded ? esc(s.sample_label || "loaded") : "Not loaded"}${s.fixture_class ? ` · fixture: ${esc(s.fixture_class)}` : ""}</dd>
    <dt>Output format</dt><dd><pre class="alex-testcode-context-pre">Return one complete GTest (spec comments + TEST/TEST_F).
After code: ASSUMPTIONS section (max 5 bullets).
Use \`\`\`cpp fence. Include testcase ID in comments.</pre></dd>
  </dl>`;
}

function patchTestCodeCaseStatusUi() {
  const rows = state.testCode.rows || [];
  const cid = state.testCode.selectedCandidateId;
  const wf = computeTestCodeWorkflowStatus(cid);
  const dirty = state.testCode.dirtyMap?.[cid];

  const progressEl = $("#testcode-code-progress");
  if (progressEl) progressEl.textContent = renderTestCodeProgressSummaryText(rows);

  const caseBadge = $("#testcode-case-status-badge");
  if (caseBadge) {
    caseBadge.className = `tag ${testCodeWorkflowTagClass(wf)} testcode-wf-badge`;
    caseBadge.textContent = `[${testCodeWorkflowLabel(wf)}]`;
  }

  const unsavedHint = $("#testcode-unsaved-hint");
  if (unsavedHint) {
    if (dirty) {
      unsavedHint.hidden = false;
      unsavedHint.className = "tag warning testcode-unsaved-hint";
      unsavedHint.textContent = "Unsaved changes";
    } else {
      unsavedHint.hidden = true;
    }
  }

  const sel = document.querySelector('[data-tcase-select="testcode"]');
  if (sel) {
    [...sel.options].forEach((opt) => {
      const id = opt.value;
      const row = rows.find((r) => r.candidate_id === id);
      const status = computeTestCodeWorkflowStatus(id);
      const event = row?.event || row?.test_function || "";
      opt.textContent = `${id} ${event} [${status}]`.trim();
    });
  }
  const badgeWrap = $("#testcode-editor-status-wrap");
  if (badgeWrap) badgeWrap.outerHTML = renderTestCodeEditorStatusBadge(cid);

  const metaEl = $("#testcode-case-meta");
  if (metaEl) {
    const row = rows.find((r) => r.candidate_id === cid);
    metaEl.outerHTML = renderTestCodeCaseMeta(cid, row);
  }
}

function testCodeRowOrder(rows) {
  return [...(rows || [])].sort((a, b) => {
    const na = parseInt(String(a.no || ""), 10);
    const nb = parseInt(String(b.no || ""), 10);
    if (!Number.isNaN(na) && !Number.isNaN(nb) && na !== nb) return na - nb;
    return String(a.candidate_id || "").localeCompare(String(b.candidate_id || ""));
  });
}

function nextTestCodeMissingId(rows) {
  const ordered = testCodeRowOrder(rows);
  const hit = ordered.find((r) => {
    const wf = computeTestCodeWorkflowStatus(r.candidate_id);
    return wf === TC_WF.NO_CODE || wf === TC_WF.NEEDS_REVIEW || wf === TC_WF.DRAFT;
  });
  return hit?.candidate_id || null;
}

function renderTestCodePageBody(rows, activeRow, draft, samples) {
  const apiDisabled = !m365KnowledgeReady();
  const cid = activeRow?.candidate_id || "";
  const apiStatus = state.testCode.apiGenStatus || "idle";
  return `<div class="alex-testcode-steps">
    <section class="card alex-testcode-step">
      <header class="alex-testcode-step__header">
        <span class="alex-testcode-step__num">1</span>
        <h3 class="alex-testcode-step__title">Select Test Case</h3>
      </header>
      <div class="alex-testcode-step__body">
        ${renderTestCodeCaseBar(rows)}
        ${renderTestCodeIoContext(activeRow)}
      </div>
    </section>

    <section class="card alex-testcode-step">
      <header class="alex-testcode-step__header">
        <span class="alex-testcode-step__num">2</span>
        <h3 class="alex-testcode-step__title">Coding Context</h3>
      </header>
      <div class="alex-testcode-step__body alex-testcode-context-split">
        <div class="alex-testcode-context-panel">
          <h4 class="alex-testcode-panel-title">Coding Rules / Change Request</h4>
          <textarea id="testcode-user-request" class="gtest-input gtest-note alex-testcode-rules" rows="8" placeholder="Example: use TEST_F, fixture PowerModeTest, use SetInput() for inputs, assert PMODE_STS only, add WaitMs(50), do not access internal variables.">${esc(state.testCode.userRequest || "")}</textarea>
        </div>
        ${renderTestCodeSamplePanel(samples)}
      </div>
    </section>

    <section class="card alex-testcode-step">
      <header class="alex-testcode-step__header">
        <span class="alex-testcode-step__num">3</span>
        <h3 class="alex-testcode-step__title">Generate Code</h3>
      </header>
      <div class="alex-testcode-step__body">
        <div class="alex-testcode-gen-panels">
          <div class="alex-testcode-gen-option card">
            <h4 class="alex-testcode-panel-title">Option A — Copilot Web</h4>
            <p class="detail">Use this when M365 API is slow or failed.</p>
            <button type="button" class="btn" id="btn-testcode-copy-prompt">Copy Copilot Prompt</button>
            <label class="detail">Paste Copilot Result Here
              <textarea id="testcode-copilot-import" class="gtest-input gtest-note" rows="6" placeholder="Paste Copilot cpp block (+ ASSUMPTIONS optional)…"></textarea>
            </label>
            <button type="button" class="btn secondary" id="btn-testcode-import-copilot">Import to Editor</button>
          </div>
          <div class="alex-testcode-gen-option card">
            <h4 class="alex-testcode-panel-title">Option B — Generate API</h4>
            <p class="detail">Same context package — result goes to the editor when done.</p>
            <button type="button" class="btn secondary" id="btn-testcode-copilot" ${apiDisabled ? "disabled" : ""} title="${esc(apiDisabled ? m365KnowledgeBlockReason() : "")}">Generate by API</button>
            <div id="testcode-api-status" class="alex-testcode-api-status">${apiStatus === "idle" ? '<span class="detail">Status: Idle</span>' : ""}</div>
            ${apiDisabled ? `<p class="detail testcode-copilot-hint">${esc(m365KnowledgeBlockReason())}</p>` : ""}
          </div>
        </div>
        <details class="alex-testcode-prompt-preview" id="testcode-prompt-preview">
          <summary>Prompt Preview — context sent to Copilot / API</summary>
          <div class="alex-testcode-prompt-preview__body" id="testcode-prompt-preview-body">${renderTestCodePromptPreviewPlaceholder()}</div>
          <button type="button" class="btn secondary btn-inline" id="btn-testcode-refresh-prompt">Refresh preview</button>
        </details>
      </div>
    </section>

    <section class="card alex-testcode-step alex-testcode-step--review">
      <header class="alex-testcode-step__header">
        <span class="alex-testcode-step__num">4</span>
        <h3 class="alex-testcode-step__title">Review &amp; Save Code</h3>
        <span class="detail">${esc(draft?.test_name || cid || "")}</span>
        ${renderTestCodeEditorStatusBadge(cid)}
      </header>
      <div class="alex-testcode-step__body">
        <div id="testcode-validation" class="alex-testcode-validation" hidden></div>
        <textarea id="testcode-code-editor" class="gtest-editor gtest-editor--main gtest-editor--tall" spellcheck="false" placeholder="// Generated GTest code appears here…">${esc(draft?.full_snippet || draft?.code_body || "")}</textarea>
        <div class="alex-testcode-editor__foot">
          <p class="detail testcode-flow-hint" id="testcode-status">Review generated code, validate, then Save Code.</p>
          <div class="alex-testcode-editor__actions">
            <button type="button" class="btn secondary" id="btn-testcode-validate">Validate Code</button>
            <button type="button" class="btn secondary" id="btn-testcode-apply-imported">Apply Imported Code</button>
            <button type="button" class="btn secondary" id="btn-testcode-export-cpp">Export .cpp</button>
            <button type="button" class="btn secondary" id="btn-testcode-merge-saved">Merge Saved Code</button>
            <button type="button" class="btn" id="btn-testcode-save-draft">Save Code</button>
          </div>
        </div>
        <div id="testcode-merge-panel" class="alex-testcode-merge-panel" hidden></div>
      </div>
    </section>

    <details class="alex-testcode-advanced card">
      <summary>Advanced</summary>
      <div class="alex-testcode-advanced__body">
        <label class="detail testcode-followup-label">
          <input type="checkbox" id="testcode-copilot-followup" ${state.testCode.copilotWebFollowUp ? "checked" : ""} />
          Shorter Copilot prompt for next testcase (same web chat)
        </label>
        <p class="detail">Workflow badges: [NO_CODE] [DRAFT] [SAVED] [MODIFIED_UNSAVED] [NEEDS_REVIEW] [ERROR]</p>
      </div>
    </details>
  </div>`;
}

function userRequestImpliesAllTestcases(req) {
  const t = String(req || "").toLowerCase();
  return /\b(toàn bộ|tất cả|all test|every testcase|các testcase|mọi testcase|all tc|every tc)\b/.test(t);
}

function renderTestCodeSyncSummaryText(sync) {
  if (!sync?.summary) return "Chưa sync — bấm Refresh sync";
  const s = sync.summary;
  const parts = [];
  if (s.ok) parts.push(`${s.ok} ok`);
  if (s.no_code) parts.push(`${s.no_code} chưa có code`);
  if (s.stale_comment) parts.push(`${s.stale_comment} stale comment`);
  if (s.stale_body) parts.push(`${s.stale_body} stale body`);
  if (s.orphan_code) parts.push(`${s.orphan_code} orphan`);
  return parts.join(" · ") || "—";
}

function testCodeSyncStatusFor(candidateId) {
  const rows = state.testCode.syncStatus?.rows || [];
  return rows.find((r) => r.candidate_id === candidateId)?.status || "";
}

async function refreshTestCodeSyncStatus() {
  if (!state.jobId) return null;
  try {
    const lang = state.exportLanguage || "EN";
    const data = await api(`/api/review/gtest-sync-status?job_id=${encodeURIComponent(state.jobId)}&language=${encodeURIComponent(lang)}`);
    state.testCode.syncStatus = data;
    patchTestCodeCaseStatusUi();
    return data;
  } catch {
    return null;
  }
}

async function runTestCodeBulk(action, candidateIds = null) {
  const lang = state.exportLanguage || "EN";
  const body = {
    action,
    candidate_ids: candidateIds || (state.testCode.selectedCandidateId ? [state.testCode.selectedCandidateId] : []),
    language: lang,
    stale_only: action === "regen_comment_stale",
    persist: true,
  };
  return api(`/api/review/gtest-bulk?job_id=${encodeURIComponent(state.jobId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function renderTestCodeContextPreviewBody(summary, row) {
  if (!summary && !row) {
    return `<p class="detail">Chọn testcase và nhập Code Rule để xem preview.</p>`;
  }
  const s = summary || {};
  const clip = (text, max = 280) => {
    const flat = String(text || "")
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .join("\n");
    return flat.length > max ? `${flat.slice(0, max)}…` : flat || "—";
  };
  return `<dl class="alex-testcode-context-dl">
    <dt>Testcase</dt><dd><code>${esc(s.candidate_id || row?.candidate_id || "—")}</code>${s.test_function ? ` · ${esc(s.test_function)}` : ""}</dd>
    <dt>BEFORE (input)</dt><dd><pre class="alex-testcode-context-pre">${esc(clip(s.expected_input || row?.expected_input))}</pre></dd>
    <dt>AFTER (output)</dt><dd><pre class="alex-testcode-context-pre">${esc(clip(s.expected_output || row?.expected_output))}</pre></dd>
    <dt>Sample .cpp</dt><dd>${s.sample_loaded ? esc(s.sample_label || "loaded") : "— chưa load"}${s.fixture_class ? ` · fixture: ${esc(s.fixture_class)}` : ""}</dd>
    <dt>Code Rule</dt><dd><pre class="alex-testcode-context-pre">${esc(s.code_rule || "—")}</pre></dd>
  </dl>`;
}

async function copyTestCodeCopilotPrompt(rows) {
  const tc = state.testCode;
  if (!tc.selectedCandidateId) throw new Error("Chọn testcase trước.");
  const codeRule = $("#testcode-user-request")?.value || tc.userRequest || "";
  const followUp = $("#testcode-copilot-followup")?.checked ?? tc.copilotWebFollowUp;
  tc.copilotWebFollowUp = followUp;
  const editorCode = $("#testcode-code-editor")?.value || "";
  const q = new URLSearchParams({
    candidate_id: tc.selectedCandidateId,
    language: state.exportLanguage || "EN",
    code_rule: codeRule,
    existing_code: editorCode.slice(0, 12000),
    prompt_mode: followUp ? "followup" : "full",
    slim: "1",
  });
  const data = await api(`/api/review/copilot/code/prompt?job_id=${encodeURIComponent(state.jobId)}&${q}`);
  const prompt = data.prompt || "";
  if (!prompt) throw new Error("Không lấy được prompt.");
  tc.copilotPromptText = prompt;
  await navigator.clipboard.writeText(prompt);
  return prompt;
}

async function openTestCodeCopilotWeb(rows) {
  await copyTestCodeCopilotPrompt(rows);
  window.open(COPILOT_WEB_URL, "_blank", "noopener,noreferrer");
  const statusEl = $("#testcode-status");
  if (statusEl) {
    const followUp = state.testCode.copilotWebFollowUp;
    statusEl.textContent = followUp
      ? "Đã copy prompt ngắn (cùng chat) — dán vào Copilot → dán cpp về bước 3."
      : "Đã copy prompt đầy đủ — dán vào Copilot. TC tiếp: tick「Cùng chat」để prompt ngắn hơn.";
  }
}

function parseCopilotCppPaste(text) {
  const raw = String(text || "").trim();
  if (!raw) return { code: "", assumptions: [] };
  let body = raw;
  let assumptions = [];
  const assumeMatch = raw.match(/(?:^|\n)\s*ASSUMPTIONS?\s*:\s*\n([\s\S]*)$/i);
  if (assumeMatch) {
    body = raw.slice(0, assumeMatch.index).trim();
    assumptions = assumeMatch[1]
      .split("\n")
      .map((l) => l.replace(/^[\s\-*•]+/, "").trim())
      .filter(Boolean);
  }
  const fence = body.match(/```(?:cpp|c\+\+)?\s*\n?([\s\S]*?)```/i);
  let code = fence ? fence[1].trim() : body.replace(/^```(?:cpp|c\+\+)?\s*/i, "").replace(/\s*```$/, "").trim();
  return { code, assumptions };
}

function validateGtestBeforeSave(code, candidateId, sampleSnippet) {
  const body = String(code || "").trim();
  const warnings = [];
  const issueLabels = {
    empty: "Empty code",
    markdown_fence: "Contains markdown fence (```)",
    todo: "Contains TODO",
    missing_TEST: "Missing TEST or TEST_F",
    missing_EXPECT: "Missing EXPECT or ASSERT",
    missing_candidate_id: "Testcase ID not found in code comments",
  };

  if (!body) warnings.push(issueLabels.empty);
  if (body.includes("```")) warnings.push(issueLabels.markdown_fence);
  if (/\bTODO\b/i.test(body)) warnings.push(issueLabels.todo);
  if (!/\bTEST(?:_F)?\s*\(/.test(body)) warnings.push(issueLabels.missing_TEST);
  if (
    !/\bEXPECT_(EQ|NE|TRUE|FALSE|THAT)\b/.test(body) &&
    !/\bASSERT_(EQ|NE|TRUE|FALSE|THAT)\b/.test(body)
  ) {
    warnings.push(issueLabels.missing_EXPECT);
  }
  const cid = String(candidateId || "").trim();
  if (cid && !body.includes(cid)) warnings.push(issueLabels.missing_candidate_id);

  const callRe = /\b([A-Za-z_][A-Za-z0-9_]*)\s*\(/g;
  const builtins = new Set([
    "TEST", "TEST_F", "EXPECT_EQ", "EXPECT_NE", "EXPECT_TRUE", "EXPECT_FALSE", "EXPECT_THAT",
    "ASSERT_EQ", "ASSERT_NE", "ASSERT_TRUE", "ASSERT_FALSE", "if", "for", "while", "return", "sizeof",
  ]);
  const sampleCalls = new Set();
  let m;
  while ((m = callRe.exec(String(sampleSnippet || "")))) {
    if (!builtins.has(m[1])) sampleCalls.add(m[1]);
  }
  if (sampleCalls.size) {
    const codeCalls = new Set();
    callRe.lastIndex = 0;
    while ((m = callRe.exec(body))) {
      if (!builtins.has(m[1]) && !m[1].startsWith("EXPECT") && !m[1].startsWith("ASSERT")) codeCalls.add(m[1]);
    }
    const unknown = [...codeCalls].filter((c) => !sampleCalls.has(c));
    if (unknown.length) warnings.push(`API not in sample: ${unknown.slice(0, 6).join(", ")}`);
  }

  return { ok: true, flags: [], warnings };
}

function codeLikelyMatchesTestcase(code, candidateId) {
  const cid = String(candidateId || "").trim();
  if (!cid) return true;
  return String(code || "").includes(cid);
}

function confirmTestCodeSave(val, code, candidateId) {
  const lines = [...(val?.warnings || [])];
  if (!codeLikelyMatchesTestcase(code, candidateId)) {
    lines.push("Generated code may not match selected testcase_id.");
  }
  if (!lines.length) return true;
  return window.confirm(`Validation warnings:\n\n${lines.map((l) => `• ${l}`).join("\n")}\n\nSave anyway?`);
}

async function refreshTestCodePromptPreview(rows) {
  const host = document.getElementById("testcode-prompt-preview-body");
  if (!host || !state.jobId) return;
  const tc = state.testCode;
  const row = (rows || tc.rows || []).find((r) => r.candidate_id === tc.selectedCandidateId);
  const codeRule = $("#testcode-user-request")?.value || tc.userRequest || "";
  if (!tc.selectedCandidateId) {
    host.innerHTML = renderTestCodePromptPreviewPlaceholder();
    return;
  }
  host.innerHTML = `<p class="detail">Loading prompt preview…</p>`;
  try {
    const editorCode = $("#testcode-code-editor")?.value || "";
    const followUp = $("#testcode-copilot-followup")?.checked ?? tc.copilotWebFollowUp;
    const q = new URLSearchParams({
      candidate_id: tc.selectedCandidateId,
      language: state.exportLanguage || "EN",
      code_rule: codeRule,
      existing_code: editorCode.slice(0, 12000),
      prompt_mode: followUp ? "followup" : "full",
      slim: "1",
    });
    const data = await api(`/api/review/copilot/code/prompt?job_id=${encodeURIComponent(state.jobId)}&${q}`);
    tc.copilotPromptText = data.prompt || "";
    tc.contextSummary = data.context_summary || {};
    host.innerHTML = renderTestCodePromptPreviewBody(data.context_summary, row);
  } catch (e) {
    host.innerHTML = renderTestCodePromptPreviewBody(
      {
        candidate_id: row?.candidate_id,
        expected_input: row?.expected_input,
        expected_output: row?.expected_output,
        code_rule: codeRule,
        sample_loaded: !!(tc.codeStyleSamples || []).length,
        sample_label: tc.codeStyleSamples?.[0]?.label || tc.codeStyleSamples?.[0]?.source_file,
      },
      row
    );
    host.insertAdjacentHTML("beforeend", `<p class="detail warn">Preview partial: ${esc(e.message)}</p>`);
  }
}

/** @deprecated use refreshTestCodePromptPreview */
async function refreshTestCodeContextPreview(rows) {
  return refreshTestCodePromptPreview(rows);
}

function editorHasGtestCode() {
  const code = $("#testcode-code-editor")?.value || "";
  return code.includes("TEST_F(") && code.trim().length > 80;
}

function startTestCodeCopilotProgress({ steps = [] } = {}) {
  const host = document.getElementById("testcode-copilot-progress");
  if (!host) return { stop: () => {}, tick: () => {} };
  const started = Date.now();
  const defaultSteps = steps.length
    ? steps
    : [
        "1/4 Chuẩn bị context (I/O + code mẫu)…",
        "2/4 Gọi Microsoft 365 Copilot API…",
        "3/4 Copilot đang viết GTest (thường 30s–2 phút)…",
        "4/4 Nhận và parse kết quả…",
      ];
  let stepIdx = 0;
  host.hidden = false;
  host.innerHTML = `<div class="copilot-progress card">
    <div class="copilot-progress__head">
      <span class="tag warning" id="testcode-copilot-badge">Copilot running</span>
      <span id="testcode-copilot-elapsed" class="detail">0s</span>
    </div>
    <div class="progress-bar progress-bar--indeterminate" id="testcode-copilot-bar"><div></div></div>
    <p id="testcode-copilot-step" class="detail">${esc(defaultSteps[0])}</p>
    <p class="detail copilot-progress__hint">M365 Copilot không stream realtime — bar chạy theo bước ước lượng, không treo.</p>
  </div>`;
  const btn = $("#btn-testcode-copilot");
  if (btn) {
    btn.disabled = true;
    btn.dataset.busy = "1";
  }
  const editor = $("#testcode-code-editor");
  editor?.classList.add("gtest-editor--busy");
  const timer = setInterval(() => {
    const elapsed = Math.floor((Date.now() - started) / 1000);
    const el = document.getElementById("testcode-copilot-elapsed");
    if (el) el.textContent = `${elapsed}s`;
    stepIdx = Math.min(defaultSteps.length - 1, Math.floor(elapsed / 12));
    const stepEl = document.getElementById("testcode-copilot-step");
    if (stepEl) stepEl.textContent = defaultSteps[stepIdx];
  }, 400);
  return {
    tick(label) {
      const stepEl = document.getElementById("testcode-copilot-step");
      if (stepEl && label) stepEl.textContent = label;
    },
    stop(ok, msg) {
      clearInterval(timer);
      if (btn) {
        btn.disabled = !m365KnowledgeReady();
        delete btn.dataset.busy;
      }
      editor?.classList.remove("gtest-editor--busy");
      const badge = document.getElementById("testcode-copilot-badge");
      const bar = document.getElementById("testcode-copilot-bar");
      if (badge) {
        badge.textContent = ok ? "Done" : "Failed";
        badge.className = `tag ${ok ? "high" : "error"}`;
      }
      if (bar) bar.classList.remove("progress-bar--indeterminate");
      const stepEl = document.getElementById("testcode-copilot-step");
      if (stepEl && msg) stepEl.textContent = msg;
      if (ok) {
        setTimeout(() => {
          host.hidden = true;
          host.innerHTML = "";
        }, 2500);
      }
    },
  };
}

function showTestCodeApplyAllBanner(rows, activeRow, onApplyAll, { allJob = false, userRequest = "" } = {}) {
  const banner = document.getElementById("testcode-apply-all-banner");
  if (!banner || !activeRow) return;
  const batchAll = allJob || userRequestImpliesAllTestcases(userRequest);
  const siblings = batchAll
    ? rows.filter((r) => r.candidate_id !== activeRow.candidate_id)
    : rows.filter((r) => r.logic_id === activeRow.logic_id && r.candidate_id !== activeRow.candidate_id);
  if (!siblings.length) {
    banner.hidden = true;
    banner.innerHTML = "";
    return;
  }
  const scope = batchAll ? "toàn bộ job" : `nhóm ${activeRow.logic_id || "logic"}`;
  banner.hidden = false;
  banner.innerHTML = `<div class="copilot-apply-all-banner field-copilot-changed">
    <p><b>Yêu cầu áp dụng nhiều testcase</b> — Copilot đã xử lý <code>${esc(activeRow.candidate_id)}</code>.
    Apply cùng pattern cho <b>${siblings.length}</b> TC còn lại (${esc(scope)})?</p>
    <div class="review-actions">
      <button type="button" class="btn" id="btn-testcode-apply-all">Apply tất cả (${siblings.length})</button>
      <button type="button" class="btn secondary" id="btn-testcode-apply-all-skip">Chỉ TC này</button>
    </div>
  </div>`;
  bindClick("#btn-testcode-apply-all", onApplyAll);
  bindClick("#btn-testcode-apply-all-skip", () => {
    banner.hidden = true;
    banner.innerHTML = "";
  });
}

function renderTestCodeIoStrip(row) {
  if (!row) return "";
  const clip = (text, max = 160) => {
    const flat = String(text || "")
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .join(" · ");
    return flat.length > max ? `${flat.slice(0, max)}…` : flat;
  };
  return `<div class="gtest-io-strip" id="testcode-io-strip">
    <div class="gtest-io-strip__col"><span class="gtest-io-strip__label">Before</span><span>${esc(clip(row.expected_input) || "—")}</span></div>
    <div class="gtest-io-strip__col"><span class="gtest-io-strip__label">After</span><span>${esc(clip(row.expected_output) || "—")}</span></div>
  </div>`;
}

function renderTestCodeSamplesPanel(samples, referenceTestName) {
  const rows = samples || [];
  const refOpts = rows
    .map((s) => {
      const val = s.test_name || s.label || "";
      return val ? `<option value="${esc(val)}" ${val === referenceTestName ? "selected" : ""}>${esc(s.label || s.test_name)}</option>` : "";
    })
    .join("");
  const list =
    rows.length === 0
      ? `<p class="detail">Chưa có mẫu — upload .cpp hoặc upload file code cùng spec ở Review.</p>`
      : `<ul class="alex-testcode-sample-list">${rows
          .map(
            (s) =>
              `<li><b>${esc(s.label || s.test_name || "sample")}</b> <span class="detail">${esc(s.source_file || "")}${s.fixture_class ? ` · ${esc(s.fixture_class)}` : ""}</span></li>`
          )
          .join("")}</ul>`;
  return `${list}
    <label class="gtest-inline-label">Reference test
      <select id="testcode-ref-select" class="gtest-input gtest-select">
        <option value="">— auto first —</option>
        ${refOpts}
      </select>
    </label>
    <label class="detail">Engineer note (helpers, timing…)
      <textarea id="testcode-engineer-note" class="gtest-input gtest-note" rows="3" placeholder="vd. Dùng RunForMs(100) sau When elapsed…">${esc(state.testCode.engineerNote || "")}</textarea>
    </label>
    <label class="detail">Copilot instructions (optional, markdown-style)
      <textarea id="testcode-copilot-prompt" class="gtest-input gtest-note" rows="3" placeholder="vd. Dùng TEST_F, không mock CAN trực tiếp…">${esc(state.testCode.copilotPromptOverride || "")}</textarea>
    </label>
    <div class="gtest-map-toolbar">
      <label class="btn secondary upload-label">Attach .cpp<input type="file" id="testcode-cpp-upload" accept=".cpp,.h,.hpp,.cc,.txt" hidden /></label>
    </div>`;
}

function renderTestCodeBatchPanel(results) {
  if (!results?.length) return "";
  const rows = results
    .map((r) => {
      const q = r.validation?.quality || (r.ok ? "good" : r.skipped ? "skip" : "failed");
      const tag = r.skipped ? "skip" : r.ok ? "ok" : "warn";
      return `<tr data-batch-cid="${esc(r.candidate_id)}">
        <td><input type="checkbox" class="batch-apply-cb" data-batch-cid="${esc(r.candidate_id)}" ${r.ok ? "checked" : ""} ${r.ok ? "" : "disabled"} /></td>
        <td>${esc(r.candidate_id)}</td>
        <td><span class="tag ${tag}">${esc(q)}</span></td>
        <td class="detail">${esc(r.reason || r.error || (r.validation?.flags || []).join(", ") || "")}</td>
      </tr>`;
    })
    .join("");
  return `<details class="alex-testcode-panel alex-testcode-batch" open>
    <summary>Batch results (${results.length})</summary>
    <div class="alex-testcode-panel__body">
      <table class="data-grid alex-table gtest-batch-table">
        <thead><tr><th></th><th>TestCase</th><th>Status</th><th>Note</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <button type="button" class="btn secondary btn-inline" id="btn-testcode-batch-apply">Apply selected drafts</button>
    </div>
  </details>`;
}

function renderTestCodeSpecPreview(draft) {
  const preview = draft?.spec_preview || {};
  if (preview.given_when || preview.then) {
    return `<pre class="gtest-spec-preview">${esc([preview.given_when, preview.then].filter(Boolean).join("\n\n"))}</pre>`;
  }
  if (preview.logic_expression) {
    return `<pre class="gtest-spec-preview">${esc(preview.logic_expression)}</pre>`;
  }
  return `<p class="detail">Select a test case or logic group to preview spec text.</p>`;
}

function updateTestCodeBatchPanel(results) {
  let host = document.querySelector(".alex-testcode-batch");
  const html = renderTestCodeBatchPanel(results);
  if (!html) {
    host?.remove();
    return;
  }
  if (host) {
    host.outerHTML = html;
  } else {
    const hint = $("#testcode-status");
    hint?.insertAdjacentHTML("afterend", html);
  }
  $("#btn-testcode-batch-apply")?.addEventListener("click", onTestCodeBatchApply);
}

function bindTestCodeSampleControls(onUpload) {
  $("#testcode-ref-select")?.addEventListener("change", (ev) => {
    state.testCode.referenceTestName = ev.target.value || "";
  });
  $("#testcode-engineer-note")?.addEventListener("input", (ev) => {
    state.testCode.engineerNote = ev.target.value || "";
  });
  $("#testcode-copilot-prompt")?.addEventListener("input", (ev) => {
    state.testCode.copilotPromptOverride = ev.target.value || "";
  });
  const uploadEl = $("#testcode-cpp-upload");
  if (uploadEl && onUpload) {
    uploadEl.onchange = onUpload;
  }
}

async function onTestCodeBatchApply() {
  const statusEl = $("#testcode-status");
  const tc = state.testCode;
  const selected = [...document.querySelectorAll(".batch-apply-cb:checked")].map((el) => el.dataset.batchCid).filter(Boolean);
  if (!selected.length) {
    if (statusEl) statusEl.textContent = "No batch drafts selected.";
    return;
  }
  const ws = tc.workspace || (await fetchGtestWorkspace(true));
  const drafts = ws.drafts || {};
  if (selected.includes(tc.selectedCandidateId)) {
    const d = drafts[tc.selectedCandidateId];
    if (d?.full_snippet) {
      const row = (tc.rows || []).find((r) => r.candidate_id === tc.selectedCandidateId);
      applyTestCodeDraftToUi(d, row);
      if (statusEl) statusEl.textContent = "Applied batch draft to editor — review and Save.";
      return;
    }
  }
  if (statusEl) statusEl.textContent = "Select a test case with a generated draft to preview in editor.";
}

function bindTestCodeHandlers(rows) {
  const tc = state.testCode;
  const statusEl = $("#testcode-status");

  const userRequest = () => {
    const v = $("#testcode-user-request")?.value || "";
    tc.userRequest = v;
    return v;
  };

  const handleCppUpload = async (ev) => {
    const file = ev.target.files?.[0];
    if (!file) return;
    if (statusEl) statusEl.textContent = `Uploading ${file.name}…`;
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/api/review/code-style-samples/upload?job_id=${encodeURIComponent(state.jobId)}`, {
        method: "POST",
        body: fd,
        credentials: "same-origin",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || "Upload failed");
      tc.codeStyleSamples = data.samples || [];
      invalidateApiCache(`gtest-ws:${state.jobId}:${state.exportLanguage || "EN"}`);
      const ws = await fetchGtestWorkspace(true);
      tc.workspace = ws;
      tc.codeStyleSamples = ws.code_style_samples || tc.codeStyleSamples;
      const statusSample = document.querySelector(".gtest-sample-status");
      if (statusSample && tc.codeStyleSamples[0]) {
        const s = tc.codeStyleSamples[0];
        statusSample.textContent = `Sample loaded: ${s.label || s.source_file || "sample.cpp"}`;
      }
      if (statusEl) statusEl.textContent = `Sample loaded (${tc.codeStyleSamples.length}).`;
      refreshTestCodePromptPreview(rows);
    } catch (e) {
      if (statusEl) statusEl.textContent = e.message;
    }
    ev.target.value = "";
  };

  bindOnChange("#testcode-cpp-upload", handleCppUpload);
  bindOnChange("#testcode-user-request", () => {
    tc.userRequest = $("#testcode-user-request")?.value || "";
    refreshTestCodePromptPreview(rows);
  });
  bindOnChange("#testcode-sample-paste", (ev) => {
    tc.samplePasteDraft = ev.target.value || "";
  });

  refreshTestCodeSyncStatus().then(() => refreshTestCodePromptPreview(rows));

  bindOnChange("#testcode-copilot-followup", (ev) => {
    state.testCode.copilotWebFollowUp = !!ev.target.checked;
  });

  bindClick("#btn-testcode-prev-case", () => navigateTestCodeCase(rows, -1));
  bindClick("#btn-testcode-next-case", () => navigateTestCodeCase(rows, 1));

  document.querySelectorAll("[data-case-filter]").forEach((btn) => {
    btn.onclick = () => {
      state.testCode.caseFilter = btn.dataset.caseFilter || "all";
      document.querySelectorAll("[data-case-filter]").forEach((b) => b.classList.toggle("active", b === btn));
      patchTestCodeCaseStatusUi();
    };
  });

  bindClick("#btn-testcode-save-sample-paste", async () => {
    const text = ($("#testcode-sample-paste")?.value || "").trim();
    if (!text) {
      if (statusEl) statusEl.textContent = "Paste sample code first.";
      return;
    }
    try {
      await api(`/api/review/code-style-samples?job_id=${encodeURIComponent(state.jobId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          replace: true,
          samples: [{ label: "pasted_sample", source_file: "paste.cpp", snippet: text }],
        }),
      });
      invalidateApiCache(`gtest-ws:${state.jobId}:${state.exportLanguage || "EN"}`);
      tc.workspace = await fetchGtestWorkspace(true);
      tc.codeStyleSamples = tc.workspace.code_style_samples || [];
      if (statusEl) statusEl.textContent = "Pasted sample saved.";
      refreshTestCodePromptPreview(rows);
    } catch (e) {
      if (statusEl) statusEl.textContent = e.message;
    }
  });

  bindClick("#btn-testcode-copy-prompt", async () => {
    try {
      await copyTestCodeCopilotPrompt(rows);
      if (statusEl) statusEl.textContent = "Copilot prompt copied — paste into M365 Copilot web, then paste result in Step 3.";
    } catch (e) {
      if (statusEl) statusEl.textContent = e.message || "Copy failed.";
    }
  });

  bindClick("#btn-testcode-refresh-prompt", () => refreshTestCodePromptPreview(rows));

  bindClick("#btn-testcode-import-copilot", () => applyImportedCopilotToEditor(rows));

  bindClick("#btn-testcode-apply-imported", () => applyImportedCopilotToEditor(rows));

  bindClick("#btn-testcode-validate", () => {
    const code = $("#testcode-code-editor")?.value || "";
    const sampleSnippet = tc.codeStyleSamples?.[0]?.snippet || tc.workspace?.code_style_samples?.[0]?.snippet || "";
    showTestCodeValidationResult(validateGtestBeforeSave(code, tc.selectedCandidateId, sampleSnippet));
    if (statusEl) statusEl.textContent = "Validation updated above editor.";
  });

  bindClick("#btn-testcode-export-cpp", () => {
    const cid = tc.selectedCandidateId;
    if (!cid) {
      if (statusEl) statusEl.textContent = "Select a testcase first.";
      return;
    }
    window.open(
      `/api/export/gtest-cpp?job_id=${encodeURIComponent(state.jobId)}&candidate_id=${encodeURIComponent(cid)}`,
      "_blank"
    );
  });

  bindClick("#btn-testcode-copilot", async () => {
    if (!tc.selectedCandidateId) {
      if (statusEl) statusEl.textContent = "Chọn testcase trước.";
      return;
    }
    if (!m365KnowledgeReady()) {
      if (statusEl) statusEl.textContent = "Authorize Copilot API trước.";
      return;
    }
    const req = userRequest();
    const editorCode = $("#testcode-code-editor")?.value || "";
    try {
      setTestCodeApiStatus("running");
      if (editorHasGtestCode()) {
        await startM365Task({
          kind: "code_refine",
          label: `Chỉnh ${tc.selectedCandidateId}`,
          candidateId: tc.selectedCandidateId,
          targetPage: "test-code",
          payload: {
            candidate_id: tc.selectedCandidateId,
            existing_code: editorCode,
            instruction: req,
            language: state.exportLanguage || "EN",
            reuse_conversation: true,
          },
        });
        if (statusEl) statusEl.textContent = "Generate by API running — result will appear in the editor.";
        return;
      }

      const importedMode = jobBootstrapSource(state._summaryCache?.summary).startsWith("imported");
      await startM365Task({
        kind: "code_generate",
        label: `Generate ${tc.selectedCandidateId}`,
        candidateId: tc.selectedCandidateId,
        targetPage: "test-code",
        payload: {
          candidate_id: tc.selectedCandidateId,
          use_baseline: true,
          slim: true,
          language: state.exportLanguage || "EN",
          engineer_note: req,
          copilot_prompt_override: req,
          reference_test_name: tc.codeStyleSamples?.[0]?.test_name || "",
          from_testcase_only: importedMode ? true : null,
          reuse_conversation: true,
        },
      });
      if (statusEl) statusEl.textContent = "Generate by API running — see status in Step 3.";
    } catch (e) {
      setTestCodeApiStatus("failed", e.message);
      if (statusEl) statusEl.textContent = e.message;
    }
  });

  bindClick("#btn-testcode-save-draft", async () => {
    const key = tc.selectedCandidateId;
    if (!key) return;
    const codeEl = $("#testcode-code-editor");
    const full = codeEl?.value || "";
    const sampleSnippet = tc.codeStyleSamples?.[0]?.snippet || tc.workspace?.code_style_samples?.[0]?.snippet || "";
    const val = validateGtestBeforeSave(full, key, sampleSnippet);
    const valEl = document.getElementById("testcode-validation");
    if (valEl) {
      valEl.hidden = false;
      valEl.innerHTML = renderTestCodeValidation(val);
    }
    if (!confirmTestCodeSave(val, full, key)) {
      if (statusEl) statusEl.textContent = "Save cancelled.";
      return;
    }
    const bodyStart = full.search(/\bTEST(?:_F)?\s*\(/);
    const specBlock = bodyStart > 0 ? full.slice(0, bodyStart).trim() : "";
    const codeBody = bodyStart >= 0 ? full.slice(bodyStart).trim() : full;
    const genSrc = inferGenerationSourceForSave(key);
    if (statusEl) statusEl.textContent = "Saving…";
    try {
      const saveRes = await api(`/api/review/gtest-draft?job_id=${encodeURIComponent(state.jobId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          draft_key: key,
          source_kind: "candidate",
          test_name: tc.draft?.test_name || key,
          spec_comment_block: specBlock,
          code_body: codeBody,
          full_snippet: full,
          engineer_edited: true,
          code_status: "SAVED",
          generation_source: genSrc,
        }),
      });
      if (codeEl) codeEl.classList.remove("field-copilot-changed");
      clearTestCodeDirty(key, full);
      if (!tc.generationSource) tc.generationSource = {};
      tc.generationSource[key] = genSrc;
      if (!tc.workspace) tc.workspace = {};
      if (!tc.workspace.drafts) tc.workspace.drafts = {};
      tc.workspace.drafts[key] = {
        ...(tc.workspace.drafts[key] || {}),
        full_snippet: full,
        code_body: codeBody,
        spec_comment_block: specBlock,
        code_status: saveRes.code_status || "SAVED",
        generation_source: saveRes.generation_source || genSrc,
        last_saved_at: saveRes.last_saved_at || null,
      };
      invalidateApiCache(`gtest-ws:${state.jobId}:${state.exportLanguage || "EN"}`);
      tc.workspace = await fetchGtestWorkspace(true);
      hydrateTestCodeWorkflowFromWorkspace(tc.workspace, { fullReset: false });
      await refreshTestCodeSyncStatus();
      tc.draft = resolveDraftForCandidate(key);
      applyTestCodeDraftToUi(tc.draft, rows.find((r) => r.candidate_id === key));
      if (statusEl) statusEl.textContent = `Saved [SAVED] · ${genSrc}${saveRes.last_saved_at ? ` · ${formatTestCodeTimestamp(saveRes.last_saved_at)}` : ""}`;
      refreshTestCodePromptPreview(rows);
    } catch (e) {
      if (statusEl) statusEl.textContent = e.message;
    }
  });

  bindOnInput("#testcode-code-editor", () => markTestCodeDirty());

  bindClick("#btn-testcode-merge-saved", () => openTestCodeMergePreview(rows));
}

function renderTestCodeValidation(val) {
  if (!val) return "";
  const warnings = val.warnings || [];
  if (!warnings.length) {
    return `<span class="tag ok">Validation OK — ready to Save Code</span>`;
  }
  return `<div class="alex-testcode-validation-warn">
    <span class="tag warning">Validation warnings — review before save</span>
    <ul class="alex-testcode-validation-list">${warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>
  </div>`;
}

function renderTestCodeMergePanel(preview) {
  if (!preview) return "";
  const included = preview.included || [];
  const skipped = preview.skipped || [];
  const warnings = preview.warnings || [];
  const total = preview.total_count ?? included.length + skipped.length;
  const warnCount = preview.warning_count ?? warnings.length;
  const skipList = skipped.length
    ? `<ul class="alex-testcode-merge-list">${skipped
        .map((s) => `<li><code>${esc(s.candidate_id)}</code> — ${esc(s.reason)}</li>`)
        .join("")}</ul>`
    : `<p class="detail">—</p>`;
  const includeList = included.length
    ? `<ul class="alex-testcode-merge-list">${included.map((id) => `<li><code>${esc(id)}</code></li>`).join("")}</ul>`
    : `<p class="detail">—</p>`;
  const warnList = warnings.length
    ? `<ul class="alex-testcode-merge-list alex-testcode-merge-list--warn">${warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>`
    : `<p class="detail">—</p>`;
  return `<div class="alex-testcode-merge-summary">
      <p class="detail"><b>Total testcase:</b> ${total} · <b>Included:</b> ${included.length} · <b>Skipped:</b> ${skipped.length} · <b>Warnings:</b> ${warnCount}</p>
      ${skipped.length ? `<p class="tag warning">Some testcases are not saved or have no code. Merge will include only SAVED code.</p>` : ""}
    </div>
    <section class="alex-testcode-merge-section">
      <h4 class="alex-testcode-panel-title">Included testcases (${included.length})</h4>
      ${includeList}
    </section>
    <section class="alex-testcode-merge-section">
      <h4 class="alex-testcode-panel-title">Skipped testcases (${skipped.length})</h4>
      ${skipList}
    </section>
    <section class="alex-testcode-merge-section">
      <h4 class="alex-testcode-panel-title">Warnings (${warnings.length})</h4>
      ${warnList}
    </section>
    <section class="alex-testcode-merge-section">
      <h4 class="alex-testcode-panel-title">Final merged code</h4>
      <textarea class="gtest-input gtest-editor alex-testcode-merge-preview" id="testcode-merge-preview-code" rows="16" readonly spellcheck="false">${esc(preview.content || "")}</textarea>
    </section>
    <div class="alex-testcode-editor__actions">
      <button type="button" class="btn secondary" id="btn-testcode-merge-copy">Copy Merged Code</button>
      <button type="button" class="btn" id="btn-testcode-merge-export">Export Merged .cpp</button>
    </div>`;
}

function bindTestCodeMergePanelActions(data, statusEl) {
  bindClick("#btn-testcode-merge-copy", async () => {
    const text = data.content || "";
    if (!text) return;
    await navigator.clipboard.writeText(text);
    if (statusEl) statusEl.textContent = "Merged code copied to clipboard.";
  });
  bindClick("#btn-testcode-merge-export", () => {
    const text = data.content || "";
    if (!text) return;
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = mergedExportFilename(data);
    a.click();
    URL.revokeObjectURL(url);
    if (statusEl) statusEl.textContent = `Exported ${a.download}.`;
  });
}

async function openTestCodeMergePreview(rows) {
  const statusEl = $("#testcode-status");
  const panel = $("#testcode-merge-panel");
  if (!state.jobId) return;
  if (statusEl) statusEl.textContent = "Building merge preview…";
  try {
    const lang = state.exportLanguage || "EN";
    const data = await api(
      `/api/review/gtest-merge-saved-preview?job_id=${encodeURIComponent(state.jobId)}&language=${encodeURIComponent(lang)}`
    );
    state.testCode.mergePreview = data;
    if (panel) {
      panel.hidden = false;
      panel.innerHTML = renderTestCodeMergePanel(data);
      bindTestCodeMergePanelActions(data, statusEl);
    }
    if (statusEl) {
      statusEl.textContent = `Merge preview ready — ${data.saved_count || 0} saved, ${data.skipped_count || 0} skipped.`;
    }
    patchTestCodeCaseStatusUi();
  } catch (e) {
    if (statusEl) statusEl.textContent = e.message;
  }
}

function patchTestCodeShell({ rows, activeRow, draft, ws }) {
  const tc = state.testCode;
  const sampleName = document.querySelector(".gtest-sample-name");
  if (sampleName && (tc.codeStyleSamples?.[0] || ws?.code_style_samples?.[0])) {
    const s = tc.codeStyleSamples?.[0] || ws.code_style_samples[0];
    sampleName.textContent = s.label || s.source_file || "sample.cpp";
  }
  const reqEl = $("#testcode-user-request");
  if (reqEl && tc.userRequest != null) reqEl.value = tc.userRequest;
  const ioCtx = document.getElementById("testcode-io-context");
  if (ioCtx && activeRow) ioCtx.outerHTML = renderTestCodeIoContext(activeRow);
  if (draft) applyTestCodeDraftToUi(draft, activeRow);
  patchTestCodeCaseStatusUi();
  refreshM365TaskBanner();
}

async function renderTestCode(opts = {}) {
  const preserveSelection = opts.preserveSelection === true;
  const forceRefresh = opts.force === true;
  const skipShell = opts.skipShell === true;
  if (!state.jobId) {
    content().innerHTML = renderTestCodeHelpCard(
      "No active job",
      `<p class="detail">Import a Final TestSpec .xlsx or run Review specification first.</p>`,
      "Go to Review",
      "testcode-goto-review"
    );
    bindTestCodeHelp("testcode-goto-review", () => showPage("review"));
    return;
  }
  const hasShell = !!document.querySelector(".alex-testcode-page");
  if (!hasShell) {
    state.testCode.loading = true;
    content().innerHTML = `<p class="detail">Loading Test Code workspace…</p>`;
  }
  try {
    const jobReady =
      state.testCode.mounted && !forceRefresh ? true : await refreshJobSummary(forceRefresh);
    if (!state.jobId) {
      content().innerHTML = renderTestCodeHelpCard(
        "Review job expired",
        `<p class="detail">The saved job id was cleared because its bundle is missing.</p>`,
        "Run Review again",
        "testcode-goto-review"
      );
      bindTestCodeHelp("testcode-goto-review", () => showPage("review"));
      return;
    }
    if (!jobReady) {
      content().innerHTML = renderTestCodeHelpCard(
        "Review not ready",
        `<p class="detail">Analysis may still be running or the bundle was removed.</p>`,
        "Open Review",
        "testcode-goto-review"
      );
      bindTestCodeHelp("testcode-goto-review", () => showPage("review"));
      return;
    }

    const ws = forceRefresh ? await fetchGtestWorkspace(true) : await fetchGtestWorkspace();
    hydrateTestCodeWorkflowFromWorkspace(ws, { fullReset: !hasShell });
    const rows = ws.workbench_rows || [];
    const logicItems = ws.logic_items || [];
    if (!rows.length && !logicItems.length) {
      content().innerHTML = renderTestCodeHelpCard(
        "No test cases yet",
        `<p class="detail">This job has no workbook rows or logic groups. Run review on spec files that contain logic tables or test references.</p>`,
        "Open Final File",
        "testcode-goto-export"
      );
      bindTestCodeHelp("testcode-goto-export", () => showPage("export"));
      return;
    }
    const focusId = preserveSelection ? state.testCode.selectedCandidateId : state.workbookFocus.testcode;
    if (focusId && rows.some((r) => r.candidate_id === focusId)) {
      state.testCode.selectedCandidateId = focusId;
    } else if (rows.length) {
      const preferred = pickPreferredTestCodeRow(rows);
      state.testCode.selectedCandidateId = preferred?.candidate_id || rows[0].candidate_id;
      state.workbookFocus.testcode = state.testCode.selectedCandidateId;
    }
    const activeRow = rows.find((r) => r.candidate_id === state.testCode.selectedCandidateId);
    if (activeRow?.logic_id) state.testCode.selectedLogicId = activeRow.logic_id;
    else if (!state.testCode.selectedLogicId && logicItems.length) {
      state.testCode.selectedLogicId = state.selectedLogicId || logicItems[0].logic_id;
    }

    state.testCode.rows = rows;
    state.testCode.logicItems = logicItems;
    state.testCode.mounted = true;

    const cid = state.testCode.selectedCandidateId;
    state.testCode.lastDraftKey = cid;
    const draft = resolveDraftForCandidate(cid);
    state.testCode.draft = draft;

    if (hasShell && skipShell) {
      patchTestCodeShell({ rows, activeRow, draft, ws });
      return;
    }

    await refreshTestCodeSyncStatus();

    content().innerHTML = `<section class="alex-page alex-testcode-page alex-testcode-page--simple">
      ${renderM365KnowledgeBanner()}
      ${renderTestCodePageBody(rows, activeRow, draft, state.testCode.codeStyleSamples || ws.code_style_samples || [])}
      <div id="testcode-copilot-progress" hidden></div>
      <div id="testcode-apply-all-banner" hidden></div>
    </section>`;
    bindWorkbookTestcaseBar(rows, "testcode", renderTestCode);
    bindTestCodeHandlers(rows);
    bindTabHelpLinks();
  } catch (e) {
    content().innerHTML = `<div class="card">${explainTestCodeError(e.message)}
      <div class="review-actions" style="margin-top:1rem">
        <button class="btn" type="button" id="testcode-goto-review">Go to Review</button>
      </div></div>`;
    bindTestCodeHelp("testcode-goto-review", () => showPage("review"));
  } finally {
    state.testCode.loading = false;
  }
}

async function renderGuide() {
  const openId = state.guideOpenSection;
  state.guideOpenSection = null;
  content().innerHTML = `<header class="page-header">
      <h2>Hướng dẫn sử dụng ALEX</h2>
      <p class="lead">Bấm từng mục (▼) để mở/đóng hướng dẫn theo chức năng. Mỗi tab workflow cũng có hộp <b>?</b> thu gọn ở đầu trang.</p>
    </header>
    ${renderGuideCard()}`;
  bindTabHelpLinks();
  if (openId) {
    const el = document.getElementById(openId);
    if (el?.tagName === "DETAILS") {
      el.open = true;
      requestAnimationFrame(() => el.scrollIntoView({ behavior: "smooth", block: "start" }));
    }
  }
}

async function boot() {
  initThemeToggle();
  const m365ExpiredBtn = $("#btn-m365-expired-signin");
  if (m365ExpiredBtn) {
    m365ExpiredBtn.onclick = () => {
      showPage("review");
      document.getElementById("ai-signin-details")?.setAttribute("open", "open");
      signInM365().catch(() => {});
    };
  }
  await ensureAuthenticated();
  initNav();
  initRouting();
  const signOutBtn = $("#btn-sign-out");
  if (signOutBtn) signOutBtn.onclick = () => signOut();
  await loadAppConfig();
  startServiceStatusPolling();
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshServiceStatusNow();
  });
  state.routingBoot = true;
  const jobFromUrl = readJobIdFromUrl();
  let savedJob = null;
  try {
    savedJob = sessionStorage.getItem("alex.currentJobId");
  } catch (_) {
    savedJob = null;
  }
  setJobId(jobFromUrl || savedJob || null);
  updateSelectedCount();
  await refreshJobSummary();
  const initialPage = resolveInitialPage(state._summaryCache?.summary);
  showPage(initialPage, { replace: true });
  state.routingBoot = false;
  await resumeM365Tasks();
}

boot();
