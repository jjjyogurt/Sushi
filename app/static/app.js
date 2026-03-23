const state = {
  profiles: [],
  videos: [],
  selectedVideo: null,
  tokenInputs: {
    markets: [],
    languages: [],
  },
  transcriptExpanded: false,
};

function splitCsv(value) {
  return value
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

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || "Request failed");
  }
  return response.json();
}

function bindNav() {
  const buttons = document.querySelectorAll(".nav-btn");
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      buttons.forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      document.querySelectorAll(".panel").forEach((panel) => panel.classList.remove("active"));
      document.getElementById(button.dataset.section).classList.add("active");
    });
  });
}

function renderProfileList() {
  const list = document.getElementById("profile-list");
  const select = document.getElementById("profile-select");
  list.innerHTML = "";
  select.innerHTML = "";
  state.profiles.forEach((profile) => {
    const item = document.createElement("li");
    item.className = "list-item";
    item.innerHTML = `
      <div style="font-weight: 600; font-size: 0.875rem;">${escapeHtml(profile.name)}</div>
      <div class="meta" style="margin-top: 4px;">
        <span class="badge">Keywords</span> ${escapeHtml(profile.brand_keywords.join(", "))}
      </div>
      <div class="meta" style="margin-top: 2px;">
        <span class="badge">Markets</span> ${escapeHtml(profile.markets.join(", "))} |
        <span class="badge">Languages</span> ${escapeHtml(profile.languages.join(", "))}
      </div>`;
    list.appendChild(item);

    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = `${profile.name} (#${profile.id})`;
    select.appendChild(option);
  });
}

async function loadProfiles() {
  state.profiles = await request("/monitor-profiles");
  renderProfileList();
}

function renderVideos() {
  const list = document.getElementById("video-list");
  list.innerHTML = "";
  state.videos.forEach((video) => {
    const item = document.createElement("li");
    item.className = "list-item";
    item.innerHTML = `
      <div style="font-weight: 600; font-size: 0.875rem;">${escapeHtml(video.title)}</div>
      <div class="meta" style="margin-top: 4px;">
        ${escapeHtml(video.channel_name)} • ${escapeHtml(video.language)} •
        <span class="badge ${video.relevance_score > 0.7 ? "positive" : ""}">Score ${video.relevance_score.toFixed(2)}</span>
      </div>
      <div class="meta" style="margin-top: 2px; opacity: 0.7;">
        Status: ${escapeHtml(video.queue_state)}
      </div>`;
    item.addEventListener("click", () => {
      state.selectedVideo = video;
      state.transcriptExpanded = false;
      renderVideoDetail();
    });
    list.appendChild(item);
  });
}

function sentimentBadge(sentiment) {
  if (!sentiment) {
    return "";
  }
  const css = sentiment === "negative" ? "negative" : sentiment === "positive" ? "positive" : "";
  return `<span class="badge ${css}">${escapeHtml(sentiment)}</span>`;
}

function renderTranscriptBlock(analysis) {
  const transcript = analysis ? analysis.transcript_text || "" : "";
  const expanded = state.transcriptExpanded;
  const buttonLabel = expanded ? "Collapse" : "Expand";
  const transcriptPreview = expanded ? transcript : transcript.split("\n").slice(0, 24).join("\n");
  return `
    <div class="card" style="margin-bottom: 0;">
      <label>Transcript</label>
      <div class="transcript-wrapper" style="margin-top: 8px;">
        <div class="transcript-toolbar">
          <span class="meta">${transcript ? `${transcript.length.toLocaleString()} characters` : "No transcript available yet"}</span>
          <button id="toggle-transcript-btn">${buttonLabel}</button>
        </div>
        <pre class="transcript-body">${escapeHtml(transcriptPreview || "Run analysis after approval to generate a transcript.")}</pre>
      </div>
    </div>
  `;
}

function renderEvidence(analysis) {
  if (!analysis || !analysis.evidence || analysis.evidence.length === 0) {
    return "[]";
  }
  return analysis.evidence.map((item) => `${item.timestamp} - ${item.quote} (${item.reason})`).join("\n");
}

