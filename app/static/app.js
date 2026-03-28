/*
 * Legacy entrypoint placeholder.
 * Active frontend entrypoint is /static/main.js (ES module).
 */
function initialState() {
  return {
    profiles: [],
    selectedProfileId: null,
    videos: [],
    selectedVideoId: null,
    tokenInputs: {
      markets: [],
      languages: [],
    },
    transcriptExpanded: false,
  };
}

let state = initialState();
let analysisCache = {};
let chatCache = {};
let detailAbortController = null;
let messageTimer = null;

function normalizeAnalysisErrorMessage(rawMessage) {
  const message = String(rawMessage || "").trim();
  if (!message) {
    return "Analysis failed. Please try again.";
  }
  if (message.startsWith("GEMINI_NOT_READY:")) {
    return "Gemini is not ready. Configure GEMINI_API_KEY and restart the server.";
  }
  if (message.startsWith("TRANSCRIPT_BLOCKED:")) {
    return "Transcript provider rate-limited requests from this IP. Retry later.";
  }
  if (message.startsWith("TRANSCRIPT_UNAVAILABLE:")) {
    return "This video does not provide transcripts in requested languages.";
  }
  if (message.startsWith("TRANSCRIPT_PROVIDER_ERROR:")) {
    return "Transcript provider failed unexpectedly. Please retry in a moment.";
  }
  if (
    message.toLowerCase().includes("requires asr transcription") ||
    message.toLowerCase().includes("audio transcription is required")
  ) {
    return "This video does not expose captions. Transcript provider requires ASR transcription for this video.";
  }
  if (message.startsWith("Malformed transcript payload")) {
    return "Transcript provider returned an unsupported response. Please retry in a moment.";
  }
  if (message.startsWith("GEMINI_PROVIDER_ERROR:") || message.startsWith("GEMINI_RESPONSE_ERROR:")) {
    return "Gemini request failed. Check /health/gemini and server logs for details.";
  }
  return message;
}

function setState(patchOrUpdater) {
  state =
    typeof patchOrUpdater === "function"
      ? patchOrUpdater(state)
      : {
          ...state,
          ...patchOrUpdater,
        };
}

function splitCsv(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function normalizeSelectableValue(rawValue, type) {
  const value = (rawValue || "").trim();
  if (!value) {
    return "";
  }
  const match = value.match(/\(([^)]+)\)\s*$/);
  if (match && match[1]) {
    return type === "languages" ? match[1].toLowerCase() : match[1].toUpperCase();
  }
  return type === "languages" ? value.toLowerCase() : value;
}

function getElement(id) {
  return document.getElementById(id);
}

function debounce(callback, delayMs) {
  let timeoutId = null;
  return (...args) => {
    if (timeoutId) {
      window.clearTimeout(timeoutId);
    }
    timeoutId = window.setTimeout(() => callback(...args), delayMs);
  };
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

function clearMessage() {
  const messageEl = getElement("app-message");
  if (!messageEl) {
    return;
  }
  messageEl.classList.add("is-hidden");
  messageEl.classList.remove("error", "success");
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

async function request(path, options = {}) {
  const { headers = {}, ...rest } = options;
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...headers },
    ...rest,
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(errorPayload.detail || "Request failed");
  }

  return response.json();
}

function getSelectedVideo() {
  return state.videos.find((video) => video.id === state.selectedVideoId) || null;
}

function invalidateVideoCache(videoId) {
  const { [videoId]: _analysis, ...remainingAnalysis } = analysisCache;
  const { [videoId]: _chat, ...remainingChat } = chatCache;
  analysisCache = remainingAnalysis;
  chatCache = remainingChat;
}

function setCreatePanelVisible(isVisible) {
  const container = getElement("create-profile-container");
  const toggleButton = getElement("toggle-create-btn");
  if (!container || !toggleButton) {
    return;
  }
  container.classList.toggle("is-hidden", !isVisible);
  toggleButton.classList.toggle("is-hidden", isVisible);
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

function bindNav() {
  const buttons = Array.from(document.querySelectorAll(".nav-btn[data-section]"));
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      setActiveSection(button.dataset.section);
    });
  });
}

