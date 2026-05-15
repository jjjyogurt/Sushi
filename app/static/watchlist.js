import { escapeHtml, getElement } from "./ui-utils.js";
import { iconSvg } from "./icons.js";
import { t } from "./i18n.js";

function sentimentBadge(sentimentLabel) {
  if (!sentimentLabel) {
    return "";
  }
  const css = sentimentLabel === "negative" ? "negative" : sentimentLabel === "positive" ? "positive" : "";
  return `<span class="badge ${css}">${escapeHtml(sentimentLabel)}</span>`;
}

export function createWatchlistController({ request, runTask, onOpenVideo }) {
  let items = [];

  function renderWatchlist() {
    const list = getElement("watchlist-list");
    const count = getElement("watchlist-count");
    if (!(list instanceof HTMLElement)) {
      return;
    }
    if (count) {
      count.textContent = String(items.length);
    }
    if (items.length === 0) {
      list.innerHTML = `<div class="video-detail-empty">${escapeHtml(t("watchlistEmpty"))}</div>`;
      return;
    }
    list.innerHTML = items
      .map((video) => {
        const assignee = String(video.assigned_user_id || "").trim();
        const assigneeMarkup = assignee
          ? `<span class="meta watchlist-assignee">${escapeHtml(t("assignee"))}: ${escapeHtml(assignee)}</span>`
          : "";
        return `
          <div class="watchlist-row" data-watchlist-video-id="${video.id}" data-watchlist-project-id="${video.monitor_profile_id}">
            <button class="watchlist-open-btn" type="button" data-watchlist-open-video-id="${video.id}">
              <div class="meta-row">
                ${sentimentBadge(video.sentiment_label)}
                <span class="meta">${escapeHtml(video.channel_name || "")}</span>
                ${assigneeMarkup}
              </div>
              <h4>${escapeHtml(video.title || "")}</h4>
              <div class="meta">${escapeHtml(video.monitor_profile_name || "")}</div>
            </button>
            <button
              class="icon-btn watchlist-remove-btn"
              type="button"
              data-watchlist-remove-video-id="${video.id}"
              aria-label="${escapeHtml(t("removeFromWatchlist"))}"
              title="${escapeHtml(t("removeFromWatchlist"))}"
            >
              ${iconSvg("bookmark_remove")}
            </button>
          </div>
        `;
      })
      .join("");
  }

  async function loadWatchlist() {
    const payload = await request("/watchlist");
    items = Array.isArray(payload.items) ? payload.items : [];
    renderWatchlist();
  }

  function bindWatchlistControls() {
    const refreshButton = getElement("watchlist-refresh-btn");
    if (refreshButton instanceof HTMLButtonElement) {
      refreshButton.addEventListener("click", () => {
        void runTask(async () => {
          await loadWatchlist();
        });
      });
    }

    const list = getElement("watchlist-list");
    if (!(list instanceof HTMLElement)) {
      return;
    }
    list.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      const removeButton = target.closest("[data-watchlist-remove-video-id]");
      if (removeButton instanceof HTMLElement) {
        const videoId = Number(removeButton.dataset.watchlistRemoveVideoId);
        if (Number.isNaN(videoId)) {
          return;
        }
        void runTask(async () => {
          await request(`/watchlist/videos/${videoId}`, { method: "DELETE" });
          await loadWatchlist();
        }, t("removedFromWatchlist"));
        return;
      }
      const openButton = target.closest("[data-watchlist-open-video-id]");
      if (!(openButton instanceof HTMLElement)) {
        return;
      }
      const videoId = Number(openButton.dataset.watchlistOpenVideoId);
      const row = openButton.closest("[data-watchlist-project-id]");
      const projectId = row instanceof HTMLElement ? Number(row.dataset.watchlistProjectId) : Number.NaN;
      if (Number.isNaN(videoId) || Number.isNaN(projectId)) {
        return;
      }
      onOpenVideo(projectId, videoId);
    });
  }

  return {
    bindWatchlistControls,
    async refresh() {
      await loadWatchlist();
    },
  };
}
