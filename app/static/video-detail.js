import { escapeHtml, getElement } from "./ui-utils.js";
import { t } from "./i18n.js";

const CHAT_USER_ID = "marketing-owner";
const RETRY_CHAT_BUTTON_ID = "retry-chat-btn";

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
      ${points
        .map((item) => {
          if (item && typeof item === "object") {
            const pointText = String(item.point || "").trim();
            const quoteText = String(item.quote || "").trim();
            const fallbackText = String(item.text || "").trim();
            const resolved = pointText || fallbackText || quoteText;
            if (!resolved) {
              return "";
            }
            return `<li>${escapeHtml(resolved)}</li>`;
          }
          const fallback = String(item || "").trim();
          return fallback ? `<li>${escapeHtml(fallback)}</li>` : "";
        })
        .join("")}
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
      ${points
        .map((item) => {
          if (item && typeof item === "object") {
            const pointText = String(item.point || "").trim();
            const quoteText = String(item.quote || "").trim();
            const fallbackText = String(item.text || "").trim();
            const resolvedPoint = pointText || fallbackText || quoteText;
            if (!resolvedPoint) {
              return "";
            }
            return `
              <li>
                <div>${escapeHtml(resolvedPoint)}</div>
                ${quoteText ? `<div class="meta">"${escapeHtml(quoteText)}"</div>` : ""}
              </li>
            `;
          }
          const fallback = String(item || "").trim();
          return fallback ? `<li>${escapeHtml(fallback)}</li>` : "";
        })
        .join("")}
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

