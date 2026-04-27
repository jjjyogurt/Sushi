import { ApiError } from "./api-client.js";
import { syncProjectRoute } from "./router-state.js";
import {
  debounce,
  escapeHtml,
  formatLanguageLabel,
  formatLocalDateYmd,
  formatVideoPublishedAt,
  getElement,
} from "./ui-utils.js";
import { onLocaleChange, t } from "./i18n.js";

const MAX_MANUAL_VIDEO_URLS = 100;
const MAX_VISIBLE_MANUAL_URL_ROWS = 5;

function analysisStatusBadge(video) {
  const status = String(video.latest_analysis_status || "").toLowerCase();
  if (status === "completed") {
    return '<span class="analysis-check material-symbols-outlined">check_circle</span>';
  }
  return "";
}

function sentimentBadge(sentimentLabel) {
  if (!sentimentLabel) {
    return "";
  }
  const css = sentimentLabel === "negative" ? "negative" : sentimentLabel === "positive" ? "positive" : "";
  return `<span class="badge ${css}">${escapeHtml(sentimentLabel)}</span>`;
}

function parseManualVideoUrls(rawValue) {
  const candidates = String(rawValue || "")
    .match(/https?:\/\/[^\s,]+/gi) || [];
  const normalizedUrls = candidates
    .map((item) => item.trim().replace(/[),.;]+$/, ""))
    .filter((item) => item.length > 0)
    .filter((item) => {
      try {
        const parsed = new URL(item);
        return parsed.protocol === "http:" || parsed.protocol === "https:";
      } catch (_error) {
        return false;
      }
    });
  return [...new Set(normalizedUrls)];
}

function videoConflictDetailFromError(error) {
  if (!(error instanceof ApiError) || !error.detail || typeof error.detail !== "object" || Array.isArray(error.detail)) {
    return null;
  }
  const detail = error.detail;
  return detail.code === "VIDEO_PROJECT_CONFLICT" ? detail : null;
}

function updateManualUrlInputRows(inputElement) {
  if (!(inputElement instanceof HTMLTextAreaElement)) {
    return;
  }
  const urlCount = parseManualVideoUrls(inputElement.value).length;
  const nextRows = Math.min(MAX_VISIBLE_MANUAL_URL_ROWS, Math.max(1, urlCount || 1));
  const baseHeightPx = 40;
  const rowIncrementPx = 24;
  const nextHeightPx = baseHeightPx + (nextRows - 1) * rowIncrementPx;
  inputElement.style.height = `${nextHeightPx}px`;
  inputElement.style.overflowY = urlCount > MAX_VISIBLE_MANUAL_URL_ROWS ? "auto" : "hidden";
}

function getKeywordSearchValue() {
  const searchInput = getElement("keyword-search-input");
  if (!(searchInput instanceof HTMLInputElement || searchInput instanceof HTMLTextAreaElement)) {
    return "";
  }
  return searchInput.value.trim();
}

const DISCOVER_CUSTOM_MAX_CALENDAR_DAYS = 366;
const DAY_MS = 24 * 60 * 60 * 1000;

function parseYmdParts(ymd) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(ymd || "").trim());
  if (!match) {
    return null;
  }
  return { y: Number(match[1]), mo: Number(match[2]) - 1, d: Number(match[3]) };
}

function localStartOfYmdMs(ymd) {
  const parts = parseYmdParts(ymd);
  if (!parts) {
    return NaN;
  }
  return new Date(parts.y, parts.mo, parts.d, 0, 0, 0, 0).getTime();
}

/** Start of the calendar day after `ymd` (local), used as exclusive `publishedBefore`. */
function localStartOfDayAfterYmdMs(ymd) {
  const parts = parseYmdParts(ymd);
  if (!parts) {
    return NaN;
  }
  return new Date(parts.y, parts.mo, parts.d + 1, 0, 0, 0, 0).getTime();
}

