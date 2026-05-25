(function () {
  const root = document.getElementById("admin-root");

  function esc(text) {
    return String(text ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, { ...opts, credentials: "same-origin" });
    if (res.status === 401) {
      window.location.href = "/login";
      throw new Error("Not authenticated");
    }
    if (res.status === 403) {
      throw new Error("Admin access required.");
    }
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail || detail;
      } catch (_) {
        /* ignore */
      }
      throw new Error(detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function ensureAdmin() {
    const me = await api("/api/auth/me");
    if (!me.enabled || me.role !== "admin") {
      root.innerHTML = `<p class="detail" style="color:var(--red)">Admin access required.</p>`;
      throw new Error("Not admin");
    }
    return me;
  }

  async function renderUsers() {
    const data = await api("/api/admin/users");
    const users = data.users || [];
    const rows = users
      .map(
        (u) => `<tr>
          <td><code>${esc(u.username)}</code></td>
          <td>${esc(u.role)}</td>
          <td><span class="tag ${u.is_active ? "high" : "error"}">${u.is_active ? "active" : "disabled"}</span></td>
          <td class="detail">${esc(u.created_at || "")}</td>
          <td class="team-actions">
            <button type="button" class="btn secondary btn-xs" data-team-reset="${esc(u.username)}">Reset password</button>
            <button type="button" class="btn secondary btn-xs" data-team-toggle="${esc(u.username)}" data-active="${u.is_active ? "1" : "0"}">${u.is_active ? "Disable" : "Enable"}</button>
          </td>
        </tr>`
      )
      .join("");

    root.innerHTML = `
      <section class="card team-create-card">
        <h3>Create user</h3>
        <div class="team-create-grid">
          <label class="detail">Username
            <input id="team-new-username" class="clarify-box" placeholder="alice" autocomplete="off" />
          </label>
          <label class="detail">Password
            <input id="team-new-password" class="clarify-box" type="password" placeholder="min 8 characters" autocomplete="new-password" />
          </label>
          <label class="detail">Role
            <select id="team-new-role" class="clarify-box">
              <option value="engineer">Engineer</option>
              <option value="admin">Admin</option>
            </select>
          </label>
          <button type="button" class="btn" id="btn-team-create">Create account</button>
        </div>
        <p id="team-create-status" class="detail"></p>
      </section>
      <section class="card" style="margin-top:1rem">
        <h3>Users (${users.length})</h3>
        <div class="grid-wrap">
          <table class="data-grid alex-table team-users-table">
            <thead><tr><th>Username</th><th>Role</th><th>Status</th><th>Created</th><th>Actions</th></tr></thead>
            <tbody>${rows || `<tr><td colspan="5" class="detail">No users yet.</td></tr>`}</tbody>
          </table>
        </div>
        <p id="team-admin-status" class="detail"></p>
      </section>`;

    document.getElementById("btn-team-create").onclick = async () => {
      const statusEl = document.getElementById("team-create-status");
      const username = document.getElementById("team-new-username")?.value?.trim() || "";
      const password = document.getElementById("team-new-password")?.value || "";
      const role = document.getElementById("team-new-role")?.value || "engineer";
      if (!username || !password) {
        statusEl.textContent = "Username and password are required.";
        return;
      }
      statusEl.textContent = "Creating…";
      try {
        await api("/api/admin/users", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password, role }),
        });
        statusEl.textContent = `Created ${username}.`;
        await renderUsers();
      } catch (e) {
        statusEl.textContent = e.message;
      }
    };

    root.querySelectorAll("[data-team-reset]").forEach((btn) => {
      btn.onclick = async () => {
        const username = btn.getAttribute("data-team-reset");
        const newPassword = window.prompt(`New password for ${username} (min 8 chars):`);
        if (!newPassword) return;
        const statusEl = document.getElementById("team-admin-status");
        statusEl.textContent = "Resetting…";
        try {
          await api(`/api/admin/users/${encodeURIComponent(username)}/reset-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ new_password: newPassword }),
          });
          statusEl.textContent = `Password reset for ${username}.`;
        } catch (e) {
          statusEl.textContent = e.message;
        }
      };
    });

    root.querySelectorAll("[data-team-toggle]").forEach((btn) => {
      btn.onclick = async () => {
        const username = btn.getAttribute("data-team-toggle");
        const active = btn.getAttribute("data-active") !== "1";
        const statusEl = document.getElementById("team-admin-status");
        statusEl.textContent = active ? "Enabling…" : "Disabling…";
        try {
          await api(`/api/admin/users/${encodeURIComponent(username)}/active`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ active }),
          });
          await renderUsers();
        } catch (e) {
          statusEl.textContent = e.message;
        }
      };
    });
  }

  document.getElementById("btn-admin-sign-out")?.addEventListener("click", async () => {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch (_) {
      /* ignore */
    }
    window.location.href = "/login";
  });

  (async () => {
    try {
      await ensureAdmin();
      await renderUsers();
    } catch (e) {
      if (root.textContent === "Loading…") {
        root.innerHTML = `<p class="detail" style="color:var(--red)">${esc(e.message)}</p>`;
      }
    }
  })();
})();