function profileCardMarkup(profile) {
  return `
    <article class="project-card">
      <div style="display: flex; justify-content: space-between; align-items: start;">
        <h4>${escapeHtml(profile.name)}</h4>
        <button class="icon-btn delete-project-btn" data-profile-id="${profile.id}" title="Delete Project" type="button">
          <span class="material-symbols-outlined" style="color: var(--danger); font-size: 1.2rem;">delete</span>
        </button>
      </div>
      <div class="meta" style="font-weight: 600; color: #5a6061; font-size: 0.8rem;">Keywords: ${escapeHtml(profile.brand_keywords.join(", "))}</div>
      <div class="chip-row" style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px;">
        ${profile.markets.map((market) => `<span class="badge" style="background: #f2f4f4; color: #5a6061; padding: 4px 10px; border-radius: 4px; font-size: 0.7rem; font-weight: 700;">${escapeHtml(market)}</span>`).join("")}
      </div>
      <div class="chip-row" style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px;">
        ${profile.languages.map((language) => `<span class="badge" style="background: #f2f4f4; color: #5a6061; padding: 4px 10px; border-radius: 4px; font-size: 0.7rem; font-weight: 700;">${escapeHtml(language)}</span>`).join("")}
      </div>
      <div style="margin-top: auto; padding-top: 16px; border-top: 1px solid #f1f1f1; display: flex; justify-content: flex-end;">
        <span class="badge" style="background: #dde4e5; color: #2d3435; padding: 6px 14px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; cursor: pointer; transition: background 0.2s;">Open Queue</span>
      </div>
    </article>
  `;
}

function renderProfileList() {
  const profileGrid = getElement("profile-grid");
  const profileSelect = getElement("profile-select");
  if (!profileGrid || !profileSelect) {
    return;
  }

  profileGrid.innerHTML = "";
  profileSelect.innerHTML = "";

  if (state.profiles.length === 0) {
    profileGrid.innerHTML =
      '<div class="video-detail-empty">No projects yet. Create one to start monitoring videos.</div>';
    profileSelect.disabled = true;
    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = "No projects available";
    profileSelect.appendChild(emptyOption);
    return;
  }

  profileSelect.disabled = false;
  state.profiles.forEach((profile) => {
    profileGrid.insertAdjacentHTML("beforeend", profileCardMarkup(profile));
    const option = document.createElement("option");
    option.value = String(profile.id);
    option.textContent = profile.name;
    profileSelect.appendChild(option);
  });

  const selectedId = state.selectedProfileId ?? state.profiles[0].id;
  profileSelect.value = String(selectedId);
}

async function loadProfiles() {
  const profiles = await request("/monitor-profiles");
  const hasCurrent = profiles.some((profile) => profile.id === state.selectedProfileId);
  const selectedProfileId =
    hasCurrent || profiles.length === 0 ? state.selectedProfileId : profiles[0].id;

  setState((previous) => ({
    ...previous,
    profiles,
    selectedProfileId,
  }));
  renderProfileList();
}

function queueStateBadge(queueState) {
  const normalized = String(queueState || "discovered");
  const label = normalized.charAt(0).toUpperCase() + normalized.slice(1);
  const isApproved = normalized === "approved";
  const badgeClass = isApproved ? "bg-on-background text-on-primary" : "bg-surface-container-highest text-on-surface-variant";
  return `<span class="px-2 py-0.5 ${badgeClass}" style="font-size: 0.625rem; font-weight: 700; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.05em;">${label}</span>`;
}

function renderVideoListItem(video) {
  const isActive = video.id === state.selectedVideoId;
  const scoreClass = video.relevance_score > 0.7 ? "positive" : "";
  return `
    <button class="video-item ${isActive ? "active" : ""}" data-video-id="${video.id}" type="button">
      <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
        ${queueStateBadge(video.queue_state)}
        <span class="text-[0.6875rem] text-on-surface-variant font-medium">12:45 PM</span>
      </div>
      <h4>${escapeHtml(video.title)}</h4>
      <p>${escapeHtml(video.channel_name)} • ${escapeHtml(video.language)}</p>
      <div style="display: flex; gap: 8px; margin-top: 12px;">
        <span class="badge" style="background: #f2f4f4; color: #5a6061; padding: 4px 10px; border-radius: 4px; font-size: 0.7rem; font-weight: 700;">Design</span>
        <span class="badge" style="background: #f2f4f4; color: #5a6061; padding: 4px 10px; border-radius: 4px; font-size: 0.7rem; font-weight: 700;">Culture</span>
      </div>
    </button>
  `;
}

