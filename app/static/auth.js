import { ApiError } from "./api-client.js";
import { getElement } from "./ui-utils.js";
import { t } from "./i18n.js";

function setAuthError(message) {
  const errorEl = getElement("auth-error");
  if (!errorEl) {
    return;
  }
  errorEl.textContent = message;
}

function setAuthGateVisible(isVisible) {
  const gate = getElement("auth-gate");
  if (!gate) {
    return;
  }
  gate.classList.toggle("is-hidden", !isVisible);
}

function playSignedInSushiAnimation() {
  const sushiMark = document.querySelector(".topbar-sushi-mark");
  if (!(sushiMark instanceof HTMLElement)) {
    return;
  }
  sushiMark.classList.remove("is-animating");
  void sushiMark.offsetWidth;
  sushiMark.classList.add("is-animating");
  window.setTimeout(() => {
    sushiMark.classList.remove("is-animating");
  }, 1400);
}

export function createAuthController({ request, setState }) {
  let users = [];
  let currentUser = null;
  let waitingResolver = null;
  let formBound = false;

  function syncCurrentUserLabels() {
    const userLabel = currentUser?.display_name || t("accountNotSignedIn");
    const topbarLabel = getElement("topbar-user-label");
    if (topbarLabel) {
      topbarLabel.textContent = userLabel;
    }
    const settingsMeta = getElement("account-settings-meta");
    if (settingsMeta) {
      settingsMeta.textContent = currentUser
        ? t("accountSignedInAs", { user: currentUser.display_name })
        : t("accountNotSignedIn");
    }
  }

  async function loadUsers() {
    try {
      const payload = await request("/auth/users");
      users = Array.isArray(payload) ? payload : [];
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        users = [];
        return;
      }
      throw error;
    }
  }

  function setCurrentUser(user) {
    currentUser = user || null;
    setState((previous) => ({
      ...previous,
      currentUser,
      appUsers: users,
    }));
    syncCurrentUserLabels();
  }

  async function submitLogin() {
    const userIdInput = getElement("auth-user-id");
    const passwordInput = getElement("auth-password");
    const submitButton = getElement("auth-login-submit");
    if (!(userIdInput instanceof HTMLInputElement) || !(passwordInput instanceof HTMLInputElement)) {
      return;
    }
    const userId = userIdInput.value.trim();
    if (!userId) {
      setAuthError(t("loginFailed"));
      return;
    }
    if (submitButton instanceof HTMLButtonElement) {
      submitButton.disabled = true;
    }
    setAuthError("");
    try {
      const payload = await request("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          user_id: userId,
          password: passwordInput.value,
        }),
      });
      const currentUser = payload?.user || null;
      if (!currentUser) {
        throw new Error(t("loginFailed"));
      }
      passwordInput.value = "";
      setCurrentUser(currentUser);
      setAuthGateVisible(false);
      playSignedInSushiAnimation();
      if (waitingResolver) {
        waitingResolver(currentUser);
        waitingResolver = null;
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : t("loginFailed");
      setAuthError(message);
    } finally {
      if (submitButton instanceof HTMLButtonElement) {
        submitButton.disabled = false;
      }
    }
  }

  function bindLoginForm() {
    if (formBound) {
      return;
    }
    const form = getElement("auth-login-form");
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    formBound = true;
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      void submitLogin();
    });
  }

  async function waitForLogin() {
    setAuthGateVisible(true);
    return new Promise((resolve) => {
      waitingResolver = resolve;
    });
  }

  async function ensureAuthenticated() {
    await loadUsers();
    bindLoginForm();
    while (true) {
      try {
        const payload = await request("/auth/me");
        const currentUser = payload?.user || null;
        if (!currentUser) {
          throw new Error(t("authSessionInvalid"));
        }
        setCurrentUser(currentUser);
        setAuthGateVisible(false);
        return currentUser;
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          await waitForLogin();
          continue;
        }
        throw error;
      }
    }
  }

  function bindLogoutButtons() {
    const logoutButtons = [getElement("topbar-logout-btn"), getElement("settings-logout-btn")];
    logoutButtons.forEach((button) => {
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      button.addEventListener("click", () => {
        button.disabled = true;
        void request("/auth/logout", { method: "POST" })
          .catch(() => null)
          .finally(() => {
            window.location.assign("/");
          });
      });
    });
  }

  return {
    ensureAuthenticated,
    bindLogoutButtons,
  };
}