function localStartOfTodayMs() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0).getTime();
}

/** @returns {{ valid: true, afterMs: number, beforeExclusiveMs: number } | { valid: false, reason?: string }} */
function parseCustomPublishRangeFromDom() {
  const afterInput = getElement("discover-publish-after");
  const beforeInput = getElement("discover-publish-before");
  if (!(afterInput instanceof HTMLInputElement) || !(beforeInput instanceof HTMLInputElement)) {
    return { valid: false, reason: "incomplete" };
  }
  const afterRaw = afterInput.value.trim();
  const beforeRaw = beforeInput.value.trim();
  if (!afterRaw || !beforeRaw) {
    return { valid: false, reason: "incomplete" };
  }
  const afterMs = localStartOfYmdMs(afterRaw);
  const beforeExclusiveMs = localStartOfDayAfterYmdMs(beforeRaw);
  if (Number.isNaN(afterMs) || Number.isNaN(beforeExclusiveMs)) {
    return { valid: false, reason: "incomplete" };
  }
  if (afterMs >= beforeExclusiveMs) {
    return { valid: false, reason: "order" };
  }
  const spanDays = (beforeExclusiveMs - afterMs) / DAY_MS;
  if (spanDays > DISCOVER_CUSTOM_MAX_CALENDAR_DAYS) {
    return { valid: false, reason: "span" };
  }
  return { valid: true, afterMs, beforeExclusiveMs };
}

function discoverPublishWindowPayload() {
  const select = getElement("discover-publish-preset");
  if (!(select instanceof HTMLSelectElement)) {
    return {};
  }
  const preset = select.value.trim();
  if (!preset) {
    return {};
  }
  if (preset === "custom") {
    const parsed = parseCustomPublishRangeFromDom();
    if (!parsed.valid) {
      if (parsed.reason === "order") {
        throw new Error(t("errorDiscoverCustomOrder"));
      }
      if (parsed.reason === "span") {
        throw new Error(t("errorDiscoverCustomMaxSpan"));
      }
      throw new Error(t("errorDiscoverCustomBothRequired"));
    }
    return {
      published_after: new Date(parsed.afterMs).toISOString(),
      published_before: new Date(parsed.beforeExclusiveMs).toISOString(),
    };
  }
  const calendarDaysInclusive = {
    "24h": 1,
    "7d": 7,
    "30d": 30,
    "90d": 90,
  }[preset];
  if (calendarDaysInclusive === undefined) {
    return {};
  }
  const todayStartMs = localStartOfTodayMs();
  const afterMs = todayStartMs - (calendarDaysInclusive - 1) * DAY_MS;
  const beforeExclusiveMs = todayStartMs + DAY_MS;
  return {
    published_after: new Date(afterMs).toISOString(),
    published_before: new Date(beforeExclusiveMs).toISOString(),
  };
}