function renderVideos() {
  const list = getElement("video-list");
  const count = getElement("video-count");
  if (!list || !count) {
    return;
  }

  count.textContent = String(state.videos.length);
  if (state.videos.length === 0) {
    list.innerHTML =
      '<div class="video-detail-empty">No candidates yet. Discover videos for the selected project.</div>';
    return;
  }
  list.innerHTML = state.videos.map((video) => renderVideoListItem(video)).join("");
}

function sentimentBadge(sentiment) {
  if (!sentiment) {
    return '<span class="badge">unknown</span>';
  }
  const css = sentiment === "negative" ? "negative" : sentiment === "positive" ? "positive" : "";
  return `<span class="badge ${css}">${escapeHtml(sentiment)}</span>`;
}

function transcriptMarkup(analysis) {
  const transcript = analysis ? analysis.transcript_text || "" : "";
  const expanded = state.transcriptExpanded;
  const buttonLabel = expanded ? "Collapse" : "Expand";
  const excerpt = expanded ? transcript : transcript.split("\n").slice(0, 24).join("\n");
  const bodyText = excerpt || "Run analysis after approval to generate a transcript.";
  return `
    <div class="detail-block">
      <h5>Transcript</h5>
      <div class="transcript-wrapper">
        <div class="transcript-toolbar">
          <span class="meta">${transcript ? `${transcript.length.toLocaleString()} characters` : "No transcript available yet"}</span>
          <button id="toggle-transcript-btn" class="btn btn-secondary" type="button">${buttonLabel}</button>
        </div>
        <pre class="transcript-body">${escapeHtml(bodyText)}</pre>
      </div>
    </div>
  `;
}

function evidenceText(analysis) {
  if (!analysis || !Array.isArray(analysis.evidence) || analysis.evidence.length === 0) {
    return "No evidence snippets yet.";
  }
  return analysis.evidence.map((item) => `${item.timestamp} - ${item.quote} (${item.reason})`).join("\n");
}

function videoDetailMarkup(video, analysis, analysisError) {
  const canAnalyze = video.queue_state === "approved";
  const riskLevel = analysis ? String(analysis.risk_level || "").toUpperCase() : "-";
  const normalizedRisk = analysis ? String(analysis.risk_level || "").toLowerCase() : "";
  const riskClass = normalizedRisk ? `risk-level risk-level-${normalizedRisk}` : "risk-level";

  return `
    <div class="video-detail-body">
      <div>
        <h3 class="video-detail-title">${escapeHtml(video.title)}</h3>
        <a class="video-link" href="${escapeHtml(video.video_url)}" target="_blank" rel="noreferrer">
          ${escapeHtml(video.video_url)} ↗
        </a>
        <div class="analysis-status">
          Queue state: <strong>${escapeHtml(video.queue_state)}</strong>
          ${analysis ? ` | Analysis: <strong>${escapeHtml(analysis.status)}</strong>` : ""}
        </div>
      </div>

      <div class="inline-actions">
        <button id="approve-btn" class="btn btn-secondary" type="button">Approve</button>
        <button id="reject-btn" class="btn btn-secondary" type="button">Reject</button>
        <button id="analyze-btn" class="btn btn-primary" type="button" ${canAnalyze ? "" : "disabled"}>
          ${canAnalyze ? "Run Analysis" : "Approve First"}
        </button>
        <button id="escalate-btn" class="btn btn-danger" type="button">Escalate</button>
        <button id="delete-video-btn" class="btn btn-danger" type="button" style="margin-left: auto;">Delete</button>
      </div>

      ${analysisError ? `<div class="meta" style="color: var(--danger);">${escapeHtml(analysisError)}</div>` : ""}

      <div class="detail-grid">
        <div class="detail-block">
          <h5>Summary</h5>
          <div>${escapeHtml(analysis ? analysis.summary_text : "No analysis yet.")}</div>
        </div>
        <div class="split-grid">
          <div class="detail-block">
            <h5>Sentiment</h5>
            <div>${analysis ? sentimentBadge(analysis.sentiment) : "-"}</div>
          </div>
          <div class="detail-block">
            <h5>Risk Level</h5>
            <div><strong class="${riskClass}">${escapeHtml(riskLevel)}</strong></div>
          </div>
        </div>
        ${transcriptMarkup(analysis)}
        <div class="detail-block">
          <h5>Evidence</h5>
          <pre class="transcript-body">${escapeHtml(evidenceText(analysis))}</pre>
        </div>
      </div>

      <div>
        <h5 style="margin: 0 0 8px;">Chat with Video AI</h5>
        <div id="chat-window" class="chat-window"></div>
        <div class="inline-actions" style="margin-top: 8px;">
          <input id="chat-question" type="text" placeholder="Ask about risk, tone, transcript details, or missing points..." style="flex: 1;" />
          <button id="send-chat-btn" class="btn btn-primary" type="button">Send</button>
        </div>
      </div>
    </div>
  `;
}

