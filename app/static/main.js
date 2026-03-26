import { request, requestForm } from "./api-client.js";
import { bindDashboardInteractions, renderProfileGrid } from "./dashboard.js";
import { createQueueController } from "./queue.js";
import { getProjectIdFromRoute, navigateToProject, syncProjectRoute } from "./router-state.js";
import { getState, setState } from "./state.js";
import { debounce, escapeHtml, getElement, normalizeSelectableValue, splitCsv } from "./ui-utils.js";
import { createVideoDetailController } from "./video-detail.js";
import { createAgentSettingsController } from "./agent-settings.js";
import { createKnowledgeSettingsController } from "./knowledge-settings.js";

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

function renderTokenList(type) {
  const tokenContainer = getElement(`${type}-tokens`);
  const hiddenInput = getElement(`${type}-hidden`);
  if (!tokenContainer || !hiddenInput) {
    return;
  }
  const values = getState().tokenInputs[type];

  tokenContainer.innerHTML = values
    .map(
      (value, index) =>
        `<span class="token">${escapeHtml(value)} <button data-type="${type}" data-index="${index}" type="button">x</button></span>`
    )
    .join("");
  hiddenInput.value = values.join(",");
}

function addToken(type, rawValue) {
  const normalized = normalizeSelectableValue(rawValue, type);
  const state = getState();
  if (!normalized || state.tokenInputs[type].includes(normalized)) {
    return;
  }

  setState((previous) => ({
    ...previous,
    tokenInputs: {
      ...previous.tokenInputs,
      [type]: [...previous.tokenInputs[type], normalized],
    },
  }));
  renderTokenList(type);
}

function removeToken(type, index) {
  setState((previous) => ({
    ...previous,
    tokenInputs: {
      ...previous.tokenInputs,
      [type]: previous.tokenInputs[type].filter((_, itemIndex) => itemIndex !== index),
    },
  }));
  renderTokenList(type);
}

function bindTokenInputs() {
  ["markets", "languages"].forEach((type) => {
    const input = getElement(`${type}-token-input`);
    const tokenContainer = getElement(`${type}-tokens`);
    if (!input || !tokenContainer) {
      return;
    }

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === ",") {
        event.preventDefault();
        addToken(type, input.value);
        input.value = "";
      }
    });

    input.addEventListener("blur", () => {
      addToken(type, input.value);
      input.value = "";
    });

    tokenContainer.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) {
        return;
      }
      const selectedType = target.getAttribute("data-type");
      const selectedIndex = Number(target.getAttribute("data-index"));
      if (!selectedType || Number.isNaN(selectedIndex)) {
        return;
      }
      removeToken(selectedType, selectedIndex);
    });

    renderTokenList(type);
  });
}

function bindDashboardControls() {
  const toggleButton = getElement("toggle-create-btn");
  if (toggleButton) {
    toggleButton.addEventListener("click", () => {
      const isHidden = getElement("create-profile-container")?.classList.contains("is-hidden");
      setCreatePanelVisible(Boolean(isHidden));
    });
  }

  const cancelButton = getElement("cancel-create-btn");
  if (cancelButton) {
    cancelButton.addEventListener("click", () => {
      setCreatePanelVisible(false);
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

    setState((previous) => ({
      ...previous,
      profiles,
      selectedProfileId,
      selectedVideoId: null,
      searchCandidates: [],
      selectedSearchVideoIds: [],
    }));

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
            alert_sensitivity: formData.get("alert_sensitivity"),
          }),
        });

        profileForm.reset();
        setState((previous) => ({
          ...previous,
          tokenInputs: {
            markets: [],
            languages: [],
          },
        }));
        renderTokenList("markets");
        renderTokenList("languages");
        setCreatePanelVisible(false);
        await loadProfiles();
      }, "Project created.");
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
  bindGlobalSearch();
  bindProjectBackButton();
  agentSettingsController.bindAgentSettingsControls();
  knowledgeSettingsController.bindKnowledgeSettingsControls();
  queueController.bindQueueInteractions();
  bindDashboardInteractions({
    onOpenProject: (profileId) => {
      const card = document.querySelector(`[data-project-id="${profileId}"]`);
      if (card instanceof HTMLElement) {
        card.classList.add("is-opening");
      }
      window.setTimeout(() => navigateToProject(profileId), 140);
    },
    onDeleteProject: (profileId) => {
      void runTask(async () => {
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
  const routeProjectId = getProjectIdFromRoute();
  setActiveSection(routeProjectId ? "queue" : "dashboard");

  await loadProfiles();
  await queueController.refreshVideos();
  await loadAlerts();
  await agentSettingsController.loadSettings();
  await knowledgeSettingsController.loadSettings();
}

bootstrap().catch((error) => {
  const message = error instanceof Error ? error.message : "Unexpected startup failure.";
  showMessage(message, "error");
});
