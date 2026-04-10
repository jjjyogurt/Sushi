import { escapeHtml, getElement } from "./ui-utils.js";
import { t } from "./i18n.js";

function normalizeAnalysisErrorMessage(rawMessage) {
  const message = String(rawMessage || "").trim();
  if (!message) {
    return t("analysisFailedTryAgain");
  }
  if (message.startsWith("GEMINI_NOT_READY:")) {
    return t("geminiNotReady");
  }
  if (message.startsWith("TRANSCRIPT_BLOCKED:")) {
    return t("transcriptRateLimited");
  }
  if (message.startsWith("TRANSCRIPT_UNAVAILABLE:")) {
    return t("transcriptUnavailable");
  }
  if (message.startsWith("TRANSCRIPT_PROVIDER_ERROR:")) {
    return t("transcriptProviderFailed");
  }
  if (
    message.toLowerCase().includes("requires asr transcription") ||
    message.toLowerCase().includes("audio transcription is required")
  ) {
    return t("transcriptRequiresAsr");
  }
  if (message.startsWith("Malformed transcript payload")) {
    return t("transcriptMalformed");
  }
  if (message.startsWith("GEMINI_PROVIDER_ERROR:") || message.startsWith("GEMINI_RESPONSE_ERROR:")) {
    return t("geminiRequestFailed");
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
    return `<span class="badge">${escapeHtml(t("unknown"))}</span>`;
  }
  const css = sentiment === "negative" ? "negative" : sentiment === "positive" ? "positive" : "";
  return `<span class="badge ${css}">${escapeHtml(sentiment)}</span>`;
}

function transcriptMarkup(analysis, transcriptExpanded) {
  const transcript = analysis ? analysis.transcript_text || "" : "";
  const buttonLabel = transcriptExpanded ? t("collapse") : t("expand");
  const excerpt = transcriptExpanded ? transcript : transcript.split("\n").slice(0, 24).join("\n");
  const bodyText = excerpt || t("runAnalysisForTranscript");
  return `
    <div class="detail-block">
      <h5>${escapeHtml(t("transcript"))}</h5>
      <div class="transcript-wrapper">
        <div class="transcript-toolbar">
          <span class="meta">${
            transcript ? t("characterCount", { count: transcript.length.toLocaleString() }) : t("noTranscriptYet")
          }</span>
          <button id="toggle-transcript-btn" class="btn btn-secondary" type="button">${buttonLabel}</button>
        </div>
        <pre class="transcript-body">${escapeHtml(bodyText)}</pre>
      </div>
    </div>
  `;
}

function evidenceText(analysis) {
  if (!analysis || !Array.isArray(analysis.evidence) || analysis.evidence.length === 0) {
    return t("noEvidenceYet");
  }
  return analysis.evidence.map((item) => `${item.timestamp} - ${item.quote} (${item.reason})`).join("\n");
}

function summaryMarkup(analysis) {
  if (!analysis) {
    return t("noAnalysisYet");
  }
  const headline = String(analysis.summary_headline || "").trim();
  const body = String(analysis.summary_body || "").trim();
  const businessImpact = String(analysis.business_impact || "").trim();
  if (!headline && !body && !businessImpact) {
    return escapeHtml(String(analysis.summary_text || "").trim() || t("noAnalysisYet"));
  }

  return `
    <div class="summary-structured">
      ${headline ? `<div class="summary-headline">${escapeHtml(headline)}</div>` : ""}
      ${body ? `<div class="summary-body">${escapeHtml(body)}</div>` : ""}
      ${
        businessImpact
          ? `<div class="summary-impact"><strong>${escapeHtml(t("businessImpact"))}:</strong> ${escapeHtml(
              businessImpact
            )}</div>`
          : ""
      }
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
      <h5>${escapeHtml(t("influencerSignal"))}</h5>
      <div class="signal-grid">
        <div>
          <div class="signal-label">${escapeHtml(t("praise"))}</div>
          ${pointListMarkup(praisePoints, t("noPraiseYet"))}
        </div>
        <div>
          <div class="signal-label">${escapeHtml(t("criticism"))}</div>
          ${pointListMarkup(criticismPoints, t("noCriticismYet"))}
        </div>
      </div>
    </div>
  `;
}

