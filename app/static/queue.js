import { syncProjectRoute } from "./router-state.js";
import { debounce, escapeHtml, formatLanguageLabel, getElement } from "./ui-utils.js";

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

function videoStatusLabel(candidate) {
  if (candidate.can_add) {
    return '<span class="badge positive">Addable</span>';
  }
  return `<span class="badge neutral">${escapeHtml(candidate.block_reason || "Unavailable")}</span>`;
}

export function createQueueController({
  getState,
  setState,
  request,
  runTask,
  videoDetailController,
  onProfileSelectionChange,
}) {
  function renderProfileSelect() {
    const profileSelect = getElement("profile-select");
    if (!profileSelect) {
      return;
    }
    const state = getState();

    profileSelect.innerHTML = '<option value="">All Projects</option>';
    state.profiles.forEach((profile) => {
      const option = document.createElement("option");
      option.value = String(profile.id);
      option.textContent = profile.name;
      profileSelect.appendChild(option);
    });

    profileSelect.value = state.selectedProfileId ? String(state.selectedProfileId) : "";
  }

  function renderVideoListItem(video, isGlobalScope, isActive) {
    const projectMeta = isGlobalScope && video.monitor_profile_name ? ` • ${escapeHtml(video.monitor_profile_name)}` : "";
    const sentimentMarkup = sentimentBadge(video.sentiment_label);
    return `
      <div class="video-list-row ${isActive ? "active" : ""}">
        <button class="video-item ${isActive ? "active" : ""}" data-video-id="${video.id}" type="button">
          ${analysisStatusBadge(video)}
          <div class="meta-row">
            ${sentimentMarkup}
            <span class="meta">${escapeHtml(video.channel_name)}${projectMeta}</span>
          </div>
          <h4>${escapeHtml(video.title)}</h4>
          <div class="meta">
            ${escapeHtml(formatLanguageLabel(video.language))}
          </div>
        </button>
        <button
          class="icon-btn video-item-delete-btn"
          type="button"
          data-delete-video-id="${video.id}"
          aria-label="Delete ${escapeHtml(video.title)}"
          title="Delete video"
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

    count.textContent = String(state.videos.length);
    if (state.videos.length === 0) {
      const emptyMessage = isGlobalScope
        ? "No videos in the global queue yet."
        : "No videos yet. Discover or search for videos for this project.";
      list.innerHTML = `<div class="video-detail-empty">${escapeHtml(emptyMessage)}</div>`;
      return;
    }

    list.innerHTML = state.videos
      .map((video) => renderVideoListItem(video, isGlobalScope, video.id === state.selectedVideoId))
      .join("");
  }

  function renderSearchCandidates() {
    const candidateList = getElement("search-candidate-list");
    if (!candidateList) {
      return;
    }
    const state = getState();

    if (state.searchCandidates.length === 0) {
      candidateList.innerHTML = "";
      return;
    }

    candidateList.innerHTML = state.searchCandidates
      .map((candidate) => {
        const addLabel = candidate.can_add ? "Add" : "Added";
        return `
          <div class="candidate-row ${candidate.can_add ? "" : "is-disabled"}">
            <div class="candidate-body">
              <div class="candidate-title">${escapeHtml(candidate.title)}</div>
              <div class="meta">${escapeHtml(candidate.channel_name)} • ${escapeHtml(
          formatLanguageLabel(candidate.language)
        )}</div>
              <div class="candidate-status-row">
                ${videoStatusLabel(candidate)}
                <div class="candidate-status-actions">
                  <a href="${escapeHtml(candidate.video_url)}" target="_blank" rel="noreferrer">Preview ↗</a>
                  <button
                    class="btn btn-secondary btn-sm"
                    type="button"
                    data-candidate-add-id="${escapeHtml(candidate.youtube_video_id)}"
                    ${candidate.can_add ? "" : "disabled"}
                  >
                    ${addLabel}
                  </button>
                </div>
              </div>
            </div>
          </div>
        `;
      })
      .join("");
  }

  async function refreshVideos() {
    const state = getState();
    const titleFilter = (getElement("title-filter")?.value || "").trim();
    const query = new URLSearchParams();
    if (state.selectedProfileId) {
      query.set("monitor_profile_id", String(state.selectedProfileId));
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
    }));
    renderVideos();
    await videoDetailController.renderVideoDetail();
  }

  async function discoverVideos() {
    const state = getState();
    if (!state.selectedProfileId) {
      throw new Error("Select a project first.");
    }
    await request("/videos/discover", {
      method: "POST",
      body: JSON.stringify({
        monitor_profile_id: state.selectedProfileId,
        max_results: 20,
      }),
    });
    videoDetailController.resetCaches();
    await refreshVideos();
  }

  async function addManualVideo() {
    const state = getState();
    if (!state.selectedProfileId) {
      throw new Error("Select a project first.");
    }
    const urlInput = getElement("manual-video-url");
    if (!urlInput) {
      return;
    }
    const videoUrl = urlInput.value.trim();
    if (!videoUrl) {
      throw new Error("Paste a YouTube URL first.");
    }

    await request("/videos/manual", {
      method: "POST",
      body: JSON.stringify({
        monitor_profile_id: state.selectedProfileId,
        video_url: videoUrl,
        language: state.tokenInputs.languages[0] || "en",
      }),
    });
    urlInput.value = "";
    
    // Success animation
    const container = getElement("queue");
    if (container) {
      container.classList.add("success-animate");
      setTimeout(() => container.classList.remove("success-animate"), 400);
    }

    await refreshVideos();
  }

  async function searchCandidatesByKeyword() {
    const state = getState();
    if (!state.selectedProfileId) {
      throw new Error("Select a project first.");
    }
    const searchInput = getElement("keyword-search-input");
    if (!searchInput) {
      return;
    }
    const query = searchInput.value.trim();
    if (!query) {
      throw new Error("Type keywords to search videos.");
    }

    const payload = await request("/videos/search", {
      method: "POST",
      body: JSON.stringify({
        monitor_profile_id: state.selectedProfileId,
        query,
        max_results: 20,
      }),
    });

    setState((previous) => ({
      ...previous,
      searchCandidates: Array.isArray(payload.items) ? payload.items : [],
    }));
    renderSearchCandidates();
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
      throw new Error("Select a project first.");
    }
    const candidate = state.searchCandidates.find((item) => item.youtube_video_id === youtubeVideoId);
    if (!candidate || !candidate.can_add) {
      throw new Error("This candidate is unavailable for adding.");
    }

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
              block_reason: "Already in queue",
            }
          : item
      ),
    }));
    renderSearchCandidates();
    await refreshVideos();
  }

  async function runAllAnalyses(runAllButton) {
    const state = getState();
    const videos = [...state.videos];
    if (videos.length === 0) {
      throw new Error("No videos in this list to analyze.");
    }

    const button = runAllButton || getElement("run-all-analysis-btn");
    const originalLabel = button ? button.textContent : "Run All Analysis";
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
          button.textContent = `Analyzing ${index + 1}/${videos.length}`;
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
          const message = error instanceof Error ? error.message : "Analysis failed.";
          failures.push(`${video.title}: ${message}`);
        }
      }
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = originalLabel || "Run All Analysis";
      }
    }

    await refreshVideos();
    if (failedCount > 0) {
      const failurePreview = failures.slice(0, 2).join(" | ");
      throw new Error(`Run all completed: ${successCount} succeeded, ${failedCount} failed. ${failurePreview}`);
    }
  }

  async function deleteVideo(videoId) {
    if (!window.confirm("Delete this video from the list? This action cannot be undone.")) {
      return;
    }

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
            }, "Video deleted.");
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
      discoverButton.addEventListener("click", () => {
        void runTask(async () => {
          await discoverVideos();
        }, "Discovery completed.");
      });
    }

    const runAllAnalysisButton = getElement("run-all-analysis-btn");
    if (runAllAnalysisButton) {
      runAllAnalysisButton.addEventListener("click", () => {
        void runTask(async () => {
          await runAllAnalyses(runAllAnalysisButton);
        }, "Run all analysis completed.");
      });
    }

    const addManualButton = getElement("add-manual-video-btn");
    if (addManualButton) {
      addManualButton.addEventListener("click", () => {
        void runTask(async () => {
          await addManualVideo();
        }, "Manual video added.");
      });
    }

    const keywordSearchButton = getElement("search-keyword-btn");
    if (keywordSearchButton) {
      keywordSearchButton.addEventListener("click", () => {
        void runTask(async () => {
          await searchCandidatesByKeyword();
        }, "Search completed.");
      });
    }

    const keywordSearchInput = getElement("keyword-search-input");
    if (keywordSearchInput) {
      keywordSearchInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          void runTask(async () => {
            await searchCandidatesByKeyword();
          }, "Search completed.");
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
        }, "Video added to queue.");
      });
    }

    const titleFilterInput = getElement("title-filter");
    if (titleFilterInput) {
      const debouncedRefresh = debounce(() => {
        void runTask(async () => {
          await refreshVideos();
        });
      }, 260);
      titleFilterInput.addEventListener("input", () => {
        debouncedRefresh();
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
