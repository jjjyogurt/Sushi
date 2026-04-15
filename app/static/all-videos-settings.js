import { escapeHtml, getElement } from "./ui-utils.js";
import { t } from "./i18n.js";

export function createAllVideosSettingsController({
  request,
  runTask,
  setActiveSection,
  syncProjectRoute,
  onVideosMutated,
}) {
  async function fetchAllVideos() {
    const data = await request("/videos");
    return Array.isArray(data.items) ? data.items : [];
  }

  function renderTable(items) {
    const tbody = getElement("all-videos-tbody");
    const meta = getElement("all-videos-meta");
    if (!(tbody instanceof HTMLTableSectionElement)) {
      return;
    }
    if (meta) {
      meta.textContent = t("settingsAllVideosMetaCount", { count: items.length });
    }
    if (items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="all-videos-empty">${escapeHtml(t("settingsAllVideosEmpty"))}</td></tr>`;
      return;
    }
    tbody.innerHTML = items
      .map((video) => {
        const projectName = video.monitor_profile_name
          ? escapeHtml(String(video.monitor_profile_name))
          : escapeHtml(t("unknown"));
        const title = escapeHtml(String(video.title || ""));
        const channel = escapeHtml(String(video.channel_name || ""));
        const url = String(video.video_url || "");
        const safeUrl = escapeHtml(url);
        const vid = Number(video.id);
        return `
          <tr data-all-video-id="${vid}" class="all-videos-row">
            <td>${projectName}</td>
            <td>${title}</td>
            <td>${channel}</td>
            <td><a href="${safeUrl}" target="_blank" rel="noreferrer" class="all-videos-external">${escapeHtml(t("settingsAllVideosOpenYoutube"))}</a></td>
            <td>
              <button type="button" class="btn btn-secondary btn-sm text-danger" data-all-videos-delete="${vid}">
                ${escapeHtml(t("deleteVideo"))}
              </button>
            </td>
          </tr>
        `;
      })
      .join("");
  }

  async function loadVideos() {
    const tbody = getElement("all-videos-tbody");
    if (!(tbody instanceof HTMLTableSectionElement)) {
      return;
    }
    tbody.innerHTML = `<tr><td colspan="5">${escapeHtml(t("loading"))}</td></tr>`;
    try {
      const items = await fetchAllVideos();
      renderTable(items);
    } catch (_error) {
      tbody.innerHTML = `<tr><td colspan="5" class="all-videos-error">${escapeHtml(t("settingsAllVideosLoadFailed"))}</td></tr>`;
    }
  }

  function scrollToHighlight(videoId) {
    const row = document.querySelector(`[data-all-video-id="${videoId}"]`);
    if (!(row instanceof HTMLElement)) {
      return;
    }
    row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    row.classList.add("all-videos-row-flash");
    window.setTimeout(() => {
      row.classList.remove("all-videos-row-flash");
    }, 2400);
  }

  function openSettingsAndHighlight(videoId) {
    syncProjectRoute(null);
    setActiveSection("settings");
    const details = getElement("all-videos-details");
    if (details instanceof HTMLDetailsElement) {
      details.open = true;
    }
    void loadVideos().then(() => {
      scrollToHighlight(videoId);
    });
  }

  function bindAllVideosSettings() {
    const details = getElement("all-videos-details");
    const tbody = getElement("all-videos-tbody");
    if (!(details instanceof HTMLDetailsElement) || !(tbody instanceof HTMLTableSectionElement)) {
      return;
    }

    details.addEventListener("toggle", () => {
      if (!details.open) {
        return;
      }
      void loadVideos();
    });

    tbody.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      const btn = target.closest("[data-all-videos-delete]");
      if (!(btn instanceof HTMLButtonElement)) {
        return;
      }
      const id = Number(btn.dataset.allVideosDelete);
      if (Number.isNaN(id)) {
        return;
      }
      if (!window.confirm(t("confirmDeleteVideo"))) {
        return;
      }
      void runTask(async () => {
        await request(`/videos/${id}`, { method: "DELETE" });
        await loadVideos();
        await onVideosMutated?.();
      }, t("videoDeleted"));
    });
  }

  return {
    bindAllVideosSettings,
    openSettingsAndHighlight,
  };
}