function actionRecommendationMarkup(analysis) {
  const recommendation = analysis ? String(analysis.action_recommendation || "").trim() : "";
  return `
    <div class="detail-block">
      <h5>${escapeHtml(t("actionRecommendation"))}</h5>
      <div class="recommendation-body">${escapeHtml(recommendation || t("noRecommendationYet"))}</div>
    </div>
  `;
}

function concisePointListMarkup(points) {
  if (!Array.isArray(points) || points.length === 0) {
    return `<ul class="point-list"></ul>`;
  }
  return `
    <ul class="point-list">
      ${points.map((point) => `<li>${escapeHtml(String(point))}</li>`).join("")}
    </ul>
  `;
}

function commentsSentimentMarkup(analysis) {
  const summary = analysis ? String(analysis.comment_summary_text || "").trim() : "";
  const highlights = analysis ? analysis.comment_highlights || [] : [];
  const lowlights = analysis ? analysis.comment_lowlights || [] : [];
  return `
    <div class="detail-block">
      <h5>${escapeHtml(t("commentsSentiment"))}</h5>
      <div class="summary-structured">
        <div class="summary-body">${escapeHtml(summary)}</div>
      </div>
      <div class="signal-grid">
        <div>
          <div class="signal-label">${escapeHtml(t("commentsHighlights"))}</div>
          ${concisePointListMarkup(highlights)}
        </div>
        <div>
          <div class="signal-label">${escapeHtml(t("commentsLowlights"))}</div>
          ${concisePointListMarkup(lowlights)}
        </div>
      </div>
    </div>
  `;
}

function renderChatEntries(messages) {
  if (!messages || messages.length === 0) {
    return `<div class="meta">${escapeHtml(t("noChatHistoryYet"))}</div>`;
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
    return t("notStarted");
  }
  const statusValue = String(analysis.status || "").trim();
  if (!statusValue) {
    return t("unknown");
  }
  return statusValue.charAt(0).toUpperCase() + statusValue.slice(1);
}

function normalizeAnalysisLanguage(language) {
  return language === "zh-Hans" ? "zh-Hans" : "en";
}

function analysisLanguageLabel(language) {
  return normalizeAnalysisLanguage(language) === "zh-Hans" ? "中文" : "English";
}

function analysisCacheKey(videoId, language) {
  return `${videoId}:${normalizeAnalysisLanguage(language)}`;
}

function selectedAnalysisLanguageForVideo(state, videoId) {
  const byVideo = state.analysisLanguageByVideoId || {};
  return normalizeAnalysisLanguage(byVideo[videoId]);
}