async function renderVideoDetail() {
  const container = document.getElementById("video-detail");
  if (!state.selectedVideo) {
    container.textContent = "Select a video to view analysis and chat.";
    return;
  }

  const selected = state.selectedVideo;
  let analysis = null;
  let analysisError = "";
  try {
    analysis = await request(`/videos/${selected.id}/analysis`);
  } catch (error) {
    analysisError = error.message;
  }

  const canAnalyze = selected.queue_state === "approved";
  container.innerHTML = `
    <h3 style="border:none; margin-bottom: 8px;">${escapeHtml(selected.title)}</h3>
    <div class="meta" style="margin-bottom: 8px;">
      <a href="${escapeHtml(selected.video_url)}" target="_blank" style="color: var(--accent); text-decoration: none;">${escapeHtml(selected.video_url)} ↗</a>
    </div>
    <div class="analysis-status">
      Queue state: <strong>${escapeHtml(selected.queue_state)}</strong>
      ${analysis ? `| Analysis: <strong>${escapeHtml(analysis.status)}</strong>` : ""}
    </div>

    <div class="inline-actions" style="margin-top: 14px; margin-bottom: 22px;">
      <button id="approve-btn">Approve</button>
      <button id="reject-btn">Reject</button>
      <button id="analyze-btn" ${canAnalyze ? "" : "disabled"}>${canAnalyze ? "Run Analysis" : "Approve First"}</button>
      <button id="escalate-btn" style="color: var(--danger);">Escalate</button>
    </div>

    ${analysisError ? `<div class="meta" style="color: var(--danger); margin-bottom: 16px;">${escapeHtml(analysisError)}</div>` : ""}

    <div style="display: grid; gap: 20px; margin-bottom: 28px;">
      <div class="card" style="margin-bottom: 0;">
        <label>Summary</label>
        <div style="font-size: 0.95rem; margin-top: 8px; line-height: 1.6;">${escapeHtml(
          analysis ? analysis.summary_text : "No analysis yet."
        )}</div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
        <div class="card" style="margin-bottom: 0;">
          <label>Sentiment</label>
          <div style="margin-top: 8px;">${analysis ? sentimentBadge(analysis.sentiment) : "-"}</div>
        </div>
        <div class="card" style="margin-bottom: 0;">
          <label>Risk Level</label>
          <div style="margin-top: 8px; font-weight: 600; color: ${
            analysis && analysis.risk_level === "high" ? "var(--danger)" : "var(--text)"
          }">${analysis ? escapeHtml(analysis.risk_level.toUpperCase()) : "-"}</div>
        </div>
      </div>

      ${renderTranscriptBlock(analysis)}

      <div class="card" style="margin-bottom: 0;">
        <label>Evidence</label>
        <pre class="transcript-body" style="max-height: 180px;">${escapeHtml(renderEvidence(analysis))}</pre>
      </div>
    </div>

    <h4 style="font-size: 1.1rem; margin-bottom: 16px;">Chat with Video AI</h4>
    <div class="chat-window" id="chat-window"></div>
    <div class="inline-actions" style="display: flex; gap: 8px;">
      <input id="chat-question" type="text" placeholder="Ask about risk, tone, transcript details, or missing points..." style="flex: 1;" />
      <button id="send-chat-btn" style="background: var(--text); color: white; border: none;">Send</button>
    </div>
  `;
  bindDetailActions(selected.id, canAnalyze);
  await renderChat(selected.id);
}

