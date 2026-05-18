/**
 * ALEX — engineering review workflow (trace evidence, approve, export).
 */
const PAGES = [
  { id: "review", step: "1", label: "Review", icon: "review" },
  { id: "logic-review", step: "2", label: "Logic & Definitions", icon: "logic" },
  { id: "diagram-graph", step: "3", label: "Diagram Graph", icon: "diagram" },
  { id: "export", step: "4", label: "Final File", icon: "export" },
  { id: "guide", step: "5", label: "Guide", icon: "guide" },
];

const FILE_TYPE_OPTIONS = [
  { value: "system_spec", label: "System Spec" },
  { value: "test_spec", label: "Test Spec" },
  { value: "sample_code", label: "Sample Code" },
  { value: "test_code", label: "Test Code" },
];

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
  },
  inboxFocus: {},
  diagramFocus: {
    state: null,
    edgeKey: null,
    match: null,
  },
  serviceStatusTimer: null,
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
};

const $ = (sel) => document.querySelector(sel);
const content = () => $("#content");

function setJobId(id) {
  state.jobId = id;
  const el = $("#job-id");
  if (el) el.textContent = id ? id.slice(-16) : "—";
}

function api(path, opts = {}) {
  return fetch(path, opts).then(async (r) => {
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
    if (ct.includes("json")) return r.json();
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
  try {
    return JSON.stringify(src);
  } catch {
    return String(src);
  }
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
  const st = await api("/api/copilot/status");
  state.copilot.status = st;
  return st;
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
    return `<span class="auth-badge auth-badge--ok">${icon("check", "alex-icon--badge")} AUTH OK</span>`;
  }
  if (m.client_id_configured) {
    return `<span class="auth-badge auth-badge--warn">SIGN IN</span>`;
  }
  return `<span class="auth-badge auth-badge--err">NEEDS CLIENT ID</span>`;
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
    ready_for_ai: "ready for AI",
    blocked_missing_definition: "blocked",
    needs_engineer_answer: "needs answer",
    ai_drafted: "AI drafted",
    completed: "completed",
    no_rows: "no rows",
  }[status] || status || "unknown";
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

function resolutionLabel(value) {
  return {
    definition_found: "found",
    added_context_found: "added context",
    missing_definition: "missing",
  }[value] || value || "review";
}

function renderCapabilitySummary(_capability) {
  return "";
}

function renderGuideCard() {
  return "";
}

function inboxFocusTerm(inbox) {
  if (!inbox?.terms?.length) return null;
  const current = state.inboxFocus[inbox.logic_id];
  return inbox.terms.find((row) => row.term === current) || inbox.terms[0];
}

function renderAiQueue(_queue) {
  return "";
}

async function refreshJobSummary() {
  if (!state.jobId) {
    $("#stat-ready").textContent = "—";
    $("#stat-blocked").textContent = "—";
    $("#stat-missing").textContent = "—";
    $("#stat-logic").textContent = "—";
    return;
  }
  try {
    const s = await api(`/api/jobs/${encodeURIComponent(state.jobId)}/summary`);
    applyJobSummary(s.summary || {});
  } catch (_) {
    /* job bundle not ready */
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

function requireJobHtml() {
  return `<div class="card">
    <p><b>No review yet.</b> On <b>Spec review</b>, select files and click <b>Review specification</b>.</p>
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
      if (btn.dataset.page !== "review") refreshJobSummary();
    });
  });
}

function showPage(id) {
  $("#nav").querySelectorAll("button").forEach((b) => {
    b.classList.toggle("active", b.dataset.page === id);
  });
  const map = {
    review: renderReview,
    "logic-review": renderLogicReview,
    "diagram-graph": renderDiagramGraph,
    export: renderExport,
    guide: renderGuide,
  };
  (map[id] || renderReview)();
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
      const pt = $("#progress-text");
      const pf = $("#progress-fill");
      if (pt) pt.textContent = st.current_step || st.status;
      if (pf) pf.style.width = (st.progress || 0) + "%";
      if (st.status === "completed") {
        clearInterval(state.pollTimer);
        await refreshJobSummary();
        if (pt) pt.textContent = "Review complete.";
        await loadReviewResults();
      }
      if (st.status === "failed") {
        clearInterval(state.pollTimer);
        if (pt) pt.textContent = "Failed: " + (st.error_message || "unknown");
      }
    } catch (e) {
      const pt = $("#progress-text");
      if (pt) pt.textContent = e.message;
    }
  }, 800);
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
    const copilot = await loadCopilotStatus().catch(() => null);
    const data = await api("/api/files");
    state.files = data.files || [];
    updateSelectedCount();
    const n = state.files.filter((f) => f.selected).length;

    content().innerHTML = `<header class="page-header">
        <h2>Sources &amp; analyze</h2>
        <p class="lead">Select files, run one analysis pass, then continue to Logic review. Re-upload if you changed a local file.</p>
      </header>
      ${renderReviewLoginHub(copilot)}
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
      <div id="progress-area" class="card" style="display:none;margin-top:0.75rem">
        <p id="progress-text">Starting…</p>
        <div class="progress-bar"><div id="progress-fill" style="width:0%"></div></div>
      </div>
      <p id="review-run-status" class="detail"></p>
      <div id="review-results" style="display:none;margin-top:0.75rem"></div>`;

    $("#file-upload").onchange = async () => {
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
    };

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

    $("#chk-all").onchange = () => {
      const on = $("#chk-all").checked;
      state.files.forEach((f) => (f.selected = on));
      scheduleSaveSelection();
      renderSourcesTable();
      updateReviewButton();
    };

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

    $("#btn-copilot-login").onclick = async () => {
      const testBtn = $("#btn-copilot-test-prompt");
      if (testBtn) testBtn.disabled = true;
      await startCopilotLogin(async () => {
        const fresh = await loadCopilotStatus().catch(() => null);
        $("#copilot-review-status").innerHTML = copilotStatusHtml(fresh);
        refreshGithubAuthBadge(fresh);
        if (testBtn) testBtn.disabled = false;
      });
    };

    $("#btn-copilot-check").onclick = async () => {
      await verifyCopilot(async () => {
        const fresh = await loadCopilotStatus().catch(() => null);
        $("#copilot-review-status").innerHTML = copilotStatusHtml(fresh);
        refreshGithubAuthBadge(fresh);
      }, { deep: false });
    };

    $("#btn-copilot-test-prompt").onclick = async () => {
      await verifyCopilot(async () => {
        const fresh = await loadCopilotStatus().catch(() => null);
        $("#copilot-review-status").innerHTML = copilotStatusHtml(fresh);
        refreshGithubAuthBadge(fresh);
      }, { deep: true });
    };

    bindReviewLoginHub();
    refreshCopilotLoginContainers();
    renderSourcesTable();
    updateReviewButton();
    refreshJobSummary();
    if (state.jobId) loadReviewResults();
  } catch (e) {
    content().innerHTML = `<p class="detail" style="color:var(--red)">${esc(e.message)}</p>`;
  }
}
function renderTreeLines(lines) {
  if (!lines?.length) return "<p class='detail'>No tree lines.</p>";
  return `<pre class="tree-view logic-tree-pre">${esc(lines.join("\n"))}</pre>`;
}

function traceStatusLabel(status) {
  if (status === "resolved") return "resolved";
  if (status === "needs_review") return "resolved, review";
  return "missing definition";
}

function renderTraceRows(traceRows) {
  if (!traceRows?.length) return "<p class='detail'>No referenced terms detected.</p>";
  return `<div class="grid-wrap"><table class="data-grid alex-table alex-trace-table"><thead><tr>
    <th class="col-term">Term</th><th class="col-status">Status</th><th>What we found</th><th>Sources</th>
  </tr></thead><tbody>${traceRows
    .map((row) => {
      const statusClass =
        row.status === "resolved" ? "high" : row.status === "needs_review" ? "warning" : "error";
      const chips = [];
      (row.definitions || []).slice(0, 4).forEach((d) => {
        const kind = d.kind === "added_file" ? "file" : d.kind === "engineer_note" ? "note" : "spec";
        const label = (d.name || "term").length > 28 ? `${(d.name || "term").slice(0, 25)}…` : d.name || "term";
        chips.push({
          kind,
          label,
          detail: [d.name, formatSourceReadable(d.source), d.definition].filter(Boolean).join("\n"),
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
        <td><span class="tag ${statusClass}">${esc(traceStatusLabel(row.status))}</span></td>
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
    .map((row) => `<div class="issue-pill">
      <span class="tag ${queueStatusClass(row.status === "ok" ? "completed" : row.status === "error" ? "blocked_missing_definition" : "needs_engineer_answer")}">${esc(row.status)}</span>
      <span class="issue-main"><b>${esc(row.title)}</b></span>
      <span class="issue-detail">${esc(row.message)}${row.count > 1 ? ` (${row.count})` : ""}</span>
    </div>`)
    .join("")}</div>`;
}

function renderDefinitionInbox(inbox, { engineerNote = "", attachments = [] } = {}) {
  if (!inbox?.terms?.length) return "<p class='detail'>No definition work items for this logic group.</p>";
  const current = inboxFocusTerm(inbox);
  state.inboxFocus[inbox.logic_id] = current?.term || "";
  const currentStatusClass = current?.resolution === "definition_found"
    ? "high"
    : current?.resolution === "added_context_found"
      ? "warning"
      : "error";
  const defs = (current?.definitions || [])
    .map((d) => `<li><b>${esc(d.kind)}</b>${d.match_mode && d.match_mode !== "exact" ? ` · ${esc(d.match_mode)} match` : ""} · ${esc(formatSourceReadable(d.source) || "unknown source")}<br>${esc(d.definition || "")}</li>`)
    .join("");
  const queryHistory = (inbox.query_history || []).slice().reverse();
  return `<div class="definition-workbench">
    <div class="definition-term-list">
      ${inbox.terms.map((term) => {
        const statusClass = term.resolution === "definition_found"
          ? "high"
          : term.resolution === "added_context_found"
            ? "warning"
            : "error";
        return `<button class="term-chip ${term.term === current?.term ? "active" : ""}" data-term-pick="${esc(term.term)}">
          <span class="term-chip-name">${esc(term.term)}</span>
          <span class="tag ${statusClass}">${esc(resolutionLabel(term.resolution))}</span>
        </button>`;
      }).join("")}
      ${inbox.unused_added_definitions?.length ? `<div class="definition-card mini">
        <div class="definition-head"><b>Unused added definitions</b></div>
        <ul class="detail">${inbox.unused_added_definitions
          .map((row) => `<li><code>${esc(row.name)}</code> · ${esc(row.source)}</li>`)
          .join("")}</ul>
      </div>` : ""}
    </div>
    <div class="definition-panel">
      ${current ? `<div class="definition-card">
        <div class="definition-head">
          <code>${esc(current.term)}</code>
          <span class="tag ${currentStatusClass}">${esc(resolutionLabel(current.resolution))}</span>
        </div>
        <p><b>${esc(reasonCodeLabel(current.reason_code))}</b> · ${esc(current.reason_detail || "")}</p>
        ${defs ? `<ul class="detail">${defs}</ul>` : "<p class='detail'>No trusted definition attached yet.</p>"}
      </div>` : ""}
      <div class="definition-card">
        <div class="definition-head">
          <b>Knowledge workbench</b>
        </div>
        <p class="detail">Sign in to M365 or GitHub Copilot on the <b>Review</b> tab. Knowledge is applied when you resolve with AI.</p>
        <textarea id="definition-workbench-note" class="clarify-box definition-query-box" placeholder="Engineer rules, boundary values, signal meanings…">${esc(engineerNote)}</textarea>
        <div class="definition-workbench-actions">
          <button class="btn" id="btn-definition-query">Resolve with AI</button>
          <label class="btn secondary upload-label">Attach files<input type="file" id="logic-attachment-upload" multiple hidden /></label>
        </div>
        ${attachments.length ? `<div class="definition-attachments detail">${attachments.map((a) => `<div><b>${esc(a.name)}</b>${a.definition_count ? ` · ${esc(String(a.definition_count))} definition(s)` : ""}</div>`).join("")}</div>` : ""}
        <div data-definition-query-status class="detail"></div>
      </div>
      ${queryHistory.length ? `<div class="definition-card">
        <div class="definition-head"><b>Recent Copilot answers</b></div>
        <div class="definition-history">${queryHistory
          .map((row) => `<div class="history-item">
            <p><b>${esc(row.term || "")}</b> · ${esc(row.question || "")}</p>
            <p>${esc(row.answer || "")}</p>
            ${row.suggested_matches?.length ? `<p class="detail">Matches: ${row.suggested_matches.map((m) => `${m.name} (${m.confidence || "low"})`).join(", ")}</p>` : ""}
            ${row.follow_up_questions?.length ? `<p class="detail">Follow-up: ${esc(row.follow_up_questions[0])}</p>` : ""}
          </div>`)
          .join("")}</div>
      </div>` : ""}
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
    { key: "test_function", label: "Test Function", editable: false, colClass: "col-fn" },
    { key: "event", label: "Event", editable: false },
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
  return api(`/api/review/workbench-row?job_id=${encodeURIComponent(state.jobId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

async function loadAppConfig() {
  try {
    state.appConfig = await api("/api/app-config");
  } catch {
    state.appConfig = { features: { validator: false, add_clone_tc: false }, export: { strict: false } };
  }
}

function formatOllamaTopbarStatus(st) {
  if (!st) return "Loading…";
  if (!st.enabled && !st.allow_ollama_fallback) return "Disabled";
  const ok = st.ollama?.reachable;
  if (ok) {
    const model = st.ollama?.resolved_model || st.ollama?.model || "Model";
    return `Online · ${model}`;
  }
  if (st.allow_ollama_fallback) return "Offline";
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

function applyOllamaTopbarStatus(st) {
  const el = $("#stat-ollama");
  if (!el) return;
  el.textContent = formatOllamaTopbarStatus(st);
  const ok = !!(st?.ollama?.reachable);
  const enabled = !!(st?.enabled || st?.allow_ollama_fallback);
  const parent = el.parentElement;
  if (parent) {
    parent.classList.toggle("high", ok);
    parent.classList.toggle("err", enabled && !ok);
    parent.classList.toggle("warn", !enabled);
  }
}

function applyM365TopbarStatus(st) {
  const el = $("#stat-m365");
  if (!el) return;
  el.textContent = formatM365TopbarStatus(st);
  const ready = !!(st?.api_ready || st?.connected);
  const parent = el.parentElement;
  if (parent) {
    parent.classList.toggle("high", ready);
    parent.classList.toggle("err", !ready);
    parent.classList.toggle("warn", !ready && st?.client_id_configured);
  }
}

async function loadOllamaStatus() {
  const el = $("#stat-ollama");
  if (!el) return;
  try {
    const st = await api("/api/llm/status");
    state.ollamaStatus = st;
    applyOllamaTopbarStatus(st);
  } catch {
    el.textContent = "Unavailable";
    el.parentElement?.classList.add("err");
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

function m365KnowledgeReady() {
  return !!(state.m365Status?.api_ready || state.m365Status?.connected);
}

function sleepMs(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function m365ReviewStatusText(st) {
  if (!st) return "Loading…";
  if (st.api_ready || st.connected) {
    const who = st.display_name || st.user_principal || "M365";
    return `Signed in: ${who}`;
  }
  if (st.client_id_configured) return "Client ID saved. Click Sign in.";
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
  const ready = m365KnowledgeReady();
  if (signOut) signOut.hidden = !ready;
  if (signIn) signIn.disabled = ready || !!state.m365LoginInProgress;
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
  } catch {
    const el = $("#stat-m365");
    if (el) el.textContent = "Unavailable";
    el?.parentElement?.classList.add("err");
  }
  refreshReviewM365Tile();
}

function renderReviewLoginHub(copilot) {
  const m = state.m365Status || {};
  return `<section class="card login-hub">
      <h3>AI sign-in</h3>
      <div class="login-hub-grid">
        <article class="login-tile">
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
        </article>
        <article class="login-tile">
          <div class="login-tile-head">
            ${icon("microsoft", "alex-icon--brand")}
            <h4>Microsoft 365 Copilot</h4>
            <span id="m365-auth-badge">${m365AuthBadge(m)}</span>
          </div>
          <p id="review-m365-status" class="detail">${esc(m365ReviewStatusText(m))}</p>
          <label class="detail login-compact-label">Application (client) ID
            <input type="text" id="m365-setup-client-id" class="clarify-box" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" autocomplete="off" />
          </label>
          <label class="detail login-compact-label">Tenant
            <input type="text" id="m365-setup-tenant-id" class="clarify-box" placeholder="common" autocomplete="off" value="common" />
          </label>
          <div class="review-actions" style="margin-top:0.5rem">
            <button type="button" class="btn secondary" id="btn-m365-save-setup">Save</button>
            <button type="button" class="btn secondary" id="btn-m365-connect">Sign in</button>
            <button type="button" class="btn secondary" id="btn-m365-disconnect" hidden>Sign out</button>
            <button type="button" class="btn secondary" id="btn-m365-reset-setup">Clear</button>
          </div>
          <div id="m365-login-panel" class="m365-login-panel" hidden>
            <p class="detail">1. Open <a id="m365-login-link" href="https://microsoft.com/devicelogin" target="_blank" rel="noopener noreferrer">microsoft.com/devicelogin</a></p>
            <p class="detail">2. Code: <code id="m365-login-code" class="m365-user-code">—</code>
              <button type="button" class="btn secondary" id="btn-m365-copy-code">Copy</button></p>
            <p class="detail" id="m365-login-wait">Waiting for sign-in…</p>
          </div>
          <p id="m365-setup-hint" class="detail err" hidden></p>
        </article>
      </div>
    </section>`;
}

function bindReviewLoginHub() {
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
        if (wait) wait.textContent = "Code copied. Paste it at microsoft.com/devicelogin";
      }
    };
  }
  const m365ConnectBtn = $("#btn-m365-connect");
  if (m365ConnectBtn) {
    m365ConnectBtn.onclick = async () => {
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
}

function showM365LoginPanel(start) {
  const panel = $("#m365-login-panel");
  const link = $("#m365-login-link");
  const codeEl = $("#m365-login-code");
  const wait = $("#m365-login-wait");
  const uri = start.verification_uri || "https://microsoft.com/devicelogin";
  const code = start.user_code || "";
  if (panel) panel.hidden = false;
  if (link) {
    link.href = uri;
    link.textContent = uri.replace(/^https:\/\//, "");
  }
  if (codeEl) codeEl.textContent = code || "—";
  if (wait) wait.textContent = "Waiting for you to sign in in the browser…";
  state.m365LoginInProgress = true;
  refreshReviewM365Tile();
}

function hideM365LoginPanel() {
  const panel = $("#m365-login-panel");
  if (panel) panel.hidden = true;
  state.m365LoginInProgress = false;
  refreshReviewM365Tile();
}

async function saveM365Setup() {
  const clientId = $("#m365-setup-client-id")?.value?.trim() || "";
  const tenantId = $("#m365-setup-tenant-id")?.value?.trim() || "common";
  if (!clientId) throw new Error("Paste the Application (client) ID from Azure.");
  await api("/api/m365/setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, tenant_id: tenantId }),
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
  if (tid) tid.value = "common";
  await loadM365Status();
}

function showM365SetupError(message) {
  const hint = $("#m365-setup-hint");
  if (hint) {
    hint.hidden = false;
    hint.textContent = message;
  }
}

async function signInM365() {
  await loadM365Status();
  if (state.m365Status?.setup_required) {
    throw new Error("Save the M365 Client ID on the Review tab before signing in.");
  }
  const pollStatus = (msg) => setM365AuthMessage(msg);
  pollStatus("Starting M365 sign-in…");
  let start;
  try {
    start = await api("/api/m365/login/start", { method: "POST" });
  } catch (e) {
    showM365SetupError(e.message || String(e));
    throw e;
  }
  showM365LoginPanel(start);
  const uri = start.verification_uri || "https://microsoft.com/devicelogin";
  const code = start.user_code || "";
  pollStatus(`Open the link below and enter code ${code}`);
  try {
    window.open(uri, "_blank", "noopener,noreferrer");
  } catch (_) {
    /* popup blocked — user uses the visible link */
  }
  const intervalMs = Math.max(3, Number(start.interval || 5)) * 1000;
  const deadline = Date.now() + Number(start.expires_in || 900) * 1000;
  while (Date.now() < deadline) {
    await sleepMs(intervalMs);
    const poll = await api("/api/m365/login/poll", { method: "POST" });
    if (poll.ok && poll.status === "completed") {
      hideM365LoginPanel();
      await loadM365Status();
      pollStatus(`Signed in: ${poll.display_name || "M365 user"}.`);
      refreshReviewM365Tile();
      return poll;
    }
    if (poll.status === "failed") {
      hideM365LoginPanel();
      const msg = poll.error || "M365 sign-in failed.";
      showM365SetupError(msg);
      throw new Error(msg);
    }
    const wait = $("#m365-login-wait");
    if (wait) wait.textContent = `Waiting… enter code ${code} at microsoft.com/devicelogin`;
  }
  hideM365LoginPanel();
  throw new Error("Sign-in timed out. Click Sign in Microsoft 365 and try again.");
}

async function disconnectM365() {
  await api("/api/m365/disconnect", { method: "POST" });
  await loadM365Status();
}

function assistEnabled() {
  return featureOn("ollama_assist") || state.appConfig?.llm?.enabled;
}

function featureOn(name) {
  return !!(state.appConfig?.features?.[name]);
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
  return `<div class="tcase-bar" data-tcase-scope="${esc(scope)}" role="tablist" aria-label="Test cases">
    ${rows
      .map((row) => {
        const active = row.candidate_id === activeId;
        const label = row.candidate_id || `Row ${row.no}`;
        const meta = row.event || row.test_function || "";
        return `<button type="button" class="tcase-pick ${active ? "active" : ""}" data-tcase-id="${esc(
          row.candidate_id || ""
        )}" role="tab" aria-selected="${active}">
          <span class="tcase-pick__id">${esc(label)}</span>
          ${meta ? `<span class="tcase-pick__meta">${esc(meta)}</span>` : ""}
        </button>`;
      })
      .join("")}
  </div>`;
}

function renderWorkbookFocusEditor(rows, { language = "EN", scope = "export", title = "Test case editor" } = {}) {
  const row = currentFocusRow(rows, scope);
  if (!row) return "<p class='detail'>No final workbook rows yet.</p>";
  state.workbookFocus[scope] = row.candidate_id;
  const statusClass =
    row.review_status === "ready" || row.review_status === "approved"
      ? "high"
      : row.review_status === "blocked"
        ? "error"
        : "warning";
  return `<div class="card workbook-focus-card" id="${scope}-workbook-anchor">
    <div class="focus-head">
      <div>
        <h4>${esc(title)}</h4>
        <p class="detail"><b>${esc(row.candidate_id || "")}</b> · ${esc(row.test_function || "")} · ${esc(row.event || "")}
          <span class="tag ${statusClass}" style="margin-left:0.35rem">${esc(row.review_status || "pending")}</span>
          ${renderValidationBadge(row)} ${renderTermRoleHint(row)}</p>
      </div>
    </div>
    <div class="focus-grid focus-grid--workbook">
      <label class="focus-span-2">UseCase<textarea id="${scope}-focus-use_case" class="focus-text focus-text--wide">${esc(row.use_case || "")}</textarea></label>
      <label class="focus-span-2">Operation<textarea id="${scope}-focus-operation" class="focus-text focus-text--wide">${esc(row.operation || "")}</textarea></label>
      <label>Expected input<textarea id="${scope}-focus-expected_input" class="focus-text focus-text--io">${esc(row.expected_input || "")}</textarea></label>
      <label>Expected output<textarea id="${scope}-focus-expected_output" class="focus-text focus-text--io">${esc(row.expected_output || "")}</textarea></label>
    </div>
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
      ${
        assistEnabled()
          ? `<button type="button" class="btn secondary" id="${scope}-focus-improve-io">Improve I/O (AI)</button>`
          : ""
      }
      ${
        featureOn("add_clone_tc")
          ? `<button type="button" class="btn secondary" id="${scope}-focus-add">+ Add test case</button>
      <button type="button" class="btn secondary" id="${scope}-focus-clone">Clone</button>
      ${
        ["engineer_manual", "engineer_clone"].includes(String(row.source || ""))
          ? `<button type="button" class="btn secondary" id="${scope}-focus-delete">Delete</button>`
          : ""
      }`
          : ""
      }
    </div>
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
        .map(
          (col) =>
            `<td class="${col.colClass || ""}" data-col="${esc(col.key)}">${renderWorkbookValue(row, col, editable, idx, {
              spreadsheet,
            })}</td>`
        )
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
  document.querySelectorAll(`[data-tcase-scope="${scope}"] .tcase-pick`).forEach((btn) => {
    btn.onclick = () => {
      const id = btn.dataset.tcaseId;
      if (!id || state.workbookFocus[scope] === id) return;
      state.workbookFocus[scope] = id;
      onReload();
    };
  });
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
    if (statusEl) statusEl.textContent = `Saving ${row.candidate_id}…`;
    const payload = {
      candidate_id: row.candidate_id,
      language,
      use_case: document.getElementById(`${scope}-focus-use_case`)?.value || "",
      operation: document.getElementById(`${scope}-focus-operation`)?.value || "",
      expected_input: document.getElementById(`${scope}-focus-expected_input`)?.value || "",
      expected_output: document.getElementById(`${scope}-focus-expected_output`)?.value || "",
      review_status: document.getElementById(`${scope}-focus-review_status`)?.value || "pending",
      engineer_confirmation_required: document.getElementById(`${scope}-focus-engineer_confirmation_required`)?.value || "yes",
    };
    if (language !== "EN") {
      payload.open_questions = document.getElementById(`${scope}-focus-open_questions`)?.value || "";
    }
    try {
      await saveWorkbookRow(payload);
      await refreshJobSummary();
      if (statusEl) statusEl.textContent = `${row.candidate_id} saved.`;
      onReload();
    } catch (e) {
      if (statusEl) statusEl.textContent = e.message;
    }
  };
  const row = currentFocusRow(rows, scope);
  if (!row) return;
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

  const improveIoBtn = document.getElementById(`${scope}-focus-improve-io`);
  if (improveIoBtn) {
    improveIoBtn.onclick = async () => {
      const focusRow = currentFocusRow(rows, scope);
      if (!focusRow) return;
      const statusEl = statusElSelector ? document.querySelector(statusElSelector) : null;
      if (statusEl) statusEl.textContent = "Ollama improving I/O…";
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
        if (!res.ok) throw new Error(res.error || "Ollama assist failed");
        const patch = res.result || {};
        if (patch.expected_input) {
          document.getElementById(`${scope}-focus-expected_input`).value = patch.expected_input;
        }
        if (patch.expected_output) {
          document.getElementById(`${scope}-focus-expected_output`).value = patch.expected_output;
        }
        if (statusEl) statusEl.textContent = "Review Ollama suggestion, then Save row.";
      } catch (e) {
        if (statusEl) statusEl.textContent = e.message;
      }
    };
  }

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
  return api(`/api/review/workbench?job_id=${encodeURIComponent(state.jobId)}&language=${encodeURIComponent(language)}`);
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

function renderDiagramFocus(edge, overlay) {
  if (!edge) return `<div class="card"><h4>Transition focus</h4><p class="detail">Select a transition edge to inspect its evidence.</p></div>`;
  const conditionChips = (edge.conditions || []).map((text) => {
    const value = String(text || "");
    return {
      kind: "note",
      label: value.length > 36 ? `${value.slice(0, 33)}…` : value,
      detail: value,
    };
  });
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

async function renderDiagramGraph() {
  if (!state.jobId) {
    content().innerHTML = requireJobHtml();
    bindNoJob();
    return;
  }
  await refreshJobSummary();
  try {
    const data = await api(`/api/review/states?job_id=${encodeURIComponent(state.jobId)}`);
    const semantics = data.diagram_semantics || {};
    const rawTransitions = data.transitions || [];
    const diagrams = data.diagrams || [];
    const rawStates = semantics.states?.length ? semantics.states : data.states || [];
    const states = rawStates.map((row) => (typeof row === "string" ? row : row?.name || "")).filter(Boolean);
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
        ["OCR mentions", semanticSummaryValue(summary, "state_mentions", 0)],
      ], { compact: true })}
      <div class="review-actions" style="margin-bottom:1rem">
        <button class="btn secondary" id="btn-diagram-logic">Logic &amp; definitions</button>
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
          ${renderDiagramFocus(activeEdge, overlay)}
        </div>
      </div>
      <details class="alex-flow-panel alex-ref-panel">
        <summary>Transition flow map (compact)</summary>
        <div class="alex-ref-body">${renderDiagramFlow(filteredEdges)}</div>
      </details>`;
    $("#btn-diagram-logic").onclick = () => showPage("logic-review");
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
  } catch (e) {
    content().innerHTML = `<p class="detail" style="color:var(--red)">${esc(e.message)}</p>`;
  }
}

async function renderLogicReview() {
  if (!state.jobId) {
    content().innerHTML = requireJobHtml();
    bindNoJob();
    return;
  }
  await refreshJobSummary();
  try {
    const data = await api(`/api/review/logic-review?job_id=${state.jobId}`);
    state.bundle = {
      ...(state.bundle || {}),
      term_roles: data.term_roles || state.bundle?.term_roles || {},
    };
    const items = data.logic_review_items || [];
    if (!items.length) {
      content().innerHTML = `<h2>Logic Review</h2><p class="detail">No logic blocks in this job.</p>`;
      return;
    }
    const sel = state.selectedLogicId || items[0].logic_id;
    const item = items.find((x) => x.logic_id === sel) || items[0];
    const [inbox, workbench] = await Promise.all([
      api(`/api/review/definition-inbox?job_id=${encodeURIComponent(state.jobId)}&logic_id=${encodeURIComponent(item.logic_id)}`),
      fetchWorkbench(state.exportLanguage),
    ]);
    const queueByLogic = Object.fromEntries(((data.ai_queue?.logic_groups) || []).map((row) => [row.logic_id, row]));
    const queueItem = queueByLogic[item.logic_id] || {};
    const engineerNote = (data.ai_assists?.engineer_notes || {})[item.logic_id] || "";
    const attachments = (data.ai_assists?.logic_attachments || {})[item.logic_id] || [];
    const relatedCandidateIds = new Set((item.candidates || []).map((row) => row.id));
    const logicRows = (workbench.rows || []).filter(
      (row) => row.logic_id === item.logic_id || relatedCandidateIds.has(row.candidate_id)
    );
    const treeHtml = renderTreeLines(item.tree_lines || []);
    const listHtml = items
      .map(
        (it) =>
          `<button class="logic-pick ${it.logic_id === item.logic_id ? "active" : ""}" data-lid="${esc(
            it.logic_id
          )}">${esc(it.control_name)} <span class="tag ${queueStatusClass(queueByLogic[it.logic_id]?.queue_status)}">${esc(
            queueStatusLabel(queueByLogic[it.logic_id]?.queue_status)
          )}</span></button>`
      )
      .join("");
    const tableRows = (item.table_rows || []).map((r) => [
      r.row_no,
      esc(r.raw_condition),
      r.depth,
      esc(r.detected_type),
      esc(r.parser_reason || ""),
    ]);
    const parserNotes = (item.parser_notes || []).map((n) => esc(n.parser_reason || n.message || JSON.stringify(n)));
    const sourceEvidenceHtml = item.source_evidence
      ? typeof item.source_evidence === "object"
        ? renderEvidenceNotes(
            [
              {
                kind: "source",
                label: basename(item.source_evidence.file || item.source_evidence.summary || "source"),
                detail: formatSourceReadable(item.source_evidence),
              },
            ],
            { label: "Source file" }
          )
        : renderEvidenceNotes(parseLegacyEvidenceString(item.source_evidence), { label: "Source file" })
      : "";
    content().innerHTML = `<div class="alex-layout-logic">
      <div class="logic-pick-bar">${listHtml}</div>
      <header class="alex-hero">
        <div>
          <h2 class="alex-hero__title">${esc(item.control_name)}</h2>
          <p class="alex-hero__sub">Read the logic tree first, then trace terms and fix definitions.</p>
        </div>
        <div class="alex-hero__badges">
          <span class="tag ${item.parse_status === "ok" ? "high" : "error"}">parse ${esc(item.parse_status)}</span>
          ${
            item.gate_status
              ? `<span class="tag ${item.gate_status === "ready" ? "high" : item.gate_status === "needs_llm" ? "warn" : "error"}">gate ${esc(item.gate_status)}</span>`
              : ""
          }
          <span class="tag ${queueStatusClass(queueItem.queue_status)}">${esc(queueStatusLabel(queueItem.queue_status))}</span>
        </div>
      </header>
      ${sourceEvidenceHtml}
      ${item.unresolved_refs?.length ? `<p class="detail" style="margin-bottom:1rem"><b>Missing definitions:</b> ${esc(item.unresolved_refs.join(", "))}</p>` : ""}
      <section class="alex-primary-panel">
        <h3 class="alex-primary-panel__label">Logic structure</h3>
        <p class="detail" style="margin-top:0">Compare the parsed tree with the logic cut from the specification.</p>
        <div class="logic-compare-grid">
          <div>
            <h4 class="logic-compare__label">Tree logic</h4>
            <div class="gate-diagram logic-tree-pre">${treeHtml}</div>
          </div>
          <div>
            <h4 class="logic-compare__label">Raw expression (from spec)</h4>
            <pre class="expr-block expr-block--spec">${esc(logicSpecExpression(item))}</pre>
          </div>
        </div>
        ${parserNotes.length ? `<ul class="detail" style="margin-top:0.75rem">${parserNotes.map((n) => `<li>${n}</li>`).join("")}</ul>` : ""}
      </section>
      <div class="alex-secondary-row alex-secondary-row--full">
        <section>
          <h4>Evidence &amp; definitions</h4>
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
          <div class="alex-definitions-block" style="margin-top:1.25rem">
            <h4>Definitions</h4>
            ${renderDefinitionInbox(inbox, { engineerNote, attachments })}
          </div>
          ${(item.issues || []).length ? `<div style="margin-top:1rem"><h4>Linked issues</h4>${renderIssueList(item.issues || [])}</div>` : ""}
        </section>
      </div>
      <section class="workbook-workspace workbook-workspace--logic" style="margin-top:1rem">
        <h4>Final workbook rows (this logic group)</h4>
        ${renderWorkbookTestcaseBar(logicRows, "logic")}
        ${renderWorkbookFocusEditor(logicRows, { language: state.exportLanguage, scope: "logic" })}
        <p id="logic-row-save-status" class="detail"></p>
      </section>
    </div>`;
    content().querySelectorAll(".logic-pick").forEach((btn) => {
      btn.onclick = () => {
        state.selectedLogicId = btn.dataset.lid;
        renderLogicReview();
      };
    });
    content().querySelectorAll("[data-term-pick]").forEach((btn) => {
      btn.onclick = () => {
        state.inboxFocus[item.logic_id] = btn.dataset.termPick;
        renderLogicReview();
      };
    });
    const applyKnowledge = async (statusMessage = "Saving knowledge…") => {
      const note = $("#definition-workbench-note")?.value || "";
      const current = inboxFocusTerm(inbox);
      const statusEl = document.querySelector("[data-definition-query-status]");
      if (statusEl) statusEl.textContent = statusMessage;
      return api(`/api/review/logic-clarification?job_id=${encodeURIComponent(state.jobId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ logic_id: item.logic_id, note, term: current?.term || "" }),
      });
    };
    $("#logic-attachment-upload").onchange = async () => {
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
        if (attachStatus) attachStatus.textContent = "Attachment(s) saved.";
        renderLogicReview();
      } catch (e) {
        if (attachStatus) attachStatus.textContent = e.message;
      }
      inp.value = "";
    };
    const definitionQueryBtn = $("#btn-definition-query");
    if (definitionQueryBtn) {
      definitionQueryBtn.onclick = async () => {
        const current = inboxFocusTerm(inbox);
        const note = $("#definition-workbench-note")?.value || "";
        const question = note.trim();
        const statusEl = document.querySelector("[data-definition-query-status]");
        if (!question.trim()) {
          if (statusEl) statusEl.textContent = "Enter the missing meaning or pasted evidence first.";
          return;
        }
        const requireM365 = state.appConfig?.assist?.require_m365_login !== false;
        if (requireM365 && !m365KnowledgeReady()) {
          const msg = "Sign in to M365 on the Review tab first.";
          if (statusEl) statusEl.textContent = msg;
          return;
        }
        if (statusEl) statusEl.textContent = "Resolve with AI is running…";
        try {
          await applyKnowledge("Applying knowledge…");
          const res = await api(`/api/review/definition-query?job_id=${encodeURIComponent(state.jobId)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              logic_id: item.logic_id,
              term: current?.term || "",
              question,
              note,
            }),
          });
          if (res.provider === "ollama" && res.status === "completed") {
            if (statusEl) statusEl.textContent = res.result?.answer || "AI updated this knowledge item.";
            await renderLogicReview();
            return;
          }
          state.copilot.assistCommandId = res.command_id;
          state.copilot.assistCommand = res;
          refreshAssistContainers();
          await pollCopilotAssist(res.command_id, async () => {
            if (statusEl) statusEl.textContent = "AI updated this knowledge item.";
            await renderLogicReview();
          });
        } catch (e) {
          if (statusEl) statusEl.textContent = e.message;
        }
      };
    }
    bindWorkbookFocusEditor(logicRows, state.exportLanguage, "logic", renderLogicReview, "#logic-row-save-status");
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
    content().innerHTML = requireJobHtml();
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
        <button type="button" class="btn secondary btn-with-icon" id="btn-translate-workbook-jp" ${assistEnabled() ? "" : "disabled"} title="Experimental: translate all rows to Japanese via Ollama (slow)">${icon("translate", "alex-icon--btn")} Translate to Japanese</button>
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
  $("#export-draft-language").onchange = (e) => {
    state.exportLanguage = e.target.value;
    renderExport();
  };
  const translateBtn = $("#btn-translate-workbook-jp");
  if (translateBtn) {
    translateBtn.onclick = async () => {
      if (!assistEnabled()) {
        $("#export-status").textContent = "Enable Ollama in config to translate.";
        return;
      }
      translateBtn.disabled = true;
      $("#export-status").textContent = `Translating ${rows.length} row(s) to Japanese via Ollama…`;
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
}

async function renderGuide() {
  content().innerHTML = `<header class="page-header">
      <h2>How to review with ALEX</h2>
      <p class="lead">Work in this order — each step builds on traceable evidence from the spec.</p>
    </header>
    <section class="card">
      <h3>Recommended workflow</h3>
      <ol class="alex-guide-steps">
        <li><b>Review</b> — select files and run one analysis pass.</li>
        <li><b>Logic &amp; definitions</b> — confirm the logic tree, then resolve missing terms.</li>
        <li><b>Diagram graph</b> — validate states and transitions against source evidence.</li>
        <li><b>Final file</b> — edit workbook rows, switch EN/JP view, and export when ready.</li>
      </ol>
    </section>
    ${renderGuideCard()}`;
}

async function boot() {
  initNav();
  await loadAppConfig();
  startServiceStatusPolling();
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshServiceStatusNow();
  });
  setJobId(null);
  updateSelectedCount();
  await refreshJobSummary();
  showPage("review");
}

boot();