function videoDetailMarkup({ video, analysis, analysisError, transcriptExpanded, isRerunning, analysisLanguage }) {
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
        <div class="analysis-status">${escapeHtml(t("analysisStatus"))}: <strong>${escapeHtml(
    analysisStatusLabel(analysis)
  )}</strong> | ${escapeHtml(analysisLanguageLabel(analysisLanguage))}</div>
      </div>

      ${embedMarkup}

      <div class="inline-actions">
        <button id="analyze-btn" class="btn btn-primary" type="button">${isRerunning ? escapeHtml(
          t("rerunning")
        ) : analysis ? escapeHtml(t("rerunAnalysis")) : escapeHtml(t("runAnalysis"))}</button>
        <button id="escalate-btn" class="btn btn-danger" type="button">${escapeHtml(t("escalate"))}</button>
        <button id="delete-video-btn" class="btn btn-secondary" type="button">${escapeHtml(t("delete"))}</button>
        <div class="analysis-language-toggle" role="group" aria-label="Analysis language">
          <button
            id="analysis-lang-en-btn"
            class="btn btn-secondary btn-sm ${normalizeAnalysisLanguage(analysisLanguage) === "en" ? "is-active" : ""}"
            type="button"
          >
            English
          </button>
          <button
            id="analysis-lang-zh-btn"
            class="btn btn-secondary btn-sm ${normalizeAnalysisLanguage(analysisLanguage) === "zh-Hans" ? "is-active" : ""}"
            type="button"
          >
            中文
          </button>
        </div>
      </div>

      ${analysisError ? `<div class="meta" style="color: var(--danger);">${escapeHtml(analysisError)}</div>` : ""}

      <div class="detail-grid">
        <div class="detail-block">
          <h5>${escapeHtml(t("summary"))}</h5>
          <div>${summaryMarkup(analysis)}</div>
        </div>
        <div class="split-grid">
          <div class="detail-block">
            <h5>${escapeHtml(t("sentiment"))}</h5>
            <div>${analysis ? sentimentBadge(analysis.sentiment) : `<span class="badge">${escapeHtml(
              t("unknown")
            )}</span>`}</div>
          </div>
          <div class="detail-block">
            <h5>${escapeHtml(t("riskLevel"))}</h5>
            <div><strong class="${riskClass}">${escapeHtml(riskLevel)}</strong></div>
          </div>
        </div>
        ${influencerSignalMarkup(analysis)}
        ${commentsSentimentMarkup(analysis)}
        ${actionRecommendationMarkup(analysis)}
        ${transcriptMarkup(analysis, transcriptExpanded)}
        <div class="detail-block">
          <h5>${escapeHtml(t("evidence"))}</h5>
          <pre class="transcript-body">${escapeHtml(evidenceText(analysis))}</pre>
        </div>
      </div>

      <div>
        <h5 style="margin: 0 0 8px;">${escapeHtml(t("chatWithVideoAi"))}</h5>
        <div id="chat-window" class="chat-window"></div>
        <div class="inline-actions" style="margin-top: 8px;">
          <input id="chat-question" type="text" placeholder="${escapeHtml(
            t("chatInputPlaceholder")
          )}" style="flex: 1;" />
          <button id="send-chat-btn" class="btn btn-primary" type="button">${escapeHtml(t("send"))}</button>
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
  onAnyVideoAction,
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
    const analysisEntries = Object.entries(analysisCache).filter(
      ([key]) => !key.startsWith(`${videoId}:`)
    );
    const remainingAnalysis = Object.fromEntries(analysisEntries);
    const { [videoId]: _chat, ...remainingChat } = chatCache;
    const { [videoId]: _rerun, ...remainingRerun } = rerunStateByVideoId;
    analysisCache = remainingAnalysis;
    chatCache = remainingChat;
    rerunStateByVideoId = remainingRerun;
  }

  function renderVideoDetailEmpty(message) {
    const container = getElement("video-detail");
    if (!container) {
      return;
    }
    container.className = "video-detail-empty";
    container.innerHTML = `
      <div class="empty-state-content">
        <h3>${escapeHtml(t("noVideoSelected"))}</h3>
        <p>${escapeHtml(message)}</p>
      </div>
    `;
  }

  async function fetchAnalysis(videoId, language, forceRefresh = false) {
    const key = analysisCacheKey(videoId, language);
    if (!forceRefresh && analysisCache[key]) {
      return analysisCache[key];
    }

    if (detailAbortController) {
      detailAbortController.abort();
    }
    detailAbortController = new AbortController();

    const analysis = await request(`/videos/${videoId}/analysis?language=${encodeURIComponent(language)}`, {
      signal: detailAbortController.signal,
    });
    analysisCache = {
      ...analysisCache,
      [key]: analysis,
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
      const message = error instanceof Error ? error.message : t("failedToLoadChat");
      chatWindow.innerHTML = `<div class="meta" style="color: var(--danger);">${escapeHtml(message)}</div>`;
    }
  }

  function bindDetailActions(videoId) {
    const transcriptToggle = getElement("toggle-transcript-btn");
    if (transcriptToggle) {
      transcriptToggle.onclick = () => {
        onAnyVideoAction?.();
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
          onAnyVideoAction?.();
          const originalLabel = analyzeButton.textContent;
          analyzeButton.disabled = true;
          analyzeButton.textContent = t("rerunning");
          rerunStateByVideoId = {
            ...rerunStateByVideoId,
            [videoId]: true,
          };
          analysisCache = {};
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
            analysisCache = {};
            await renderVideoDetail();
          } catch (error) {
            rerunStateByVideoId = {
              ...rerunStateByVideoId,
              [videoId]: false,
            };
            analysisCache = {};
            await renderVideoDetail();
            const errorMessage = error instanceof Error ? error.message : t("analysisFailed");
            throw new Error(normalizeAnalysisErrorMessage(errorMessage));
          } finally {
            analyzeButton.disabled = false;
            analyzeButton.textContent = originalLabel || t("rerunAnalysis");
          }
        }, t("analysisRerunCompleted"));
    }

    const escalateButton = getElement("escalate-btn");
    if (escalateButton) {
      escalateButton.onclick = () =>
        runTask(async () => {
          onAnyVideoAction?.();
          await request(`/videos/${videoId}/escalate`, {
            method: "POST",
            body: JSON.stringify({ owner: "marketing-owner", notes: "Escalated from dashboard" }),
          });
          await onAlertsChanged();
        }, t("escalatedAndAlertGenerated"));
    }

    const deleteButton = getElement("delete-video-btn");
    if (deleteButton) {
      deleteButton.onclick = () =>
        runTask(async () => {
          onAnyVideoAction?.();
          await request(`/videos/${videoId}`, { method: "DELETE" });
          invalidateVideoCache(videoId);
          await onVideosChanged();
        }, t("videoDeleted"));
    }

    const sendChatButton = getElement("send-chat-btn");
    if (sendChatButton) {
      sendChatButton.onclick = () =>
        runTask(async () => {
          onAnyVideoAction?.();
          const questionInput = getElement("chat-question");
          if (!questionInput) {
            return;
          }
          const question = questionInput.value.trim();
          if (!question) {
            throw new Error(t("typeQuestionBeforeSending"));
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

    const analysisLanguageEnButton = getElement("analysis-lang-en-btn");
    if (analysisLanguageEnButton) {
      analysisLanguageEnButton.onclick = () => {
        onAnyVideoAction?.();
        setState((previous) => ({
          ...previous,
          analysisLanguageByVideoId: {
            ...(previous.analysisLanguageByVideoId || {}),
            [videoId]: "en",
          },
        }));
        void renderVideoDetail();
      };
    }

    const analysisLanguageZhButton = getElement("analysis-lang-zh-btn");
    if (analysisLanguageZhButton) {
      analysisLanguageZhButton.onclick = () => {
        onAnyVideoAction?.();
        setState((previous) => ({
          ...previous,
          analysisLanguageByVideoId: {
            ...(previous.analysisLanguageByVideoId || {}),
            [videoId]: "zh-Hans",
          },
        }));
        void renderVideoDetail();
      };
    }
  }

  async function renderVideoDetail() {
    const selectedVideo = getSelectedVideo();
    if (!selectedVideo) {
      renderVideoDetailEmpty(t("selectVideoForDetails"));
      return;
    }

    const container = getElement("video-detail");
    if (!container) {
      return;
    }

    container.className = "";
    container.innerHTML = `<div class="video-detail-body"><div class="meta">${escapeHtml(
      t("loadingDetail")
    )}</div></div>`;

    const renderTargetId = selectedVideo.id;
    let analysis = null;
    let analysisError = "";
    const state = getState();
    const analysisLanguage = selectedAnalysisLanguageForVideo(state, renderTargetId);

    try {
      analysis = await fetchAnalysis(renderTargetId, analysisLanguage);
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
      const errorMessage = error instanceof Error ? error.message : t("failedToLoadAnalysis");
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
      analysisLanguage,
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