async function renderChat(videoId) {
  const chatWindow = document.getElementById("chat-window");
  if (!chatWindow) {
    return;
  }
  const messages = await request(`/videos/${videoId}/chat`);
  chatWindow.innerHTML = "";
  messages.forEach((message) => {
    const entry = document.createElement("div");
    entry.className = "chat-entry";
    const citationText =
      message.citations && message.citations.length > 0
        ? ` (citations: ${message.citations.map((item) => item.timestamp).join(", ")})`
        : "";
    entry.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 4px;">
        <strong style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">${escapeHtml(message.role)}</strong>
        <div style="background: ${message.role === "assistant" ? "var(--sidebar-bg)" : "white"}; padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border);">
          ${escapeHtml(message.content)}${escapeHtml(citationText)}
        </div>
      </div>`;
    chatWindow.appendChild(entry);
  });
}

function bindDetailActions(videoId, canAnalyze) {
  const transcriptToggle = document.getElementById("toggle-transcript-btn");
  if (transcriptToggle) {
    transcriptToggle.onclick = async () => {
      state.transcriptExpanded = !state.transcriptExpanded;
      await renderVideoDetail();
    };
  }

  document.getElementById("approve-btn").onclick = async () => {
    await request(`/videos/${videoId}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved: true }),
    });
    await refreshVideos();
    state.selectedVideo = state.videos.find((item) => item.id === videoId) || state.selectedVideo;
    await renderVideoDetail();
  };
  document.getElementById("reject-btn").onclick = async () => {
    await request(`/videos/${videoId}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved: false }),
    });
    await refreshVideos();
    state.selectedVideo = state.videos.find((item) => item.id === videoId) || state.selectedVideo;
    await renderVideoDetail();
  };
  document.getElementById("analyze-btn").onclick = async (event) => {
    if (!canAnalyze) {
      return;
    }
    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = "Analyzing...";
    try {
      await request(`/videos/${videoId}/analyze`, {
        method: "POST",
        body: JSON.stringify({ force_reanalyze: false }),
      });
    } finally {
      await renderVideoDetail();
    }
  };
  document.getElementById("escalate-btn").onclick = async () => {
    await request(`/videos/${videoId}/escalate`, {
      method: "POST",
      body: JSON.stringify({ owner: "marketing-owner", notes: "Escalated from dashboard" }),
    });
    await loadAlerts();
    window.alert("Escalated and alert generated.");
  };
  document.getElementById("send-chat-btn").onclick = async () => {
    const questionInput = document.getElementById("chat-question");
    const question = questionInput.value;
    if (!question.trim()) {
      return;
    }
    await request(`/videos/${videoId}/chat`, {
      method: "POST",
      body: JSON.stringify({ question, user_id: "marketing-owner" }),
    });
    questionInput.value = "";
    await renderChat(videoId);
  };
}

async function discoverVideos() {
  const profileId = Number(document.getElementById("profile-select").value);
  if (!profileId) {
    throw new Error("Select a profile first.");
  }
  await request("/videos/discover", {
    method: "POST",
    body: JSON.stringify({ monitor_profile_id: profileId, max_results: 20 }),
  });
  await refreshVideos();
}

async function addManualVideo() {
  const profileId = Number(document.getElementById("profile-select").value);
  if (!profileId) {
    throw new Error("Select a profile first.");
  }
  const urlInput = document.getElementById("manual-video-url");
  const videoUrl = urlInput.value.trim();
  if (!videoUrl) {
    throw new Error("Paste a YouTube URL first.");
  }
  await request("/videos/manual", {
    method: "POST",
    body: JSON.stringify({
      monitor_profile_id: profileId,
      video_url: videoUrl,
      language: state.tokenInputs.languages[0] || "en",
    }),
  });
  urlInput.value = "";
  await refreshVideos();
}

async function refreshVideos() {
  const profileId = document.getElementById("profile-select").value;
  const title = document.getElementById("title-filter").value.trim();
  const query = new URLSearchParams();
  if (profileId) {
    query.set("monitor_profile_id", profileId);
  }
  if (title) {
    query.set("title", title);
  }
  const data = await request(`/videos?${query.toString()}`);
  state.videos = data.items;
  renderVideos();
}

async function loadAlerts() {
  const list = document.getElementById("alerts-list");
  const data = await request("/alerts");
  list.innerHTML = "";
  data.items.forEach((alert) => {
    const item = document.createElement("li");
    item.className = "list-item";
    item.style.borderLeft = "4px solid var(--danger)";
    item.style.paddingLeft = "16px";
    item.innerHTML = `
      <div style="font-weight: 500; font-size: 0.9rem;">${escapeHtml(alert.message)}</div>
      <div class="meta" style="margin-top: 4px;">Channel: ${escapeHtml(alert.channel)}</div>`;
    list.appendChild(item);
  });
}

function renderTokenList(type) {
  const tokenContainer = document.getElementById(`${type}-tokens`);
  const hiddenInput = document.getElementById(`${type}-hidden`);
  const values = state.tokenInputs[type];
  tokenContainer.innerHTML = "";
  values.forEach((value, index) => {
    const chip = document.createElement("span");
    chip.className = "token";
    chip.innerHTML = `${escapeHtml(value)} <button data-type="${type}" data-index="${index}" type="button">x</button>`;
    tokenContainer.appendChild(chip);
  });
  hiddenInput.value = values.join(",");
}

function addToken(type, rawValue) {
  const normalized = normalizeSelectableValue(rawValue, type);
  if (!normalized) {
    return;
  }
  if (state.tokenInputs[type].includes(normalized)) {
    return;
  }
  state.tokenInputs[type] = [...state.tokenInputs[type], normalized];
  renderTokenList(type);
}

function removeToken(type, index) {
  state.tokenInputs[type] = state.tokenInputs[type].filter((_, itemIndex) => itemIndex !== index);
  renderTokenList(type);
}

function bindTokenInputs() {
  ["markets", "languages"].forEach((type) => {
    const input = document.getElementById(`${type}-token-input`);
    const tokenContainer = document.getElementById(`${type}-tokens`);
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
      if (target.tagName !== "BUTTON") {
        return;
      }
      const selectedType = target.getAttribute("data-type");
      const selectedIndex = Number(target.getAttribute("data-index"));
      removeToken(selectedType, selectedIndex);
    });
    renderTokenList(type);
  });
}

function bindForms() {
  document.getElementById("profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.target);
    if (state.tokenInputs.markets.length === 0) {
      throw new Error("Please add at least one market.");
    }
    if (state.tokenInputs.languages.length === 0) {
      throw new Error("Please add at least one language.");
    }
    await request("/monitor-profiles", {
      method: "POST",
      body: JSON.stringify({
        name: formData.get("name"),
        brand_keywords: splitCsv(formData.get("brand_keywords")),
        markets: [...state.tokenInputs.markets],
        languages: [...state.tokenInputs.languages],
        alert_sensitivity: formData.get("alert_sensitivity"),
      }),
    });
    event.target.reset();
    state.tokenInputs.markets = [];
    state.tokenInputs.languages = [];
    renderTokenList("markets");
    renderTokenList("languages");
    await loadProfiles();
  });

  document.getElementById("discover-btn").addEventListener("click", async () => {
    await discoverVideos();
  });

  document.getElementById("refresh-videos-btn").addEventListener("click", async () => {
    await refreshVideos();
  });

  document.getElementById("add-manual-video-btn").addEventListener("click", async () => {
    await addManualVideo();
  });

  document.getElementById("refresh-alerts-btn").addEventListener("click", async () => {
    await loadAlerts();
  });
}

async function bootstrap() {
  bindNav();
  bindTokenInputs();
  bindForms();
  await loadProfiles();
  await loadAlerts();
}

bootstrap().catch((error) => {
  window.alert(error.message);
});
