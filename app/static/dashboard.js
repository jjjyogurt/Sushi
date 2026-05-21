import { escapeHtml, formatLanguageLabel, formatMarketLabel, getElement } from "./ui-utils.js";
import { iconSvg } from "./icons.js?v=20260521-two-corner-expand";
import { t } from "./i18n.js";

function formatProjectDateTime(rawValue) {
  const raw = String(rawValue || "").trim();
  if (!raw) {
    return "";
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  return parsed.toLocaleString();
}

function formatSensitivity(value) {
  const normalized = String(value || "medium").toLowerCase();
  if (normalized === "low") {
    return t("sensitivityLow");
  }
  if (normalized === "high") {
    return t("sensitivityHigh");
  }
  return t("sensitivityMedium");
}

function formatProjectStatus(profile) {
  return profile.is_active ? t("projectStatusActive") : t("projectStatusInactive");
}

function profileCardMarkup(profile, isSelected, openProjectMenuId, expandedProjectIds) {
  const isMenuOpen = openProjectMenuId === profile.id;
  const expandedIds = Array.isArray(expandedProjectIds) ? expandedProjectIds : [];
  const isExpanded = expandedIds.includes(profile.id);
  const keyProducts = Array.isArray(profile.key_products) ? profile.key_products : [];
  const languages = Array.isArray(profile.languages) ? profile.languages : [];
  const detailsId = `project-details-${profile.id}`;
  const createdAt = formatProjectDateTime(profile.created_at);
  const updatedAt = formatProjectDateTime(profile.updated_at);
  return `
    <article class="project-card ${isSelected ? "active" : ""} ${isExpanded ? "is-expanded" : ""}" data-project-id="${profile.id}">
      <div class="project-card-header">
        <h4>${escapeHtml(profile.name)}</h4>
        <div class="project-card-actions">
          <button
            class="icon-btn project-card-action-btn project-expand-btn"
            data-project-expand-toggle-id="${profile.id}"
            type="button"
            aria-label="${escapeHtml(t(isExpanded ? "collapseProjectDetails" : "expandProjectDetails"))}"
            aria-controls="${escapeHtml(detailsId)}"
            aria-expanded="${isExpanded ? "true" : "false"}"
          >
            ${iconSvg("open_in_full")}
          </button>
          <button
            class="icon-btn project-card-action-btn project-menu-btn"
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
      ${
        isExpanded
          ? `<div class="project-card-details" id="${escapeHtml(detailsId)}">
              <div class="project-detail-row">
                <span>${escapeHtml(t("formAlertSensitivity"))}</span>
                <strong>${escapeHtml(formatSensitivity(profile.alert_sensitivity))}</strong>
              </div>
              <div class="project-detail-row">
                <span>${escapeHtml(t("projectStatus"))}</span>
                <strong>${escapeHtml(formatProjectStatus(profile))}</strong>
              </div>
              <div class="project-detail-row">
                <span>${escapeHtml(t("formLanguages"))}</span>
                <strong>${escapeHtml(languages.map(formatLanguageLabel).join(", "))}</strong>
              </div>
              ${
                createdAt
                  ? `<div class="project-detail-row">
                      <span>${escapeHtml(t("projectCreatedAt"))}</span>
                      <strong>${escapeHtml(createdAt)}</strong>
                    </div>`
                  : ""
              }
              ${
                updatedAt
                  ? `<div class="project-detail-row">
                      <span>${escapeHtml(t("projectLastUpdated"))}</span>
                      <strong>${escapeHtml(updatedAt)}</strong>
                    </div>`
                  : ""
              }
            </div>`
          : ""
      }
      <button class="open-project-btn btn btn-secondary" type="button" data-open-project-id="${profile.id}">
        ${escapeHtml(t("openProject"))}
      </button>
    </article>
  `;
}

export function renderProfileGrid({ profiles, selectedProfileId, openProjectMenuId = null, expandedProjectIds = [] }) {
  const profileGrid = getElement("profile-grid");
  if (!profileGrid) {
    return;
  }

  if (profiles.length === 0) {
    profileGrid.innerHTML = `<div class="video-detail-empty">${escapeHtml(t("noProjectsYet"))}</div>`;
    return;
  }

  profileGrid.innerHTML = profiles
    .map((profile) => profileCardMarkup(profile, profile.id === selectedProfileId, openProjectMenuId, expandedProjectIds))
    .join("");
}

export function bindDashboardInteractions({
  onOpenProject,
  onDeleteProject,
  onEditProject,
  onToggleProjectMenu,
  onToggleProjectDetails,
  onCloseProjectMenu,
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

    const detailsToggle = target.closest("[data-project-expand-toggle-id]");
    if (detailsToggle instanceof HTMLElement) {
      event.preventDefault();
      event.stopPropagation();
      const profileId = Number(detailsToggle.dataset.projectExpandToggleId);
      if (!Number.isNaN(profileId)) {
        onToggleProjectDetails(profileId);
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
}