function renderChatEntries(messages, { pendingQuestion = "", isSending = false, inlineError = "" } = {}) {
  const baseMessages = Array.isArray(messages) ? messages : [];
  const pendingText = String(pendingQuestion || "").trim();
  const entries = [...baseMessages];
  if (pendingText) {
    entries.push({ role: "user", content: pendingText, isPending: true });
    if (isSending) {
      entries.push({ role: "assistant", content: t("chatAssistantThinking"), isPending: true });
    }
  }

  const entriesMarkup =
    entries.length === 0
      ? `<div class="meta">${escapeHtml(t("noChatHistoryYet"))}</div>`
      : entries
          .map((message) => {
            const citationText =
              Array.isArray(message.citations) && message.citations.length > 0
                ? ` (citations: ${message.citations.map((item) => item.timestamp).join(", ")})`
                : "";
            const role = String(message.role || "user");
            const roleClass = role === "assistant" ? "assistant" : "user";
            const pendingClass = message.isPending ? " is-pending" : "";
            return `
              <div class="chat-entry ${roleClass}${pendingClass}">
                <div class="chat-entry-label">${escapeHtml(role)}</div>
                <div class="chat-entry-bubble">${escapeHtml(String(message.content || ""))}${escapeHtml(
                  citationText
                )}</div>
              </div>
            `;
          })
          .join("");

  const errorText = String(inlineError || "").trim();
  const inlineErrorMarkup = errorText
    ? `
      <div class="chat-inline-error">
        <span>${escapeHtml(errorText)}</span>
        <button id="${RETRY_CHAT_BUTTON_ID}" class="btn btn-secondary btn-sm" type="button">${escapeHtml(
          t("retry")
        )}</button>
      </div>
    `
    : "";

  return `${entriesMarkup}${inlineErrorMarkup}`;
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
  let chatDraftByVideoId = {};
  let chatPendingQuestionByVideoId = {};
  let chatInlineErrorByVideoId = {};
  let chatSendingByVideoId = {};
  let rerunStateByVideoId = {};
  let detailAbortController = null;

  function withoutVideoKey(record, videoId) {
    const { [videoId]: _removed, ...remaining } = record;
    return remaining;
  }

  function getSelectedVideo() {
    const state = getState();
    return state.videos.find((video) => video.id === state.selectedVideoId) || null;
  }

  function invalidateVideoCache(videoId) {
    const analysisEntries = Object.entries(analysisCache).filter(
      ([key]) => !key.startsWith(`${videoId}:`)
    );
    const remainingAnalysis = Object.fromEntries(analysisEntries);
    const remainingChat = withoutVideoKey(chatCache, videoId);
    const remainingDraft = withoutVideoKey(chatDraftByVideoId, videoId);
    const remainingPendingQuestion = withoutVideoKey(chatPendingQuestionByVideoId, videoId);
    const remainingInlineError = withoutVideoKey(chatInlineErrorByVideoId, videoId);
    const remainingSending = withoutVideoKey(chatSendingByVideoId, videoId);
    const { [videoId]: _rerun, ...remainingRerun } = rerunStateByVideoId;
    analysisCache = remainingAnalysis;
    chatCache = remainingChat;
    chatDraftByVideoId = remainingDraft;
    chatPendingQuestionByVideoId = remainingPendingQuestion;
    chatInlineErrorByVideoId = remainingInlineError;
    chatSendingByVideoId = remainingSending;
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
    const messages = await request(`/videos/${videoId}/chat?user_id=${encodeURIComponent(CHAT_USER_ID)}`);
    chatCache = {
      ...chatCache,
      [videoId]: messages,
    };
    return messages;
  }

  function setChatComposerState(videoId) {
    const questionInput = getElement("chat-question");
    const sendChatButton = getElement("send-chat-btn");
    const isSending = Boolean(chatSendingByVideoId[videoId]);

    if (questionInput) {
      questionInput.disabled = isSending;
    }
    if (sendChatButton) {
      sendChatButton.disabled = isSending;
      sendChatButton.textContent = isSending ? t("sending") : t("send");
    }
  }

  async function renderChat(videoId, { forceRefresh = false, skipFetch = false } = {}) {
    const chatWindow = getElement("chat-window");
    if (!chatWindow) {
      return;
    }
    try {
      const messages = skipFetch ? chatCache[videoId] || [] : await fetchChat(videoId, forceRefresh);
      chatWindow.innerHTML = renderChatEntries(messages, {
        pendingQuestion: chatPendingQuestionByVideoId[videoId],
        isSending: Boolean(chatSendingByVideoId[videoId]),
        inlineError: chatInlineErrorByVideoId[videoId],
      });
      chatWindow.scrollTop = chatWindow.scrollHeight;
    } catch (error) {
      const message = error instanceof Error ? error.message : t("failedToLoadChat");
      chatWindow.innerHTML = renderChatEntries(chatCache[videoId] || [], {
        pendingQuestion: chatPendingQuestionByVideoId[videoId],
        isSending: Boolean(chatSendingByVideoId[videoId]),
        inlineError: message,
      });
      chatWindow.scrollTop = chatWindow.scrollHeight;
    }
    setChatComposerState(videoId);
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
    const questionInput = getElement("chat-question");
    const bindRetryButton = () => {
      const retryButton = getElement(RETRY_CHAT_BUTTON_ID);
      if (!retryButton) {
        return;
      }
      retryButton.onclick = () => {
        const pendingQuestion = String(chatDraftByVideoId[videoId] || "").trim();
        void submitChatQuestion(pendingQuestion);
      };
    };
    const submitChatQuestion = async (retryQuestion = "") => {
      if (chatSendingByVideoId[videoId]) {
        return;
      }
      const input = getElement("chat-question");
      const rawQuestion = String(retryQuestion || (input ? input.value : ""));
      const question = rawQuestion.trim();
      if (!question) {
        chatInlineErrorByVideoId = {
          ...chatInlineErrorByVideoId,
          [videoId]: t("typeQuestionBeforeSending"),
        };
        await renderChat(videoId, { skipFetch: true });
        bindRetryButton();
        if (input) {
          input.focus();
        }
        return;
      }

      onAnyVideoAction?.();
      chatSendingByVideoId = {
        ...chatSendingByVideoId,
        [videoId]: true,
      };
      chatPendingQuestionByVideoId = {
        ...chatPendingQuestionByVideoId,
        [videoId]: question,
      };
      chatDraftByVideoId = withoutVideoKey(chatDraftByVideoId, videoId);
      chatInlineErrorByVideoId = withoutVideoKey(chatInlineErrorByVideoId, videoId);
      if (input) {
        input.value = "";
      }
      await renderChat(videoId, { skipFetch: true });
      bindRetryButton();

      try {
        await request(`/videos/${videoId}/chat`, {
          method: "POST",
          body: JSON.stringify({ question, user_id: CHAT_USER_ID }),
        });
        chatSendingByVideoId = withoutVideoKey(chatSendingByVideoId, videoId);
        chatPendingQuestionByVideoId = withoutVideoKey(chatPendingQuestionByVideoId, videoId);
        chatInlineErrorByVideoId = withoutVideoKey(chatInlineErrorByVideoId, videoId);
        chatDraftByVideoId = withoutVideoKey(chatDraftByVideoId, videoId);
        chatCache = withoutVideoKey(chatCache, videoId);
        await renderChat(videoId, { forceRefresh: true });
        bindRetryButton();
        const refreshedInput = getElement("chat-question");
        if (refreshedInput) {
          refreshedInput.focus();
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : t("failedToLoadChat");
        chatSendingByVideoId = withoutVideoKey(chatSendingByVideoId, videoId);
        chatPendingQuestionByVideoId = withoutVideoKey(chatPendingQuestionByVideoId, videoId);
        chatDraftByVideoId = {
          ...chatDraftByVideoId,
          [videoId]: question,
        };
        chatInlineErrorByVideoId = {
          ...chatInlineErrorByVideoId,
          [videoId]: message,
        };
        await renderChat(videoId, { skipFetch: true });
        bindRetryButton();
        const restoredInput = getElement("chat-question");
        if (restoredInput) {
          restoredInput.value = question;
          restoredInput.focus();
        }
      }
    };

    if (sendChatButton) {
      sendChatButton.onclick = () => {
        void submitChatQuestion();
      };
    }

    if (questionInput) {
      questionInput.onkeydown = (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          void submitChatQuestion();
        }
      };
    }
    bindRetryButton();

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
      chatDraftByVideoId = {};
      chatPendingQuestionByVideoId = {};
      chatInlineErrorByVideoId = {};
      chatSendingByVideoId = {};
      rerunStateByVideoId = {};
    },
  };
}
