import { escapeHtml, formatLanguageLabel, formatMarketLabel, getElement } from "./ui-utils.js";
import { t } from "./i18n.js";

function profileCardMarkup(profile, isSelected, openProjectMenuId) {
  const isMenuOpen = openProjectMenuId === profile.id;
  const keyProducts = Array.isArray(profile.key_products) ? profile.key_products : [];
  return `
    <article class="project-card ${isSelected ? "active" : ""}" data-project-id="${profile.id}">
      <div class="project-card-header">
        <h4>${escapeHtml(profile.name)}</h4>
        <div class="project-card-actions">
          <button
            class="icon-btn project-menu-btn"
            data-project-menu-toggle-id="${profile.id}"
            type="button"
            aria-label="${escapeHtml(t("projectActions"))}"
            aria-haspopup="menu"
            aria-expanded="${isMenuOpen ? "true" : "false"}"
          >
            <span class="material-symbols-outlined">more_vert</span>
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
