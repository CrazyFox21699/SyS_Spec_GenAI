(function () {
  const LOGIN_USERNAME_KEY = "alex.login.username";
  const LOGIN_REMEMBER_KEY = "alex.login.remember";
  const SPLASH_MS = 1600;
  const SPLASH_LEAVE_MS = 280;

  const loginForm = document.getElementById("login-form");
  const loginShell = document.getElementById("login-shell");
  const splash = document.getElementById("welcome-splash");
  const errorEl = document.getElementById("login-error");
  const forgot = document.getElementById("login-forgot");
  const usernameInput = document.getElementById("login-username");
  const rememberInput = document.getElementById("login-remember");

  function showError(message) {
    if (!errorEl) return;
    errorEl.textContent = message || "Sign in failed.";
    errorEl.hidden = !message;
  }

  function restoreLoginPrefs() {
    try {
      const savedUser = localStorage.getItem(LOGIN_USERNAME_KEY);
      if (savedUser && usernameInput) usernameInput.value = savedUser;
      const savedRemember = localStorage.getItem(LOGIN_REMEMBER_KEY);
      if (rememberInput && savedRemember != null) {
        rememberInput.checked = savedRemember !== "0";
      }
    } catch (_) {
      /* ignore */
    }
  }

  async function isAlreadySignedIn() {
    try {
      const res = await fetch("/api/auth/me", { credentials: "same-origin" });
      if (!res.ok) return false;
      const data = await res.json();
      return data.enabled === false || Boolean(data.username);
    } catch (_) {
      return false;
    }
  }

  function hideSplash() {
    if (!splash) return;
    splash.classList.add("is-leaving");
    window.setTimeout(() => {
      splash.classList.add("is-hidden");
      splash.setAttribute("aria-hidden", "true");
    }, SPLASH_LEAVE_MS);
  }

  function showLoginShell() {
    if (loginShell) loginShell.hidden = false;
  }

  async function runSplashThenLogin() {
    await new Promise((resolve) => window.setTimeout(resolve, SPLASH_MS));
    hideSplash();
    showLoginShell();
  }

  if (forgot) {
    forgot.addEventListener("click", (event) => {
      event.preventDefault();
      showError("Contact your IT administrator to reset your password.");
    });
  }

  loginForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    showError("");
    const username = usernameInput?.value?.trim() || "";
    const password = document.getElementById("login-password")?.value || "";
    const remember = rememberInput?.checked ?? true;
    const submit = document.getElementById("login-submit");
    if (submit) submit.disabled = true;
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, remember }),
      });
      if (!res.ok) {
        let detail = "Invalid username or password.";
        try {
          const body = await res.json();
          detail = body.detail || detail;
        } catch (_) {
          /* ignore */
        }
        showError(detail);
        return;
      }
      try {
        localStorage.setItem(LOGIN_USERNAME_KEY, username);
        localStorage.setItem(LOGIN_REMEMBER_KEY, remember ? "1" : "0");
      } catch (_) {
        /* ignore */
      }
      window.location.href = "/";
    } catch (_) {
      showError("Unable to reach the server.");
    } finally {
      if (submit) submit.disabled = false;
    }
  });

  async function boot() {
    if (await isAlreadySignedIn()) {
      window.location.href = "/";
      return;
    }
    restoreLoginPrefs();
    await runSplashThenLogin();
  }

  boot();
})();
