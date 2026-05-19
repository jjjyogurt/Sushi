import { escapeHtml, formatLanguageLabel, formatMarketLabel, getElement } from "./ui-utils.js";
import { iconSvg } from "./icons.js";
import { t } from "./i18n.js";

const MONITORING_CADENCES = ["daily", "weekly", "monthly"];

function profileCardMarkup(profile, isSelected, openProjectMenuId) {
  const isMenuOpen = openProjectMenuId === profile.id;
  const keyProducts = Array.isArray(profile.key_products) ? profile.key_products : [];
  const monitoringEnabled = Boolean(profile.proactive_monitoring_enabled);
  const unseenCount = Number(profile.unseen_monitoring_update_count || 0);
  const cadence = MONITORING_CADENCES.includes(profile.proactive_monitoring_cadence)
    ? profile.proactive_monitoring_cadence
    : "daily";
  const cadenceOptions = MONITORING_CADENCES.map(
    (item) => `<option value="${item}" ${item === cadence ? "selected" : ""}>${escapeHtml(t(`monitoringCadence${item}`))}</option>`
  ).join("");
  const editingMarkup = isSelected
    ? `
      <div class="project-card-edit-slot" data-project-card-edit-slot-id="${profile.id}"></div>
    `
    : "";
  return `
    <article class="project-card ${isSelected ? "active" : ""}" data-project-id="${profile.id}">
      <div class="project-card-header">
        <h4>
          ${unseenCount > 0 ? `<span class="project-update-dot" aria-label="${escapeHtml(t("newMonitoringUpdates"))}"></span>` : ""}
          ${escapeHtml(profile.name)}
        </h4>
        <div class="project-card-actions">
          <button
            class="icon-btn project-menu-btn"
            data-project-menu-toggle-id="${profile.id}"
            type="button"
            aria-label="${escapeHtml(t("projectActions"))}"
            aria-haspopup="menu"
            aria-expanded="${isMenuOpen ? "true" : "false"}"
          >
            ${iconSvg("more_vert")}
          </button>
          <div class="project-card-menu ${isMenuOpen ? "is-open" : ""}" data-project-menu-id="${profile.id}">
            <button class="dropdown-item" type="button" data-edit-project-id="${profile.id}">${escapeHtml(
              t("editProject")
            )}</button>
            <button class="dropdown-item text-danger" type="button" data-delete-project-id="${profile.id}">
              ${escapeHtml(t("deleteProject"))}
            </button>
          </div>
        </div>
      </div>
      <div class="meta">${escapeHtml(t("projectKeywords"))}: ${escapeHtml(profile.brand_keywords.join(", "))}</div>
      ${
        keyProducts.length > 0
          ? `<div class="meta">${escapeHtml(t("projectKeyProducts"))}: ${escapeHtml(keyProducts.join(", "))}</div>`
          : ""
      }
      <div class="chip-row">
        ${profile.markets.map((market) => `<span class="badge">${escapeHtml(formatMarketLabel(market))}</span>`).join("")}
      </div>
      <div class="chip-row">
        ${profile.languages
          .map((language) => `<span class="badge">${escapeHtml(formatLanguageLabel(language))}</span>`)
          .join("")}
      </div>
      <label class="monitoring-toggle-row" data-monitoring-toggle-wrap-id="${profile.id}">
        <span class="monitoring-toggle-title">${escapeHtml(t("proactiveMonitoring"))}</span>
        <select
          class="monitoring-cadence-select ${monitoringEnabled ? "" : "is-hidden"}"
          data-monitoring-cadence-id="${profile.id}"
          aria-label="${escapeHtml(t("monitoringFrequency"))}"
        >
          ${cadenceOptions}
        </select>
        <span class="monitoring-toggle-control">
          <input
            type="checkbox"
            data-monitoring-toggle-id="${profile.id}"
            ${monitoringEnabled ? "checked" : ""}
            aria-label="${escapeHtml(t("proactiveMonitoring"))}"
          />
          <span class="monitoring-toggle-track" aria-hidden="true"></span>
        </span>
      </label>
      ${editingMarkup}
      <button class="open-project-btn btn btn-secondary" type="button" data-open-project-id="${profile.id}">
        ${escapeHtml(t("openProject"))}
      </button>
    </article>
  `;
}