async function fetchAnalysis(videoId, forceRefresh = false) {
  if (!forceRefresh && analysisCache[videoId]) {
    return analysisCache[videoId];
  }

  if (detailAbortController) {
    detailAbortController.abort();
  }
  detailAbortController = new AbortController();

  const analysis = await request(`/videos/${videoId}/analysis`, {
    signal: detailAbortController.signal,
  });
  analysisCache = {
    ...analysisCache,
    [videoId]: analysis,
  };
  return analysis;
}

function renderVideoDetailEmpty(message) {
  const container = getElement("video-detail");
  if (!container) {
    return;
  }
  container.className = "video-detail-empty";
  container.textContent = message;
}

async function renderVideoDetail() {
  const selectedVideo = getSelectedVideo();
  if (!selectedVideo) {
    renderVideoDetailEmpty("Select a video to view analysis and chat.");
    return;
  }

  const container = getElement("video-detail");
  if (!container) {
    return;
  }

  container.className = "";
  container.innerHTML = '<div class="video-detail-body"><div class="meta">Loading detail...</div></div>';

  const renderTargetId = selectedVideo.id;
  let analysis = null;
  let analysisError = "";

  try {
    analysis = await fetchAnalysis(renderTargetId);
    if (analysis && String(analysis.status || "").toLowerCase() === "failed") {
      const persistedError = String(analysis.error_message || "").trim();
      if (persistedError) {
        analysisError = normalizeAnalysisErrorMessage(persistedError);
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return;
    }
    const errorMessage = error instanceof Error ? error.message : "Failed to load analysis.";
    analysisError = normalizeAnalysisErrorMessage(errorMessage);
  }

  if (renderTargetId !== state.selectedVideoId) {
    return;
  }

  container.innerHTML = videoDetailMarkup(selectedVideo, analysis, analysisError);
  bindDetailActions(selectedVideo.id, selectedVideo.queue_state === "approved");
  await renderChat(selectedVideo.id);
}

async function fetchChat(videoId, forceRefresh = false) {
  if (!forceRefresh && chatCache[videoId]) {
    return chatCache[videoId];
  }
  const messages = await request(`/videos/${videoId}/chat`);
  chatCache = {
    ...chatCache,
    [videoId]: messages,
  };
  return messages;
}

function renderChatEntries(messages) {
  if (!messages || messages.length === 0) {
    return '<div class="meta">No chat history yet. Ask a question to begin.</div>';
  }

  return messages
    .map((message) => {
      const citationText =
        Array.isArray(message.citations) && message.citations.length > 0
          ? ` (citations: ${message.citations.map((item) => item.timestamp).join(", ")})`
          : "";
      const role = escapeHtml(message.role);
      const roleClass = role === "assistant" ? "assistant" : "user";
      return `
        <div class="chat-entry ${roleClass}">
          <div class="chat-entry-label">${role}</div>
          <div class="chat-entry-bubble">${escapeHtml(message.content)}${escapeHtml(citationText)}</div>
        </div>
      `;
    })
    .join("");
}

async function renderChat(videoId) {
  const chatWindow = getElement("chat-window");
  if (!chatWindow) {
    return;
  }
  try {
    const messages = await fetchChat(videoId);
    chatWindow.innerHTML = renderChatEntries(messages);
    chatWindow.scrollTop = chatWindow.scrollHeight;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to load chat.";
    chatWindow.innerHTML = `<div class="meta" style="color: var(--danger);">${escapeHtml(message)}</div>`;
  }
}

function bindDetailActions(videoId, canAnalyze) {
  const transcriptToggle = getElement("toggle-transcript-btn");
  if (transcriptToggle) {
    transcriptToggle.onclick = () => {
      setState((previous) => ({
        ...previous,
        transcriptExpanded: !previous.transcriptExpanded,
      }));
      void renderVideoDetail();
    };
  }

  const approveButton = getElement("approve-btn");
  if (approveButton) {
    approveButton.onclick = () =>
      runTask(async () => {
        await request(`/videos/${videoId}/approve`, {
          method: "POST",
          body: JSON.stringify({ approved: true }),
        });
        invalidateVideoCache(videoId);
        await refreshVideos();
      }, "Video approved.");
  }

  const rejectButton = getElement("reject-btn");
  if (rejectButton) {
    rejectButton.onclick = () =>
      runTask(async () => {
        await request(`/videos/${videoId}/approve`, {
          method: "POST",
          body: JSON.stringify({ approved: false }),
        });
        invalidateVideoCache(videoId);
        await refreshVideos();
      }, "Video rejected.");
  }

  const analyzeButton = getElement("analyze-btn");
  if (analyzeButton) {
    analyzeButton.onclick = () =>
      runTask(async () => {
        if (!canAnalyze) {
          return;
        }
        const originalLabel = analyzeButton.textContent;
        analyzeButton.disabled = true;
        analyzeButton.textContent = "Analyzing...";
        try {
          await request(`/videos/${videoId}/analyze`, {
            method: "POST",
            body: JSON.stringify({ force_reanalyze: true }),
          });
          invalidateVideoCache(videoId);
          await renderVideoDetail();
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : "Analysis failed.";
          throw new Error(normalizeAnalysisErrorMessage(errorMessage));
        } finally {
          analyzeButton.disabled = false;
          analyzeButton.textContent = originalLabel || "Run Analysis";
        }
      }, "Analysis refreshed.");
  }

  const escalateButton = getElement("escalate-btn");
  if (escalateButton) {
    escalateButton.onclick = () =>
      runTask(async () => {
        await request(`/videos/${videoId}/escalate`, {
          method: "POST",
          body: JSON.stringify({ owner: "marketing-owner", notes: "Escalated from dashboard" }),
        });
        await loadAlerts();
      }, "Escalated and alert generated.");
  }

  const deleteVideoButton = getElement("delete-video-btn");
  if (deleteVideoButton) {
    deleteVideoButton.onclick = () =>
      runTask(async () => {
        if (!window.confirm("Are you sure you want to delete this video? This action cannot be undone.")) {
          return;
        }
        await request(`/videos/${videoId}`, {
          method: "DELETE",
        });
        invalidateVideoCache(videoId);
        setState((previous) => ({
          ...previous,
          selectedVideoId: null,
        }));
        await refreshVideos();
      }, "Video deleted.");
  }

  const sendChatButton = getElement("send-chat-btn");
  if (sendChatButton) {
    sendChatButton.onclick = () =>
      runTask(async () => {
        const questionInput = getElement("chat-question");
        if (!questionInput) {
          return;
        }
        const question = questionInput.value.trim();
        if (!question) {
          throw new Error("Type a question before sending.");
        }
        await request(`/videos/${videoId}/chat`, {
          method: "POST",
          body: JSON.stringify({ question, user_id: "marketing-owner" }),
        });
        questionInput.value = "";
        const { [videoId]: _removed, ...remainingChats } = chatCache;
        chatCache = remainingChats;
        await renderChat(videoId);
      });
  }
}

function selectVideo(videoId) {
  setState((previous) => ({
    ...previous,
    selectedVideoId: videoId,
    transcriptExpanded: false,
  }));
  renderVideos();
  void renderVideoDetail();
}

async function discoverVideos() {
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
  analysisCache = {};
  chatCache = {};
  await refreshVideos();
}

async function addManualVideo() {
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

async function refreshVideos() {
  if (!state.selectedProfileId) {
    setState((previous) => ({
      ...previous,
      videos: [],
      selectedVideoId: null,
    }));
    renderVideos();
    renderVideoDetailEmpty("Select a project to load queue candidates.");
    return;
  }

  const titleFilter = (getElement("title-filter")?.value || "").trim();
  const query = new URLSearchParams();
  query.set("monitor_profile_id", String(state.selectedProfileId));
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
  await renderVideoDetail();
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

function renderTokenList(type) {
  const tokenContainer = getElement(`${type}-tokens`);
  const hiddenInput = getElement(`${type}-hidden`);
  if (!tokenContainer || !hiddenInput) {
    return;
  }

  const values = state.tokenInputs[type];
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
      [type]: previous.tokenInputs[type].filter((_, currentIndex) => currentIndex !== index),
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
  const profileGrid = getElement("profile-grid");
  if (profileGrid) {
    profileGrid.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      const deleteBtn = target.closest(".delete-project-btn");
      if (deleteBtn instanceof HTMLElement) {
        event.stopPropagation();
        const profileId = Number(deleteBtn.dataset.profileId);
        if (Number.isNaN(profileId)) {
          return;
        }
        void runTask(async () => {
          if (!window.confirm("Are you sure you want to delete this project? All associated videos and data will be lost.")) {
            return;
          }
          await request(`/monitor-profiles/${profileId}`, {
            method: "DELETE",
          });
          if (state.selectedProfileId === profileId) {
            setState((previous) => ({
              ...previous,
              selectedProfileId: null,
              selectedVideoId: null,
              videos: [],
            }));
          }
          await loadProfiles();
          await refreshVideos();
        }, "Project deleted.");
      }
    });
  }

  const toggleButton = getElement("toggle-create-btn");
  if (toggleButton) {
    toggleButton.addEventListener("click", () => {
      setCreatePanelVisible(true);
    });
  }

  const cancelButton = getElement("cancel-create-btn");
  if (cancelButton) {
    cancelButton.addEventListener("click", () => {
      setCreatePanelVisible(false);
    });
  }
}

function bindQueueInteractions() {
  const videoList = getElement("video-list");
  if (videoList) {
    videoList.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      const button = target.closest(".video-item");
      if (!(button instanceof HTMLElement)) {
        return;
      }
      const videoId = Number(button.dataset.videoId);
      if (Number.isNaN(videoId)) {
        return;
      }
      selectVideo(videoId);
    });
  }

  const profileSelect = getElement("profile-select");
  if (profileSelect) {
    profileSelect.addEventListener("change", () => {
      const parsedProfileId = Number(profileSelect.value);
      setState((previous) => ({
        ...previous,
        selectedProfileId: Number.isNaN(parsedProfileId) ? null : parsedProfileId,
        selectedVideoId: null,
      }));
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

  const titleFilterInput = getElement("title-filter");
  if (titleFilterInput) {
    const debouncedRefresh = debounce(() => {
      void runTask(async () => {
        await refreshVideos();
      });
    }, 240);
    titleFilterInput.addEventListener("input", () => {
      debouncedRefresh();
    });
  }
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

function bindProfileForm() {
  const profileForm = getElement("profile-form");
  if (!profileForm) {
    return;
  }

  profileForm.addEventListener("submit", (event) => {
    event.preventDefault();
    void runTask(async () => {
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
      await refreshVideos();
    }, "Project created.");
  });
}

async function bootstrap() {
  bindNav();
  bindDashboardControls();
  bindTokenInputs();
  bindQueueInteractions();
  bindAlertsControls();
  bindProfileForm();

  setCreatePanelVisible(false);
  await loadProfiles();
  await refreshVideos();
  await loadAlerts();
}

bootstrap().catch((error) => {
  const message = error instanceof Error ? error.message : "Unexpected startup failure.";
  showMessage(message, "error");
});
