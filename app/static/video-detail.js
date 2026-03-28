import { escapeHtml, getElement } from "./ui-utils.js";

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

function extractVideoId(videoUrl) {
  if (!videoUrl) {
    return "";
  }
  try {
    const parsedUrl = new URL(videoUrl);
    if (parsedUrl.hostname.includes("youtu.be")) {
      return parsedUrl.pathname.replace("/", "");
    }
    if (parsedUrl.hostname.includes("youtube.com")) {
      return parsedUrl.searchParams.get("v") || "";
    }
    return "";
  } catch (_error) {
    return "";
  }
}

function sentimentBadge(sentiment) {
  if (!sentiment) {
    return '<span class="badge">unknown</span>';
  }
  const css = sentiment === "negative" ? "negative" : sentiment === "positive" ? "positive" : "";
  return `<span class="badge ${css}">${escapeHtml(sentiment)}</span>`;
}

function transcriptMarkup(analysis, transcriptExpanded) {
  const transcript = analysis ? analysis.transcript_text || "" : "";
  const buttonLabel = transcriptExpanded ? "Collapse" : "Expand";
  const excerpt = transcriptExpanded ? transcript : transcript.split("\n").slice(0, 24).join("\n");
  const bodyText = excerpt || "Run analysis to generate a transcript.";
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

function summaryMarkup(analysis) {
  if (!analysis) {
    return "No analysis yet.";
  }
  const headline = String(analysis.summary_headline || "").trim();
  const body = String(analysis.summary_body || "").trim();
  const businessImpact = String(analysis.business_impact || "").trim();
  if (!headline && !body && !businessImpact) {
    return escapeHtml(String(analysis.summary_text || "").trim() || "No analysis yet.");
  }

  return `
    <div class="summary-structured">
      ${headline ? `<div class="summary-headline">${escapeHtml(headline)}</div>` : ""}
      ${body ? `<div class="summary-body">${escapeHtml(body)}</div>` : ""}
      ${businessImpact ? `<div class="summary-impact"><strong>Business impact:</strong> ${escapeHtml(businessImpact)}</div>` : ""}
    </div>
  `;
}

function pointListMarkup(points, emptyLabel) {
  if (!Array.isArray(points) || points.length === 0) {
    return `<div class="meta">${escapeHtml(emptyLabel)}</div>`;
  }
  return `
    <ul class="point-list">
      ${points.map((point) => `<li>${escapeHtml(String(point))}</li>`).join("")}
    </ul>
  `;
}

function influencerSignalMarkup(analysis) {
  const praisePoints = analysis ? analysis.praise_points || [] : [];
  const criticismPoints = analysis ? analysis.criticism_points || [] : [];
  return `
    <div class="detail-block">
      <h5>Influencer Signal</h5>
      <div class="signal-grid">
        <div>
          <div class="signal-label">Praise</div>
          ${pointListMarkup(praisePoints, "No praise points yet.")}
        </div>
        <div>
          <div class="signal-label">Criticism</div>
          ${pointListMarkup(criticismPoints, "No criticism points yet.")}
        </div>
      </div>
    </div>
  `;
}

function actionRecommendationMarkup(analysis) {
  const recommendation = analysis ? String(analysis.action_recommendation || "").trim() : "";
  return `
    <div class="detail-block">
      <h5>Action Recommendation</h5>
      <div class="recommendation-body">${escapeHtml(recommendation || "No recommendation yet.")}</div>
    </div>
  `;
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

function analysisStatusLabel(analysis) {
  if (!analysis) {
    return "Not started";
  }
  const statusValue = String(analysis.status || "").trim();
  if (!statusValue) {
    return "Unknown";
  }
  return statusValue.charAt(0).toUpperCase() + statusValue.slice(1);
}

function videoDetailMarkup({ video, analysis, analysisError, transcriptExpanded, isRerunning }) {
  const riskLevel = analysis ? String(analysis.risk_level || "").toUpperCase() : "-";
  const normalizedRisk = analysis ? String(analysis.risk_level || "").toLowerCase() : "";
  const riskClass = normalizedRisk ? `risk-level risk-level-${normalizedRisk}` : "risk-level";
  const videoId = extractVideoId(video.video_url);
  const embedMarkup = videoId
    ? `<iframe class="video-embed" src="https://www.youtube.com/embed/${escapeHtml(
        videoId
      )}" title="${escapeHtml(video.title)}" loading="lazy" allowfullscreen></iframe>`
    : "";

  return `
    <div class="video-detail-body">
      <div>
        <h3 class="video-detail-title">${escapeHtml(video.title)}</h3>
        <a class="video-link" href="${escapeHtml(video.video_url)}" target="_blank" rel="noreferrer">
          ${escapeHtml(video.video_url)} ↗
        </a>
        <div class="analysis-status">
          Analysis status: <strong>${escapeHtml(analysisStatusLabel(analysis))}</strong>
        </div>
      </div>

      ${embedMarkup}

      <div class="inline-actions">
        <button id="analyze-btn" class="btn btn-primary" type="button">${isRerunning ? "Re-running..." : analysis ? "Re-run Analysis" : "Run Analysis"}</button>
        <button id="escalate-btn" class="btn btn-danger" type="button">Escalate</button>
        <button id="delete-video-btn" class="btn btn-secondary" type="button">Delete</button>
      </div>

      ${analysisError ? `<div class="meta" style="color: var(--danger);">${escapeHtml(analysisError)}</div>` : ""}

      <div class="detail-grid">
        <div class="detail-block">
          <h5>Summary</h5>
          <div>${summaryMarkup(analysis)}</div>
        </div>
        <div class="split-grid">
          <div class="detail-block">
            <h5>Sentiment</h5>
            <div>${analysis ? sentimentBadge(analysis.sentiment) : '<span class="badge">unknown</span>'}</div>
          </div>
          <div class="detail-block">
            <h5>Risk Level</h5>
            <div><strong class="${riskClass}">${escapeHtml(riskLevel)}</strong></div>
          </div>
        </div>
        ${influencerSignalMarkup(analysis)}
        ${actionRecommendationMarkup(analysis)}
        ${transcriptMarkup(analysis, transcriptExpanded)}
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

export function createVideoDetailController({
  getState,
  setState,
  request,
  runTask,
  onVideosChanged,
  onAlertsChanged,
}) {
  let analysisCache = {};
  let chatCache = {};
  let rerunStateByVideoId = {};
  let detailAbortController = null;

  function getSelectedVideo() {
    const state = getState();
    return state.videos.find((video) => video.id === state.selectedVideoId) || null;
  }

  function invalidateVideoCache(videoId) {
    const { [videoId]: _analysis, ...remainingAnalysis } = analysisCache;
    const { [videoId]: _chat, ...remainingChat } = chatCache;
    const { [videoId]: _rerun, ...remainingRerun } = rerunStateByVideoId;
    analysisCache = remainingAnalysis;
    chatCache = remainingChat;
    rerunStateByVideoId = remainingRerun;
  }

  function transientProcessingAnalysis() {
    return {
      status: "processing",
      summary_text: "",
      summary_headline: "",
      summary_body: "",
      business_impact: "",
      transcript_text: "",
      sentiment: "neutral",
      risk_level: "low",
      evidence: [],
      praise_points: [],
      criticism_points: [],
      action_recommendation: "",
    };
  }

  function renderVideoDetailEmpty(message) {
    const container = getElement("video-detail");
    if (!container) {
      return;
    }
    container.className = "video-detail-empty";
    container.innerHTML = `
      <div class="empty-state-content">
        <h3>No Video Selected</h3>
        <p>${escapeHtml(message)}</p>
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

  async function fetchChat(videoId, forceRefresh = false) {
    if (!forceRefresh && chatCache[videoId]) {
      return chatCache[videoId];
    }
    const messages = await request(`/videos/${videoId}/chat?user_id=marketing-owner`);
    chatCache = {
      ...chatCache,
      [videoId]: messages,
    };
    return messages;
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

  function bindDetailActions(videoId) {
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

    const analyzeButton = getElement("analyze-btn");
    if (analyzeButton) {
      analyzeButton.onclick = () =>
        runTask(async () => {
          const originalLabel = analyzeButton.textContent;
          analyzeButton.disabled = true;
          analyzeButton.textContent = "Re-running...";
          rerunStateByVideoId = {
            ...rerunStateByVideoId,
            [videoId]: true,
          };
          analysisCache = {
            ...analysisCache,
            [videoId]: transientProcessingAnalysis(),
          };
          await renderVideoDetail();
          try {
            await request(`/videos/${videoId}/analyze`, {
              method: "POST",
              body: JSON.stringify({ force_reanalyze: true }),
            });
            rerunStateByVideoId = {
              ...rerunStateByVideoId,
              [videoId]: false,
            };
            const { [videoId]: _ignored, ...remainingAnalysis } = analysisCache;
            analysisCache = remainingAnalysis;
            await renderVideoDetail();
          } catch (error) {
            rerunStateByVideoId = {
              ...rerunStateByVideoId,
              [videoId]: false,
            };
            const { [videoId]: _ignored, ...remainingAnalysis } = analysisCache;
            analysisCache = remainingAnalysis;
            await renderVideoDetail();
            const errorMessage = error instanceof Error ? error.message : "Analysis failed.";
            throw new Error(normalizeAnalysisErrorMessage(errorMessage));
          } finally {
            analyzeButton.disabled = false;
            analyzeButton.textContent = originalLabel || "Re-run Analysis";
          }
        }, "Analysis rerun completed.");
    }

    const escalateButton = getElement("escalate-btn");
    if (escalateButton) {
      escalateButton.onclick = () =>
        runTask(async () => {
          await request(`/videos/${videoId}/escalate`, {
            method: "POST",
            body: JSON.stringify({ owner: "marketing-owner", notes: "Escalated from dashboard" }),
          });
          await onAlertsChanged();
        }, "Escalated and alert generated.");
    }

    const deleteButton = getElement("delete-video-btn");
    if (deleteButton) {
      deleteButton.onclick = () =>
        runTask(async () => {
          await request(`/videos/${videoId}`, { method: "DELETE" });
          invalidateVideoCache(videoId);
          await onVideosChanged();
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

  async function renderVideoDetail() {
    const selectedVideo = getSelectedVideo();
    if (!selectedVideo) {
      renderVideoDetailEmpty("Select a video to view summary, transcript, and AI chat.");
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
    const state = getState();

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
      if (!errorMessage.includes("Analysis not found")) {
        analysisError = normalizeAnalysisErrorMessage(errorMessage);
      }
    }

    if (renderTargetId !== getState().selectedVideoId) {
      return;
    }

    container.innerHTML = videoDetailMarkup({
      video: selectedVideo,
      analysis,
      analysisError,
      transcriptExpanded: state.transcriptExpanded,
      isRerunning: Boolean(rerunStateByVideoId[selectedVideo.id]),
    });
    bindDetailActions(selectedVideo.id);
    await renderChat(selectedVideo.id);
  }

  return {
    renderVideoDetail,
    renderVideoDetailEmpty,
    invalidateVideoCache,
    resetCaches() {
      analysisCache = {};
      chatCache = {};
      rerunStateByVideoId = {};
    },
  };
}
