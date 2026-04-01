import { request, requestForm } from "./api-client.js";
import { bindDashboardInteractions, renderProfileGrid } from "./dashboard.js";
import { createQueueController } from "./queue.js";
import { getProjectIdFromRoute, navigateToProject, syncProjectRoute } from "./router-state.js";
import { getState, setState } from "./state.js";
import {
  debounce,
  escapeHtml,
  formatMarketLabel,
  formatLanguageLabel,
  getElement,
  normalizeSelectableValue,
  splitCsv,
} from "./ui-utils.js";
import { createVideoDetailController } from "./video-detail.js";
import { createAgentSettingsController } from "./agent-settings.js";
import { createKnowledgeSettingsController } from "./knowledge-settings.js";
import { createVocController } from "./voc.js";

let messageTimer = null;

function clearMessage() {
  const messageEl = getElement("app-message");
  if (!messageEl) {
    return;
  }
  messageEl.classList.add("is-hidden");
  messageEl.classList.remove("error", "success");
}

function showMessage(message, type = "info") {
  const messageEl = getElement("app-message");
  if (!messageEl) {
    window.alert(message);
    return;
  }

  if (messageTimer) {
    window.clearTimeout(messageTimer);
  }

  messageEl.classList.remove("is-hidden", "error", "success");
  if (type === "error" || type === "success") {
    messageEl.classList.add(type);
  }
  messageEl.textContent = message;

  messageTimer = window.setTimeout(() => {
    messageEl.classList.add("is-hidden");
  }, 3600);
}

async function runTask(task, successMessage = "") {
  try {
    clearMessage();
    await task();
    if (successMessage) {
      showMessage(successMessage, "success");
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Request failed";
    showMessage(message, "error");
  }
}

function setCreatePanelVisible(isVisible) {
  const container = getElement("create-profile-container");
  const toggleButton = getElement("toggle-create-btn");
  if (!container || !toggleButton) {
    return;
  }
  container.classList.toggle("is-hidden", !isVisible);
  toggleButton.textContent = isVisible ? "Hide Form" : "+ New Project";
}

function setEditPanelVisible(isVisible) {
  const container = getElement("edit-profile-container");
  if (!container) {
    return;
  }
  container.classList.toggle("is-hidden", !isVisible);
}

function setActiveSection(sectionId) {
  if (!sectionId) {
    return;
  }
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === sectionId);
  });
  document.querySelectorAll(".nav-btn[data-section]").forEach((button) => {
    button.classList.toggle("active", button.dataset.section === sectionId);
  });
}

function stateTokenKey(type) {
  return type === "key-products" ? "keyProducts" : type;
}

function renderTokenList(type, { prefix = "", stateBucket = "tokenInputs" } = {}) {
  const tokenContainer = getElement(`${prefix}${type}-tokens`);
  const hiddenInput = getElement(`${prefix}${type}-hidden`);
  if (!tokenContainer || !hiddenInput) {
    return;
  }
  const tokenKey = stateTokenKey(type);
  const state = getState();
  const values = state[stateBucket][tokenKey];

  tokenContainer.innerHTML = values
    .map(
      (value, index) => {
        const displayValue =
          tokenKey === "languages"
            ? formatLanguageLabel(value)
            : tokenKey === "markets"
              ? formatMarketLabel(value)
              : value;
        return `<span class="token">${escapeHtml(displayValue)} <button data-prefix="${prefix}" data-state-bucket="${stateBucket}" data-type="${type}" data-index="${index}" type="button">x</button></span>`;
      }
    )
    .join("");
  hiddenInput.value = values.join(",");
}

function addToken(type, rawValue, { stateBucket = "tokenInputs" } = {}) {
  const tokenKey = stateTokenKey(type);
  const normalized = normalizeSelectableValue(rawValue, tokenKey);
  const state = getState();
  if (!normalized || state[stateBucket][tokenKey].includes(normalized)) {
    return;
  }

  setState((previous) => ({
    ...previous,
    [stateBucket]: {
      ...previous[stateBucket],
      [tokenKey]: [...previous[stateBucket][tokenKey], normalized],
    },
  }));
}

function removeToken(type, index, { stateBucket = "tokenInputs" } = {}) {
  const tokenKey = stateTokenKey(type);
  setState((previous) => ({
    ...previous,
    [stateBucket]: {
      ...previous[stateBucket],
      [tokenKey]: previous[stateBucket][tokenKey].filter((_, itemIndex) => itemIndex !== index),
    },
  }));
}

