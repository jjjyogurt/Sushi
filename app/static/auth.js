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

export function createAuthController({ request, setState }) {
  let users = [];
  let currentUser = null;
  let waitingResolver = null;
  let formBound = false;
  let selectorDefaultPassword = "";

  function syncLoginInputsFromSelection() {
    const userSelect = getElement("auth-user-select");
    const userIdInput = getElement("auth-user-id");
    const passwordInput = getElement("auth-password");
    if (!(userSelect instanceof HTMLSelectElement)) {
      return;
    }
    const selectedUserId = String(userSelect.value || "").trim();
    if (!selectedUserId) {
      return;
    }
    if (userIdInput instanceof HTMLInputElement) {
      userIdInput.value = selectedUserId;
    }
    if (passwordInput instanceof HTMLInputElement) {
      if (!selectorDefaultPassword) {
        selectorDefaultPassword = passwordInput.value || "1234";
      }
      passwordInput.value = selectorDefaultPassword;
    }
  }

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
    const selectWrap = getElement("auth-user-select-wrap");
    const idWrap = getElement("auth-user-id-wrap");
    const select = getElement("auth-user-select");
    const idInput = getElement("auth-user-id");
    try {
      const payload = await request("/auth/users");
      users = Array.isArray(payload) ? payload : [];
      if (idWrap) {
        idWrap.classList.add("is-hidden");
      }
      if (selectWrap) {
        selectWrap.classList.remove("is-hidden");
      }
      if (idInput instanceof HTMLInputElement) {
        idInput.value = "";
      }
      if (!(select instanceof HTMLSelectElement)) {
        return;
      }
      select.innerHTML = users
        .map((user) => `<option value="${user.user_id}">${user.display_name}</option>`)
        .join("");
      if (users.length > 0) {
        select.value = users[0].user_id;
      }
      syncLoginInputsFromSelection();
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        users = [];
        if (selectWrap) {
          selectWrap.classList.add("is-hidden");
        }
        if (idWrap) {
          idWrap.classList.remove("is-hidden");
        }
        if (select instanceof HTMLSelectElement) {
          select.innerHTML = "";
        }
        if (idInput instanceof HTMLInputElement) {
          idInput.value = "";
          idInput.focus();
        }
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
    const userSelect = getElement("auth-user-select");
    const idWrap = getElement("auth-user-id-wrap");
    const userIdInput = getElement("auth-user-id");
    const passwordInput = getElement("auth-password");
    const submitButton = getElement("auth-login-submit");
    const usingManualId = idWrap instanceof HTMLElement && !idWrap.classList.contains("is-hidden");
    if (!(passwordInput instanceof HTMLInputElement)) {
      return;
    }
    if (!usingManualId && !(userSelect instanceof HTMLSelectElement)) {
      return;
    }
    if (usingManualId && !(userIdInput instanceof HTMLInputElement)) {
      return;
    }
    const userId = usingManualId
      ? userIdInput instanceof HTMLInputElement
        ? userIdInput.value.trim()
        : ""
      : userSelect instanceof HTMLSelectElement
        ? userSelect.value
        : "";
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
    const userSelect = getElement("auth-user-select");
    if (userSelect instanceof HTMLSelectElement) {
      userSelect.addEventListener("change", () => {
        syncLoginInputsFromSelection();
      });
    }
  }

  async function waitForLogin() {
    setAuthGateVisible(true);
    syncLoginInputsFromSelection();
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