export function renderProfileGrid({ profiles, selectedProfileId, openProjectMenuId = null }) {
  const profileGrid = getElement("profile-grid");
  if (!profileGrid) {
    return;
  }

  if (profiles.length === 0) {
    profileGrid.innerHTML = `<div class="video-detail-empty">${escapeHtml(t("noProjectsYet"))}</div>`;
    return;
  }

  profileGrid.innerHTML = profiles
    .map((profile) => profileCardMarkup(profile, profile.id === selectedProfileId, openProjectMenuId))
    .join("");
}

export function bindDashboardInteractions({
  onOpenProject,
  onDeleteProject,
  onEditProject,
  onToggleProjectMenu,
  onCloseProjectMenu,
  onToggleMonitoring,
  onChangeMonitoringCadence,
}) {
  const profileGrid = getElement("profile-grid");
  if (!profileGrid) {
    return;
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    if (!target.closest("#profile-grid")) {
      onCloseProjectMenu();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      onCloseProjectMenu();
    }
  });

  profileGrid.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }

    const menuToggle = target.closest("[data-project-menu-toggle-id]");
    if (menuToggle instanceof HTMLElement) {
      event.preventDefault();
      event.stopPropagation();
      const profileId = Number(menuToggle.dataset.projectMenuToggleId);
      if (!Number.isNaN(profileId)) {
        onToggleProjectMenu(profileId);
      }
      return;
    }

    const monitoringToggle = target.closest("[data-monitoring-toggle-id]");
    if (monitoringToggle instanceof HTMLInputElement) {
      event.stopPropagation();
      const profileId = Number(monitoringToggle.dataset.monitoringToggleId);
      if (!Number.isNaN(profileId)) {
        onToggleMonitoring(profileId, monitoringToggle.checked);
      }
      return;
    }

    const cadenceSelect = target.closest("[data-monitoring-cadence-id]");
    if (cadenceSelect instanceof HTMLSelectElement) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }

    const monitoringRow = target.closest("[data-monitoring-toggle-wrap-id]");
    if (monitoringRow instanceof HTMLElement) {
      event.preventDefault();
      event.stopPropagation();
      const profileId = Number(monitoringRow.dataset.monitoringToggleWrapId);
      const checkbox = monitoringRow.querySelector("[data-monitoring-toggle-id]");
      if (checkbox instanceof HTMLInputElement && !Number.isNaN(profileId)) {
        checkbox.checked = !checkbox.checked;
        onToggleMonitoring(profileId, checkbox.checked);
      }
      return;
    }

    const editButton = target.closest("[data-edit-project-id]");
    if (editButton instanceof HTMLElement) {
      event.preventDefault();
      event.stopPropagation();
      const profileId = Number(editButton.dataset.editProjectId);
      if (!Number.isNaN(profileId)) {
        onEditProject(profileId);
      }
      return;
    }

    const deleteButton = target.closest("[data-delete-project-id]");
    if (deleteButton instanceof HTMLElement) {
      event.preventDefault();
      event.stopPropagation();
      const profileId = Number(deleteButton.dataset.deleteProjectId);
      if (!Number.isNaN(profileId)) {
        onDeleteProject(profileId);
      }
      return;
    }

    const openButton = target.closest("[data-open-project-id]");
    if (openButton instanceof HTMLElement) {
      const profileId = Number(openButton.dataset.openProjectId);
      if (!Number.isNaN(profileId)) {
        onOpenProject(profileId);
      }
      return;
    }

    const card = target.closest("[data-project-id]");
    if (card instanceof HTMLElement) {
      if (target.closest("[data-project-menu-id]")) {
        return;
      }
      const profileId = Number(card.dataset.projectId);
      if (!Number.isNaN(profileId)) {
        onOpenProject(profileId);
      }
    }
  });

  profileGrid.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    const cadenceSelect = target.closest("[data-monitoring-cadence-id]");
    if (cadenceSelect instanceof HTMLSelectElement) {
      event.stopPropagation();
      const profileId = Number(cadenceSelect.dataset.monitoringCadenceId);
      if (!Number.isNaN(profileId)) {
        onChangeMonitoringCadence(profileId, cadenceSelect.value);
      }
    }
  });
}
