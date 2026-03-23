import { escapeHtml, getElement } from "./ui-utils.js";

function profileCardMarkup(profile, isSelected) {
  return `
    <article class="project-card ${isSelected ? "active" : ""}" data-project-id="${profile.id}">
      <div class="project-card-header">
        <h4>${escapeHtml(profile.name)}</h4>
        <button class="delete-project-btn" data-delete-project-id="${profile.id}" type="button" aria-label="Delete project">
          ×
        </button>
      </div>
      <div class="meta">Keywords: ${escapeHtml(profile.brand_keywords.join(", "))}</div>
      <div class="chip-row">
        ${profile.markets.map((market) => `<span class="badge">${escapeHtml(market)}</span>`).join("")}
      </div>
      <div class="chip-row">
        ${profile.languages.map((language) => `<span class="badge">${escapeHtml(language)}</span>`).join("")}
      </div>
      <button class="open-project-btn btn btn-secondary" type="button" data-open-project-id="${profile.id}">
        Open Project
      </button>
    </article>
  `;
}

export function renderProfileGrid({ profiles, selectedProfileId }) {
  const profileGrid = getElement("profile-grid");
  if (!profileGrid) {
    return;
  }

  if (profiles.length === 0) {
    profileGrid.innerHTML =
      '<div class="video-detail-empty">No projects yet. Create one to start monitoring videos.</div>';
    return;
  }

  profileGrid.innerHTML = profiles
    .map((profile) => profileCardMarkup(profile, profile.id === selectedProfileId))
    .join("");
}

export function bindDashboardInteractions({ onOpenProject, onDeleteProject }) {
  const profileGrid = getElement("profile-grid");
  if (!profileGrid) {
    return;
  }

  profileGrid.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }

    const deleteButton = target.closest("[data-delete-project-id]");
    if (deleteButton instanceof HTMLElement) {
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
      const profileId = Number(card.dataset.projectId);
      if (!Number.isNaN(profileId)) {
        onOpenProject(profileId);
      }
    }
  });
}
