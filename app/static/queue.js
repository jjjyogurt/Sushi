import { syncProjectRoute } from "./router-state.js";
import { debounce, escapeHtml, getElement } from "./ui-utils.js";

function queueStateBadge(queueState) {
  return `<span class="badge">${escapeHtml(queueState || "discovered")}</span>`;
}

function sentimentBadge(sentimentLabel) {
  if (!sentimentLabel) {
    return '<span class="badge">unknown</span>';
  }
  const css = sentimentLabel === "negative" ? "negative" : sentimentLabel === "positive" ? "positive" : "";
  return `<span class="badge ${css}">${escapeHtml(sentimentLabel)}</span>`;
}

function candidateStatusLabel(candidate) {
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
    return `
      <div class="video-list-row ${isActive ? "active" : ""}">
        <button class="video-item ${isActive ? "active" : ""}" data-video-id="${video.id}" type="button">
          <div class="meta-row">
            ${queueStateBadge(video.queue_state)}
            ${sentimentBadge(video.sentiment_label)}
            <span class="meta">${escapeHtml(video.channel_name)}${projectMeta}</span>
          </div>
          <h4>${escapeHtml(video.title)}</h4>
          <div class="meta">
            ${escapeHtml(video.language)} •
            <span class="badge">Score ${Number(video.relevance_score || 0).toFixed(2)}</span>
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
        : "No candidates yet. Discover videos for this project.";
      list.innerHTML = `<div class="video-detail-empty">${escapeHtml(emptyMessage)}</div>`;
      return;
    }

    list.innerHTML = state.videos
      .map((video) => renderVideoListItem(video, isGlobalScope, video.id === state.selectedVideoId))
      .join("");
  }

  function renderSearchCandidates() {
    const candidateList = getElement("search-candidate-list");
    const addSelectedButton = getElement("add-selected-candidates-btn");
    if (!candidateList || !addSelectedButton) {
      return;
    }
    const state = getState();

    if (state.searchCandidates.length === 0) {
      candidateList.innerHTML = "";
      addSelectedButton.disabled = true;
      return;
    }

    candidateList.innerHTML = state.searchCandidates
      .map((candidate) => {
        const isChecked = state.selectedSearchVideoIds.includes(candidate.youtube_video_id);
        return `
          <label class="candidate-row ${candidate.can_add ? "" : "is-disabled"}">
            <input
              type="checkbox"
              data-candidate-video-id="${escapeHtml(candidate.youtube_video_id)}"
              ${isChecked ? "checked" : ""}
              ${candidate.can_add ? "" : "disabled"}
            />
            <div class="candidate-body">
              <div class="candidate-title">${escapeHtml(candidate.title)}</div>
              <div class="meta">${escapeHtml(candidate.channel_name)} • ${escapeHtml(candidate.language)} • Score ${Number(
          candidate.relevance_score || 0
        ).toFixed(2)}</div>
              <div class="candidate-status-row">
                ${candidateStatusLabel(candidate)}
                <a href="${escapeHtml(candidate.video_url)}" target="_blank" rel="noreferrer">Preview ↗</a>
              </div>
            </div>
          </label>
        `;
      })
      .join("");

    addSelectedButton.disabled = state.selectedSearchVideoIds.length === 0;
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
      selectedSearchVideoIds: [],
    }));
    renderSearchCandidates();
  }

  function selectedCandidatePayload(state) {
    return state.searchCandidates
      .filter((candidate) => state.selectedSearchVideoIds.includes(candidate.youtube_video_id))
      .map((candidate) => ({
        youtube_video_id: candidate.youtube_video_id,
        video_url: candidate.video_url,
        title: candidate.title,
        channel_name: candidate.channel_name,
        language: candidate.language,
        published_at: candidate.published_at,
        description: candidate.description,
      }));
  }

  async function addSelectedCandidates() {
    const state = getState();
    if (!state.selectedProfileId) {
      throw new Error("Select a project first.");
    }
    if (state.selectedSearchVideoIds.length === 0) {
      throw new Error("Select at least one candidate.");
    }
    const candidates = selectedCandidatePayload(state);
    if (candidates.length === 0) {
      throw new Error("Selected candidates are unavailable for adding.");
    }

    await request("/videos/bulk-add", {
      method: "POST",
      body: JSON.stringify({
        monitor_profile_id: state.selectedProfileId,
        candidates,
      }),
    });

    setState((previous) => ({
      ...previous,
      selectedSearchVideoIds: [],
    }));
    renderSearchCandidates();
    await refreshVideos();
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
          selectedSearchVideoIds: [],
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

    const addSelectedButton = getElement("add-selected-candidates-btn");
    if (addSelectedButton) {
      addSelectedButton.addEventListener("click", () => {
        void runTask(async () => {
          await addSelectedCandidates();
        }, "Selected candidates added.");
      });
    }

    const candidateList = getElement("search-candidate-list");
    if (candidateList) {
      candidateList.addEventListener("change", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLInputElement)) {
          return;
        }
        const youtubeVideoId = target.dataset.candidateVideoId;
        if (!youtubeVideoId) {
          return;
        }

        setState((previous) => {
          const isAlreadySelected = previous.selectedSearchVideoIds.includes(youtubeVideoId);
          const nextSelectedVideoIds =
            target.checked && !isAlreadySelected
              ? [...previous.selectedSearchVideoIds, youtubeVideoId]
              : previous.selectedSearchVideoIds.filter((item) => item !== youtubeVideoId);
          return {
            ...previous,
            selectedSearchVideoIds: nextSelectedVideoIds,
          };
        });
        renderSearchCandidates();
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