function bindTokenInputs() {
  const groups = [
    { prefix: "", stateBucket: "tokenInputs" },
    { prefix: "edit-", stateBucket: "editTokenInputs" },
  ];
  const tokenTypes = ["markets", "languages", "key-products"];

  groups.forEach(({ prefix, stateBucket }) => {
    tokenTypes.forEach((type) => {
      const input = getElement(`${prefix}${type}-token-input`);
      const tokenContainer = getElement(`${prefix}${type}-tokens`);
      if (!input || !tokenContainer) {
        return;
      }

      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === ",") {
          event.preventDefault();
          addToken(type, input.value, { stateBucket });
          input.value = "";
          renderTokenList(type, { prefix, stateBucket });
        }
      });

      input.addEventListener("blur", () => {
        addToken(type, input.value, { stateBucket });
        input.value = "";
        renderTokenList(type, { prefix, stateBucket });
      });

      tokenContainer.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLButtonElement)) {
          return;
        }
        const selectedType = target.getAttribute("data-type");
        const selectedIndex = Number(target.getAttribute("data-index"));
        const selectedPrefix = target.getAttribute("data-prefix") || "";
        const selectedStateBucket = target.getAttribute("data-state-bucket") || "tokenInputs";
        if (!selectedType || Number.isNaN(selectedIndex)) {
          return;
        }
        removeToken(selectedType, selectedIndex, { stateBucket: selectedStateBucket });
        renderTokenList(selectedType, { prefix: selectedPrefix, stateBucket: selectedStateBucket });
      });

      renderTokenList(type, { prefix, stateBucket });
    });
  });
}

function bindDashboardControls() {
  const toggleButton = getElement("toggle-create-btn");
  if (toggleButton) {
    toggleButton.addEventListener("click", () => {
      const isHidden = getElement("create-profile-container")?.classList.contains("is-hidden");
      if (isHidden) {
        setEditPanelVisible(false);
      }
      setCreatePanelVisible(Boolean(isHidden));
    });
  }

  const cancelButton = getElement("cancel-create-btn");
  if (cancelButton) {
    cancelButton.addEventListener("click", () => {
      setCreatePanelVisible(false);
    });
  }

  const cancelEditButton = getElement("cancel-edit-btn");
  if (cancelEditButton) {
    cancelEditButton.addEventListener("click", () => {
      setState((previous) => ({
        ...previous,
        editingProjectId: null,
      }));
      setEditPanelVisible(false);
    });
  }
}

async function loadAlerts() {
  const list = getElement("alerts-list");
  if (!list) {
    return;
  }

  const data = await request("/alerts");
  const alerts = Array.isArray(data.items) ? data.items : [];
  if (alerts.length === 0) {
    list.innerHTML = '<li class="meta">No active alerts.</li>';
    return;
  }

  list.innerHTML = alerts
    .map(
      (alert) => `
        <li class="alert-item">
          <div style="font-weight: 600;">${escapeHtml(alert.message)}</div>
          <div class="meta">Channel: ${escapeHtml(alert.channel)}</div>
        </li>
      `
    )
    .join("");
}

function bindAlertsControls() {
  const refreshAlertsButton = getElement("refresh-alerts-btn");
  if (!refreshAlertsButton) {
    return;
  }
  refreshAlertsButton.addEventListener("click", () => {
    void runTask(async () => {
      await loadAlerts();
    });
  });
}

function bindNav() {
  const buttons = Array.from(document.querySelectorAll(".nav-btn[data-section]"));
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const sectionId = button.dataset.section;
      if (!sectionId) {
        return;
      }
      if (sectionId === "dashboard") {
        syncProjectRoute(null);
      }
      setActiveSection(sectionId);
    });
  });
}

function bindProjectBackButton() {
  const backButton = getElement("back-to-dashboard-btn");
  if (!backButton) {
    return;
  }

  backButton.addEventListener("click", () => {
    syncProjectRoute(null);
    setActiveSection("dashboard");
    window.location.assign("/");
  });
}