export function createQueueController({
  getState,
  setState,
  request,
  runTask,
  videoDetailController,
  onProfileSelectionChange,
  onAnyVideoAction,
  onWatchlistMutated,
}) {
  function renderProfileSelect() {
    const profileSelect = getElement("profile-select");
    if (!profileSelect) {
      return;
    }
    const state = getState();

    profileSelect.innerHTML = `<option value="">${escapeHtml(t("allProjects"))}</option>`;
    state.profiles.forEach((profile) => {
      const option = document.createElement("option");
      option.value = String(profile.id);
      option.textContent = profile.name;
      profileSelect.appendChild(option);
    });

    profileSelect.value = state.selectedProfileId ? String(state.selectedProfileId) : "";
  }

  function renderVideoListItem(video, isGlobalScope, isActive, isNew) {
    const projectMeta = isGlobalScope && video.monitor_profile_name ? ` • ${escapeHtml(video.monitor_profile_name)}` : "";
    const sentimentMarkup = sentimentBadge(video.sentiment_label);
    const newBadgeMarkup = isNew ? `<span class="badge new-video-badge">${escapeHtml(t("new"))}</span>` : "";
    const assigneeText = String(video.assigned_user_id || "").trim();
    const assigneeMarkup = assigneeText
      ? `<span class="meta watchlist-assignee">${escapeHtml(t("assignee"))}: ${escapeHtml(assigneeText)}</span>`
      : "";
    const watchTitle = video.is_bookmarked ? t("removeFromWatchlist") : t("addToWatchlist");
    const watchIcon = video.is_bookmarked ? "bookmark" : "bookmark_add";
    const analysisStatusText = String(video.latest_analysis_status || "").trim();
    const analysisStatusLine = `${escapeHtml(t("analysisStatus"))}: <strong>${escapeHtml(
      analysisStatusText || t("notStarted")
    )}</strong>`;
    const publishedLabel = escapeHtml(t("publishedAt"));
    const publishedFormatted = formatVideoPublishedAt(video.published_at);
    const publishedLine = publishedFormatted
      ? `<div class="meta video-row-published">${publishedLabel}: ${escapeHtml(publishedFormatted)}</div>`
      : "";

    return `
      <div class="video-list-row ${isActive ? "active" : ""}">
        <button class="video-item ${isActive ? "active" : ""}" data-video-id="${video.id}" type="button">
          ${analysisStatusBadge(video)}
          <div class="meta-row">
            ${newBadgeMarkup}
            ${sentimentMarkup}
            <span class="meta">${escapeHtml(video.channel_name)}${projectMeta}</span>
            ${assigneeMarkup}
          </div>
          <h4>${escapeHtml(video.title)}</h4>
          <div class="meta video-row-analysis">${analysisStatusLine}</div>
          ${publishedLine}
          <div class="meta">
            ${escapeHtml(formatLanguageLabel(video.language))}
          </div>
        </button>
        <button
          class="icon-btn video-item-watch-btn ${video.is_bookmarked ? "is-bookmarked" : ""}"
          type="button"
          data-watchlist-video-id="${video.id}"
          aria-label="${escapeHtml(watchTitle)}"
          title="${escapeHtml(watchTitle)}"
        >
          <span class="material-symbols-outlined">${watchIcon}</span>
        </button>
        <button
          class="icon-btn video-item-delete-btn"
          type="button"
          data-delete-video-id="${video.id}"
          aria-label="${escapeHtml(t("delete"))} ${escapeHtml(video.title)}"
          title="${escapeHtml(t("deleteVideo"))}"
        >
          <span class="material-symbols-outlined">delete</span>
        </button>
      </div>
    `;
  }

  function renderVideos() {
    const list = getElement("video-list");
    const count = getElement("video-count");
    if (!list || !count) {
      return;
    }
    const state = getState();
    const isGlobalScope = state.selectedProfileId === null;
    const newVideoIdSet = new Set(state.newVideoIds);

    count.textContent = String(state.videos.length);
    if (state.videos.length === 0) {
      const emptyMessage = isGlobalScope ? t("emptyGlobalQueue") : t("emptyProjectQueue");
      list.innerHTML = `<div class="video-detail-empty">${escapeHtml(emptyMessage)}</div>`;
      return;
    }

    list.innerHTML = state.videos
      .map((video) =>
        renderVideoListItem(video, isGlobalScope, video.id === state.selectedVideoId, newVideoIdSet.has(video.id))
      )
      .join("");
  }

  function markNewlyAddedVideos(previousVideoIds, nextVideos) {
    const previousIds = previousVideoIds || new Set();
    const newlyAddedIds = nextVideos
      .map((video) => video.id)
      .filter((videoId) => !previousIds.has(videoId));
    if (newlyAddedIds.length === 0) {
      return;
    }
    setState((previous) => ({
      ...previous,
      newVideoIds: [...new Set([...previous.newVideoIds, ...newlyAddedIds])],
    }));
  }

  function clearNewVideoLabels() {
    const state = getState();
    if (state.newVideoIds.length === 0) {
      return;
    }
    setState((previous) => ({
      ...previous,
      newVideoIds: [],
    }));
    renderVideos();
  }

  function renderSearchCandidates() {
    const candidateList = getElement("search-candidate-list");
    if (!candidateList) {
      return;
    }
    candidateList.innerHTML = "";
  }

  async function refreshVideos() {
    const state = getState();
    const riskFilter = (getElement("risk-filter")?.value || "").trim();
    const sentimentFilter = (getElement("sentiment-filter")?.value || "").trim();
    const titleFilter = getKeywordSearchValue();
    const query = new URLSearchParams();
    if (state.selectedProfileId) {
      query.set("monitor_profile_id", String(state.selectedProfileId));
    }
    if (riskFilter) {
      query.set("risk_level", riskFilter);
    }
    if (sentimentFilter) {
      query.set("sentiment", sentimentFilter);
    }
    if (titleFilter) {
      query.set("title", titleFilter);
    }

    const data = await request(`/videos?${query.toString()}`);
    const nextVideos = Array.isArray(data.items) ? data.items : [];
    const keepSelection = nextVideos.some((video) => video.id === state.selectedVideoId);
    const selectedVideoId =
      keepSelection || nextVideos.length === 0 ? state.selectedVideoId : nextVideos[0].id;

    setState((previous) => ({
      ...previous,
      videos: nextVideos,
      selectedVideoId,
      newVideoIds: previous.newVideoIds.filter((videoId) => nextVideos.some((video) => video.id === videoId)),
      analysisLanguageByVideoId: Object.fromEntries(
        Object.entries(previous.analysisLanguageByVideoId || {}).filter(([videoId]) =>
          nextVideos.some((video) => String(video.id) === String(videoId))
        )
      ),
    }));
    renderVideos();
    await videoDetailController.renderVideoDetail();
    return nextVideos;
  }

  async function discoverVideos() {
    const state = getState();
    if (!state.selectedProfileId) {
      throw new Error(t("errorSelectProjectFirst"));
    }
    const previousVideoIds = new Set(state.videos.map((video) => video.id));
    await request("/videos/discover", {
      method: "POST",
      body: JSON.stringify({
        monitor_profile_id: state.selectedProfileId,
        max_results: 20,
        ...discoverPublishWindowPayload(),
      }),
    });
    videoDetailController.resetCaches();
    const nextVideos = await refreshVideos();
    markNewlyAddedVideos(previousVideoIds, nextVideos);
    renderVideos();
  }

  function bindDiscoverVideoButton(button) {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    button.addEventListener("click", () => {
      button.classList.add("is-discovering");
      button.setAttribute("aria-busy", "true");
      button.disabled = true;
      button.textContent = t("discoveringVideos");
      void runTask(async () => {
        await discoverVideos();
      }, t("discoveryCompleted")).finally(() => {
        button.classList.remove("is-discovering");
        button.removeAttribute("aria-busy");
        button.disabled = false;
        button.textContent = t("discoverVideos");
      });
    });
  }

  async function addManualVideo() {
    const state = getState();
    if (!state.selectedProfileId) {
      throw new Error(t("errorSelectProjectFirst"));
    }
    const urlInput = getElement("manual-video-url");
    if (!(urlInput instanceof HTMLTextAreaElement || urlInput instanceof HTMLInputElement)) {
      return;
    }
    const manualUrls = parseManualVideoUrls(urlInput.value);
    if (manualUrls.length === 0) {
      throw new Error(t("errorPasteValidUrls"));
    }
    if (manualUrls.length > MAX_MANUAL_VIDEO_URLS) {
      throw new Error(t("errorUrlLimit", { count: MAX_MANUAL_VIDEO_URLS }));
    }

    const previousVideoIds = new Set(state.videos.map((video) => video.id));
    const failedUrls = [];
    let firstVideoConflictDetail = null;
    for (const videoUrl of manualUrls) {
      try {
        await request("/videos/manual", {
          method: "POST",
          body: JSON.stringify({
            monitor_profile_id: state.selectedProfileId,
            video_url: videoUrl,
            language: state.tokenInputs.languages[0] || "en",
          }),
        });
      } catch (error) {
        const conflict = videoConflictDetailFromError(error);
        if (conflict && !firstVideoConflictDetail) {
          firstVideoConflictDetail = conflict;
        }
        const message = error instanceof Error ? error.message : t("failedToAddUrl");
        failedUrls.push(`${videoUrl} (${message})`);
      }
    }
    if (failedUrls.length === manualUrls.length) {
      const err = new Error(t("errorCouldNotAddAnyUrl", { reason: failedUrls[0] }));
      if (firstVideoConflictDetail) {
        err.videoConflict = firstVideoConflictDetail;
      }
      throw err;
    }

    urlInput.value = "";
    updateManualUrlInputRows(urlInput);
    
    // Success animation
    const container = getElement("queue");
    if (container) {
      container.classList.add("success-animate");
      setTimeout(() => container.classList.remove("success-animate"), 400);
    }

    const nextVideos = await refreshVideos();
    markNewlyAddedVideos(previousVideoIds, nextVideos);
    renderVideos();

    if (failedUrls.length > 0) {
      const err = new Error(
        t("errorPartialUrlAdd", {
          successCount: manualUrls.length - failedUrls.length,
          totalCount: manualUrls.length,
          reason: failedUrls[0],
        })
      );
      if (firstVideoConflictDetail) {
        err.videoConflict = firstVideoConflictDetail;
      }
      throw err;
    }
  }

  async function searchVideosByKeyword() {
    setState((previous) => ({
      ...previous,
      searchCandidates: [],
    }));
    await refreshVideos();
  }

  function candidateToPayload(candidate) {
    return {
      youtube_video_id: candidate.youtube_video_id,
      video_url: candidate.video_url,
      title: candidate.title,
      channel_name: candidate.channel_name,
      language: candidate.language,
      published_at: candidate.published_at,
      description: candidate.description,
    };
  }

  async function addCandidateByYoutubeId(youtubeVideoId) {
    const state = getState();
    if (!state.selectedProfileId) {
      throw new Error(t("errorSelectProjectFirst"));
    }
    const candidate = state.searchCandidates.find((item) => item.youtube_video_id === youtubeVideoId);
    if (!candidate || !candidate.can_add) {
      throw new Error(t("errorCandidateUnavailable"));
    }

    const previousVideoIds = new Set(state.videos.map((video) => video.id));
    await request("/videos/bulk-add", {
      method: "POST",
      body: JSON.stringify({
        monitor_profile_id: state.selectedProfileId,
        candidates: [candidateToPayload(candidate)],
      }),
    });

    // Success animation
    const container = getElement("queue");
    if (container) {
      container.classList.add("success-animate");
      setTimeout(() => container.classList.remove("success-animate"), 400);
    }

    setState((previous) => ({
      ...previous,
      searchCandidates: previous.searchCandidates.map((item) =>
        item.youtube_video_id === youtubeVideoId
          ? {
              ...item,
              can_add: false,
              block_reason: t("alreadyInQueue"),
            }
          : item
      ),
    }));
    renderSearchCandidates();
    const nextVideos = await refreshVideos();
    markNewlyAddedVideos(previousVideoIds, nextVideos);
    renderVideos();
  }

  async function runAllAnalyses(runAllButton) {
    onAnyVideoAction?.();
    clearNewVideoLabels();
    const state = getState();
    const videos = [...state.videos];
    if (videos.length === 0) {
      throw new Error(t("errorNoVideosToAnalyze"));
    }

    const button = runAllButton || getElement("run-all-analysis-btn");
    const originalLabel = button ? button.textContent : t("runAllAnalysis");
    if (button) {
      button.disabled = true;
    }

    let successCount = 0;
    let failedCount = 0;
    const failures = [];

    try {
      for (let index = 0; index < videos.length; index += 1) {
        const video = videos[index];
        if (button) {
          button.textContent = t("analyzingProgress", { current: index + 1, total: videos.length });
        }
        try {
          await request(`/videos/${video.id}/analyze`, {
            method: "POST",
            body: JSON.stringify({ force_reanalyze: true }),
          });
          videoDetailController.invalidateVideoCache(video.id);
          successCount += 1;
        } catch (error) {
          failedCount += 1;
          const message = error instanceof Error ? error.message : t("analysisFailed");
          failures.push(`${video.title}: ${message}`);
        }
      }
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = originalLabel || t("runAllAnalysis");
      }
    }

    await refreshVideos();
    if (failedCount > 0) {
      const failurePreview = failures.slice(0, 2).join(" | ");
      throw new Error(
        t("runAllCompletedWithFailures", {
          successCount,
          failedCount,
          failurePreview,
        })
      );
    }
  }

  async function deleteVideo(videoId) {
    if (!window.confirm(t("confirmDeleteVideo"))) {
      return;
    }

    onAnyVideoAction?.();
    clearNewVideoLabels();
    await request(`/videos/${videoId}`, {
      method: "DELETE",
    });

    videoDetailController.resetCaches();
    setState((previous) => ({
      ...previous,
      selectedVideoId: previous.selectedVideoId === videoId ? null : previous.selectedVideoId,
    }));
    await refreshVideos();
  }

  async function toggleWatchlist(videoId) {
    const state = getState();
    const targetVideo = state.videos.find((video) => video.id === videoId);
    if (!targetVideo) {
      return;
    }
    const isBookmarked = Boolean(targetVideo.is_bookmarked);
    const endpoint = `/watchlist/videos/${videoId}`;
    if (isBookmarked) {
      await request(endpoint, { method: "DELETE" });
    } else {
      await request(endpoint, { method: "POST" });
    }
    setState((previous) => ({
      ...previous,
      videos: previous.videos.map((video) =>
        video.id === videoId
          ? {
              ...video,
              is_bookmarked: !isBookmarked,
            }
          : video
      ),
    }));
    renderVideos();
    await onWatchlistMutated?.();
    if (getState().selectedVideoId === videoId) {
      await videoDetailController.renderVideoDetail();
    }
  }

  function selectVideo(videoId) {
    setState((previous) => ({
      ...previous,
      selectedVideoId: videoId,
      transcriptExpanded: false,
    }));
    renderVideos();
    void videoDetailController.renderVideoDetail();
  }

  function bindQueueInteractions() {
    const videoList = getElement("video-list");
    if (videoList) {
      videoList.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
          return;
        }
        const deleteButton = target.closest("[data-delete-video-id]");
        if (deleteButton instanceof HTMLElement) {
          const deleteVideoId = Number(deleteButton.dataset.deleteVideoId);
          if (!Number.isNaN(deleteVideoId)) {
            void runTask(async () => {
              await deleteVideo(deleteVideoId);
            }, t("videoDeleted"));
          }
          return;
        }
        const watchlistButton = target.closest("[data-watchlist-video-id]");
        if (watchlistButton instanceof HTMLElement) {
          const watchlistVideoId = Number(watchlistButton.dataset.watchlistVideoId);
          if (!Number.isNaN(watchlistVideoId)) {
            void runTask(async () => {
              await toggleWatchlist(watchlistVideoId);
            }, t(watchlistButton.classList.contains("is-bookmarked") ? "removedFromWatchlist" : "addedToWatchlist"));
          }
          return;
        }
        const button = target.closest(".video-item");
        if (!(button instanceof HTMLElement)) {
          return;
        }
        const videoId = Number(button.dataset.videoId);
        if (!Number.isNaN(videoId)) {
          selectVideo(videoId);
        }
      });
    }

    const profileSelect = getElement("profile-select");
    if (profileSelect) {
      profileSelect.addEventListener("change", () => {
        const parsedProfileId = Number(profileSelect.value);
        const selectedProfileId = Number.isNaN(parsedProfileId) || !profileSelect.value ? null : parsedProfileId;
        setState((previous) => ({
          ...previous,
          selectedProfileId,
          selectedVideoId: null,
          searchCandidates: [],
        }));
        syncProjectRoute(selectedProfileId);
        onProfileSelectionChange();
        renderSearchCandidates();
        void runTask(async () => {
          await refreshVideos();
        });
      });
    }

    const refreshButton = getElement("refresh-videos-btn");
    if (refreshButton) {
      refreshButton.addEventListener("click", () => {
        void runTask(async () => {
          await refreshVideos();
        });
      });
    }

    const discoverButton = getElement("discover-btn");
    if (discoverButton) {
      bindDiscoverVideoButton(discoverButton);
    }

    const discoverPublishPreset = getElement("discover-publish-preset");
    const discoverPublishAfter = getElement("discover-publish-after");
    const discoverPublishBefore = getElement("discover-publish-before");

    let discoverCustomRangeCollapsed = false;
    const customOptionLabelMax = 56;

    function syncDiscoverPresetCustomOptionLabel() {
      const opt = getElement("discover-publish-preset-option-custom");
      if (!(opt instanceof HTMLOptionElement) || !(discoverPublishPreset instanceof HTMLSelectElement)) {
        return;
      }
      const preset = discoverPublishPreset.value.trim();
      if (preset !== "custom") {
        opt.textContent = t("discoverPresetCustom");
        return;
      }
      const parsed = parseCustomPublishRangeFromDom();
      if (
        discoverCustomRangeCollapsed &&
        parsed.valid &&
        discoverPublishAfter instanceof HTMLInputElement &&
        discoverPublishBefore instanceof HTMLInputElement
      ) {
        const startLabel = formatLocalDateYmd(discoverPublishAfter.value.trim());
        const endLabel = formatLocalDateYmd(discoverPublishBefore.value.trim());
        let text = `${startLabel} – ${endLabel}`;
        if (text.length > customOptionLabelMax) {
          text = `${text.slice(0, customOptionLabelMax - 1)}…`;
        }
        opt.textContent = text;
        return;
      }
      opt.textContent = t("discoverPresetCustom");
    }

    function refreshDiscoverPublishCustomUi() {
      if (!(discoverPublishPreset instanceof HTMLSelectElement)) {
        return;
      }
      const wrap = getElement("discover-publish-custom-wrap");
      if (!(wrap instanceof HTMLElement)) {
        return;
      }
      const preset = discoverPublishPreset.value.trim();
      if (preset !== "custom") {
        discoverCustomRangeCollapsed = false;
        wrap.classList.add("is-hidden");
        syncDiscoverPresetCustomOptionLabel();
        return;
      }
      const parsed = parseCustomPublishRangeFromDom();
      if (discoverCustomRangeCollapsed && parsed.valid) {
        wrap.classList.add("is-hidden");
        syncDiscoverPresetCustomOptionLabel();
        return;
      }
      wrap.classList.remove("is-hidden");
      syncDiscoverPresetCustomOptionLabel();
    }

    function onCustomPublishRangeFieldChange() {
      if (!(discoverPublishPreset instanceof HTMLSelectElement) || discoverPublishPreset.value.trim() !== "custom") {
        return;
      }
      const parsed = parseCustomPublishRangeFromDom();
      discoverCustomRangeCollapsed = Boolean(parsed.valid);
      refreshDiscoverPublishCustomUi();
    }

    if (discoverPublishPreset instanceof HTMLSelectElement) {
      discoverPublishPreset.addEventListener("change", () => {
        const nextPreset = discoverPublishPreset.value.trim();
        if (nextPreset !== "custom") {
          discoverCustomRangeCollapsed = false;
          if (discoverPublishAfter instanceof HTMLInputElement) {
            discoverPublishAfter.value = "";
          }
          if (discoverPublishBefore instanceof HTMLInputElement) {
            discoverPublishBefore.value = "";
          }
        }
        refreshDiscoverPublishCustomUi();
      });
    }

    if (discoverPublishAfter instanceof HTMLInputElement) {
      discoverPublishAfter.addEventListener("change", onCustomPublishRangeFieldChange);
    }
    if (discoverPublishBefore instanceof HTMLInputElement) {
      discoverPublishBefore.addEventListener("change", onCustomPublishRangeFieldChange);
    }

    onLocaleChange(() => {
      refreshDiscoverPublishCustomUi();
    });

    refreshDiscoverPublishCustomUi();

    const discoverButtonInline = getElement("discover-btn-inline");
    if (discoverButtonInline) {
      bindDiscoverVideoButton(discoverButtonInline);
    }

    const runAllAnalysisButton = getElement("run-all-analysis-btn");
    if (runAllAnalysisButton) {
      runAllAnalysisButton.addEventListener("click", () => {
        void runTask(async () => {
          await runAllAnalyses(runAllAnalysisButton);
        }, t("runAllAnalysisCompleted"));
      });
    }

    const addManualButton = getElement("add-manual-video-btn");
    if (addManualButton) {
      addManualButton.addEventListener("click", () => {
        void runTask(async () => {
          await addManualVideo();
        }, t("videosAddedToProject"));
      });
    }

    const manualVideoUrlInput = getElement("manual-video-url");
    if (manualVideoUrlInput instanceof HTMLTextAreaElement) {
      updateManualUrlInputRows(manualVideoUrlInput);
      manualVideoUrlInput.addEventListener("input", () => {
        updateManualUrlInputRows(manualVideoUrlInput);
      });
    }

    const keywordSearchButton = getElement("search-keyword-btn");
    if (keywordSearchButton) {
      keywordSearchButton.addEventListener("click", () => {
        void runTask(async () => {
          await searchVideosByKeyword();
        }, t("searchCompleted"));
      });
    }

    const keywordSearchInput = getElement("keyword-search-input");
    if (keywordSearchInput) {
      const debouncedSearch = debounce(() => {
        void runTask(async () => {
          await searchVideosByKeyword();
        });
      }, 280);
      keywordSearchInput.addEventListener("input", () => {
        debouncedSearch();
      });
      keywordSearchInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          void runTask(async () => {
            await searchVideosByKeyword();
          }, t("searchCompleted"));
        }
      });
    }

    const candidateList = getElement("search-candidate-list");
    if (candidateList) {
      candidateList.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
          return;
        }
        const addButton = target.closest("[data-candidate-add-id]");
        if (!(addButton instanceof HTMLElement)) {
          return;
        }
        const youtubeVideoId = addButton.dataset.candidateAddId;
        if (!youtubeVideoId) {
          return;
        }
        void runTask(async () => {
          await addCandidateByYoutubeId(youtubeVideoId);
        }, t("videoAddedToQueue"));
      });
    }

    const riskFilterSelect = getElement("risk-filter");
    if (riskFilterSelect) {
      riskFilterSelect.addEventListener("change", () => {
        void runTask(async () => {
          await refreshVideos();
        });
      });
    }

    const sentimentFilterSelect = getElement("sentiment-filter");
    if (sentimentFilterSelect) {
      sentimentFilterSelect.addEventListener("change", () => {
        void runTask(async () => {
          await refreshVideos();
        });
      });
    }
  }

  return {
    bindQueueInteractions,
    renderProfileSelect,
    renderVideos,
    renderSearchCandidates,
    refreshVideos,
    selectVideo,
  };
}