async function bootstrap() {
  let queueController = null;
  const agentSettingsController = createAgentSettingsController({
    request,
    runTask,
  });
  const knowledgeSettingsController = createKnowledgeSettingsController({
    request,
    requestForm,
    runTask,
    getState,
  });
  const vocController = createVocController({
    request,
    requestForm,
    runTask,
  });

  const videoDetailController = createVideoDetailController({
    getState,
    setState,
    request,
    runTask,
    onVideosChanged: async () => {
      if (queueController) {
        await queueController.refreshVideos();
      }
    },
    onAlertsChanged: loadAlerts,
  });

  function rerenderProfileArea() {
    const state = getState();
    renderProfileGrid({
      profiles: state.profiles,
      selectedProfileId: state.selectedProfileId,
      openProjectMenuId: state.openProjectMenuId,
    });
    if (queueController) {
      queueController.renderProfileSelect();
    }
    knowledgeSettingsController.syncProjectSelection();
  }

  queueController = createQueueController({
    getState,
    setState,
    request,
    runTask,
    videoDetailController,
    onProfileSelectionChange: rerenderProfileArea,
  });

  async function loadProfiles() {
    const profiles = await request("/monitor-profiles");
    const routeProjectId = getProjectIdFromRoute();
    const hasRouteProject = routeProjectId !== null && profiles.some((profile) => profile.id === routeProjectId);
    const selectedProfileId = hasRouteProject ? routeProjectId : null;
    const state = getState();
    const hasOpenMenuProfile = profiles.some((profile) => profile.id === state.openProjectMenuId);
    const hasEditingProfile = profiles.some((profile) => profile.id === state.editingProjectId);

    setState((previous) => ({
      ...previous,
      profiles,
      selectedProfileId,
      selectedVideoId: null,
      searchCandidates: [],
      openProjectMenuId: hasOpenMenuProfile ? previous.openProjectMenuId : null,
      editingProjectId: hasEditingProfile ? previous.editingProjectId : null,
    }));
    if (!hasEditingProfile) {
      setEditPanelVisible(false);
    }

    if (routeProjectId !== null && !hasRouteProject) {
      showMessage("Project route not found. Showing dashboard view instead.", "error");
      syncProjectRoute(null);
      setActiveSection("dashboard");
    }

    rerenderProfileArea();
    queueController.renderSearchCandidates();
  }

  function bindProfileForm() {
    const profileForm = getElement("profile-form");
    if (!profileForm) {
      return;
    }
    profileForm.addEventListener("submit", (event) => {
      event.preventDefault();
      void runTask(async () => {
        const state = getState();
        if (state.tokenInputs.markets.length === 0) {
          throw new Error("Please add at least one market.");
        }
        if (state.tokenInputs.languages.length === 0) {
          throw new Error("Please add at least one language.");
        }

        const formData = new FormData(profileForm);
        const projectName = String(formData.get("name") || "").trim();
        const brandKeywords = splitCsv(formData.get("brand_keywords"));
        if (!projectName || brandKeywords.length === 0) {
          throw new Error("Project name and brand keywords are required.");
        }

        await request("/monitor-profiles", {
          method: "POST",
          body: JSON.stringify({
            name: projectName,
            brand_keywords: brandKeywords,
            markets: [...state.tokenInputs.markets],
            languages: [...state.tokenInputs.languages],
            key_products: [...state.tokenInputs.keyProducts],
            alert_sensitivity: formData.get("alert_sensitivity"),
          }),
        });

        profileForm.reset();
        setState((previous) => ({
          ...previous,
          tokenInputs: {
            markets: [],
            languages: [],
            keyProducts: [],
          },
        }));
        renderTokenList("markets", { prefix: "", stateBucket: "tokenInputs" });
        renderTokenList("languages", { prefix: "", stateBucket: "tokenInputs" });
        renderTokenList("key-products", { prefix: "", stateBucket: "tokenInputs" });
        setCreatePanelVisible(false);
        await loadProfiles();
      }, "Project created.");
    });
  }

  function openEditProject(profileId) {
    const state = getState();
    const profile = state.profiles.find((item) => item.id === profileId);
    if (!profile) {
      showMessage("Project not found.", "error");
      return;
    }

    const editForm = getElement("edit-profile-form");
    if (!(editForm instanceof HTMLFormElement)) {
      return;
    }
    const nameInput = getElement("edit-profile-name");
    const brandKeywordsInput = getElement("edit-profile-brand-keywords");
    const profileIdInput = getElement("edit-profile-id");
    const alertSensitivitySelect = getElement("edit-alert-sensitivity");
    if (!(nameInput instanceof HTMLInputElement) || !(brandKeywordsInput instanceof HTMLInputElement)) {
      return;
    }
    if (!(profileIdInput instanceof HTMLInputElement) || !(alertSensitivitySelect instanceof HTMLSelectElement)) {
      return;
    }

    nameInput.value = profile.name;
    brandKeywordsInput.value = profile.brand_keywords.join(", ");
    profileIdInput.value = String(profile.id);
    alertSensitivitySelect.value = profile.alert_sensitivity || "medium";

    setState((previous) => ({
      ...previous,
      editingProjectId: profileId,
      openProjectMenuId: null,
      editTokenInputs: {
        markets: [...profile.markets],
        languages: [...profile.languages],
        keyProducts: [...(profile.key_products || [])],
      },
    }));
    renderTokenList("markets", { prefix: "edit-", stateBucket: "editTokenInputs" });
    renderTokenList("languages", { prefix: "edit-", stateBucket: "editTokenInputs" });
    renderTokenList("key-products", { prefix: "edit-", stateBucket: "editTokenInputs" });
    setCreatePanelVisible(false);
    setEditPanelVisible(true);
    rerenderProfileArea();
  }

  function bindEditProfileForm() {
    const editForm = getElement("edit-profile-form");
    if (!(editForm instanceof HTMLFormElement)) {
      return;
    }
    editForm.addEventListener("submit", (event) => {
      event.preventDefault();
      void runTask(async () => {
        const state = getState();
        if (state.editTokenInputs.markets.length === 0) {
          throw new Error("Please add at least one market.");
        }
        if (state.editTokenInputs.languages.length === 0) {
          throw new Error("Please add at least one language.");
        }

        const formData = new FormData(editForm);
        const profileId = Number(formData.get("profile_id"));
        if (Number.isNaN(profileId)) {
          throw new Error("Invalid project.");
        }
        const projectName = String(formData.get("name") || "").trim();
        const brandKeywords = splitCsv(formData.get("brand_keywords"));
        if (!projectName || brandKeywords.length === 0) {
          throw new Error("Project name and brand keywords are required.");
        }

        await request(`/monitor-profiles/${profileId}`, {
          method: "PUT",
          body: JSON.stringify({
            name: projectName,
            brand_keywords: brandKeywords,
            markets: [...state.editTokenInputs.markets],
            languages: [...state.editTokenInputs.languages],
            key_products: [...state.editTokenInputs.keyProducts],
            alert_sensitivity: formData.get("alert_sensitivity"),
          }),
        });

        setState((previous) => ({
          ...previous,
          editingProjectId: null,
          editTokenInputs: {
            markets: [],
            languages: [],
            keyProducts: [],
          },
        }));
        setEditPanelVisible(false);
        await loadProfiles();
        await queueController.refreshVideos();
      }, "Project updated.");
    });
  }

  function bindGlobalSearch() {
    const input = getElement("global-search-input");
    const titleFilter = getElement("title-filter");
    if (!input || !titleFilter) {
      return;
    }

    const propagateSearch = debounce(() => {
      const value = input.value.trim();
      titleFilter.value = value;
      setActiveSection("queue");
      void runTask(async () => {
        await queueController.refreshVideos();
      });
    }, 280);

    input.addEventListener("input", () => {
      propagateSearch();
    });
  }

  bindNav();
  bindDashboardControls();
  bindTokenInputs();
  bindAlertsControls();
  bindProfileForm();
  bindEditProfileForm();
  bindGlobalSearch();
  bindProjectBackButton();
  agentSettingsController.bindAgentSettingsControls();
  knowledgeSettingsController.bindKnowledgeSettingsControls();
  vocController.bindVocControls();
  queueController.bindQueueInteractions();
  bindDashboardInteractions({
    onOpenProject: (profileId) => {
      const card = document.querySelector(`[data-project-id="${profileId}"]`);
      if (card instanceof HTMLElement) {
        card.classList.add("is-opening");
      }
      window.setTimeout(() => navigateToProject(profileId), 140);
    },
    onEditProject: (profileId) => {
      openEditProject(profileId);
    },
    onToggleProjectMenu: (profileId) => {
      setState((previous) => ({
        ...previous,
        openProjectMenuId: previous.openProjectMenuId === profileId ? null : profileId,
      }));
      rerenderProfileArea();
    },
    onCloseProjectMenu: () => {
      if (getState().openProjectMenuId === null) {
        return;
      }
      setState((previous) => ({
        ...previous,
        openProjectMenuId: null,
      }));
      rerenderProfileArea();
    },
    onDeleteProject: (profileId) => {
      void runTask(async () => {
        setState((previous) => ({
          ...previous,
          openProjectMenuId: null,
        }));
        rerenderProfileArea();
        await request(`/monitor-profiles/${profileId}`, { method: "DELETE" });
        const state = getState();
        const isDeletedProjectSelected = state.selectedProfileId === profileId;
        if (isDeletedProjectSelected) {
          setState((previous) => ({
            ...previous,
            selectedProfileId: null,
            selectedVideoId: null,
          }));
          syncProjectRoute(null);
        }
        await loadProfiles();
        await queueController.refreshVideos();
      }, "Project deleted.");
    },
  });

  setCreatePanelVisible(false);
  setEditPanelVisible(false);
  const routeProjectId = getProjectIdFromRoute();
  setActiveSection(routeProjectId ? "queue" : "dashboard");

  await loadProfiles();
  await queueController.refreshVideos();
  await loadAlerts();
  await agentSettingsController.loadSettings();
  await knowledgeSettingsController.loadSettings();
  await vocController.loadProjects();
  await vocController.loadSettings();
}

bootstrap().catch((error) => {
  const message = error instanceof Error ? error.message : "Unexpected startup failure.";
  showMessage(message, "error");
});
