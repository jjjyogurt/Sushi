import { escapeHtml, getElement } from "./ui-utils.js";
import { t } from "./i18n.js";

function formatDateTime(isoString) {
  const raw = String(isoString || "").trim();
  if (!raw) {
    return "-";
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return "-";
  }
  return parsed.toLocaleString();
}

function formatPercent(value) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) {
    return "0.0%";
  }
  return `${numeric.toFixed(1)}%`;
}

function renderList(listElement, items, fallbackText) {
  if (!(listElement instanceof HTMLElement)) {
    return;
  }
  if (!Array.isArray(items) || items.length === 0) {
    listElement.innerHTML = `<li class="meta">${escapeHtml(fallbackText)}</li>`;
    return;
  }
  listElement.innerHTML = items.map((item) => `<li>${escapeHtml(String(item || ""))}</li>`).join("");
}

function buildTeamActions(report) {
  const topCriticism = Array.isArray(report.criticism_points) && report.criticism_points.length > 0
    ? report.criticism_points[0]
    : t("insightsNoBads");
  const topPraise = Array.isArray(report.praise_points) && report.praise_points.length > 0
    ? report.praise_points[0]
    : t("insightsNoGoods");
  const topRecommendation = Array.isArray(report.user_recommendations) && report.user_recommendations.length > 0
    ? report.user_recommendations[0]
    : t("insightsNoRecommendations");
  return [
    t("insightsTeamActionProduct", { item: topCriticism }),
    t("insightsTeamActionProductMarketing", { item: topPraise }),
    t("insightsTeamActionMarketing", { item: topRecommendation }),
  ];
}

function buildMethodologyNotes(report) {
  const analyzed = Number(report.analyzed_video_count || 0);
  const total = Number(report.total_video_count || 0);
  return [
    t("insightsMethodologySourceScope"),
    t("insightsMethodologyInclusionRule"),
    t("insightsMethodologyTranscriptRule"),
    t("insightsMethodologyCoverage", { analyzed, total }),
  ];
}

export function createInsightsController({
  getState,
  request,
  runTask,
  setActiveSection,
}) {
  let historyItems = [];
  let activeReportId = null;
  let isRefreshing = false;

  function selectedProjectId() {
    const state = getState();
    return state.selectedProfileId;
  }

  function selectedProjectName() {
    const state = getState();
    const selectedId = state.selectedProfileId;
    if (!selectedId || !Array.isArray(state.profiles)) {
      return "";
    }
    const matched = state.profiles.find((profile) => Number(profile.id) === Number(selectedId));
    return matched?.name ? String(matched.name) : "";
  }

  function isProjectSelected() {
    return Boolean(selectedProjectId());
  }

  function syncProjectContext() {
    const projectContext = getElement("insights-project-context");
    if (!(projectContext instanceof HTMLElement)) {
      return;
    }
    const projectName = selectedProjectName();
    if (!projectName) {
      projectContext.classList.add("is-hidden");
      projectContext.textContent = "";
      return;
    }
    projectContext.classList.remove("is-hidden");
    projectContext.textContent = t("insightsForProject", { project: projectName });
  }

  function syncRefreshButtonState() {
    const refreshButton = getElement("refresh-insights-btn");
    if (!(refreshButton instanceof HTMLButtonElement)) {
      return;
    }
    const projectSelected = isProjectSelected();
    const shouldDisable = !projectSelected || isRefreshing;
    refreshButton.disabled = shouldDisable;
    refreshButton.classList.toggle("is-generating", isRefreshing);
    refreshButton.setAttribute("aria-busy", isRefreshing ? "true" : "false");
    refreshButton.textContent = isRefreshing ? t("insightsGenerating") : t("insightsRefreshReport");
  }

  function syncEntryVisibility() {
    const navButton = getElement("nav-insights-btn");
    const entryButton = getElement("open-insights-btn");
    const projectSelected = isProjectSelected();

    navButton?.classList.toggle("is-hidden", !projectSelected);
    entryButton?.classList.toggle("is-hidden", !projectSelected);
    syncRefreshButtonState();
    syncProjectContext();

    if (!projectSelected && document.querySelector("#insights.panel.active")) {
      setActiveSection("queue");
    }
  }

  function renderEmptyState(message) {
    const emptyState = getElement("insights-empty-state");
    const content = getElement("insights-content");
    if (!(emptyState instanceof HTMLElement) || !(content instanceof HTMLElement)) {
      return;
    }
    emptyState.classList.remove("is-hidden");
    content.classList.add("is-hidden");
    emptyState.innerHTML = `<p class="meta">${escapeHtml(message)}</p>`;
  }

  function renderHistoryList(items) {
    const historyElement = getElement("insights-history-list");
    if (!(historyElement instanceof HTMLElement)) {
      return;
    }
    if (!Array.isArray(items) || items.length === 0) {
      historyElement.innerHTML = `<p class="meta">${escapeHtml(t("insightsNoHistory"))}</p>`;
      return;
    }
    historyElement.innerHTML = items
      .map((item) => {
        const isActive = Number(item.id) === Number(activeReportId);
        return `
          <div class="insights-history-item ${isActive ? "active" : ""}">
            <button
              type="button"
              class="insights-history-select-btn"
              data-insights-report-id="${item.id}"
            >
              <div class="insights-history-item-title">${escapeHtml(formatDateTime(item.created_at))}</div>
              <div class="meta">${escapeHtml(
                t("insightsHistoryMeta", {
                  analyzed: item.analyzed_video_count,
                  total: item.total_video_count,
                })
              )}</div>
            </button>
            <button
              type="button"
              class="insights-history-delete-btn"
              data-delete-insights-report-id="${item.id}"
              aria-label="${escapeHtml(t("insightsDeleteHistoryItem"))}"
              title="${escapeHtml(t("insightsDeleteHistoryItem"))}"
            >
              <span class="material-symbols-outlined">delete</span>
            </button>
          </div>
        `;
      })
      .join("");
  }

  function renderReport(report) {
    const emptyState = getElement("insights-empty-state");
    const content = getElement("insights-content");
    const meta = getElement("insights-meta");
    const summary = getElement("insights-summary");
    const markdown = getElement("insights-markdown");
    const goods = getElement("insights-goods-list");
    const bads = getElement("insights-bads-list");
    const recommendations = getElement("insights-recommendations-list");
    const teamActions = getElement("insights-team-actions-list");
    const methodology = getElement("insights-methodology-list");

    if (
      !(emptyState instanceof HTMLElement) ||
      !(content instanceof HTMLElement) ||
      !(meta instanceof HTMLElement) ||
      !(summary instanceof HTMLElement) ||
      !(markdown instanceof HTMLElement)
    ) {
      return;
    }

    emptyState.classList.add("is-hidden");
    content.classList.remove("is-hidden");
    activeReportId = report.id;

    meta.innerHTML = `
      <div class="insights-meta-card">
        <div class="meta">${escapeHtml(t("insightsGeneratedAt"))}</div>
        <strong>${escapeHtml(formatDateTime(report.created_at))}</strong>
      </div>
      <div class="insights-meta-card">
        <div class="meta">${escapeHtml(t("insightsAnalyzedVideos"))}</div>
        <strong>${escapeHtml(String(report.analyzed_video_count || 0))}</strong>
      </div>
      <div class="insights-meta-card">
        <div class="meta">${escapeHtml(t("insightsCoverage"))}</div>
        <strong>${escapeHtml(formatPercent(report.coverage_pct || 0))}</strong>
      </div>
      <div class="insights-meta-card">
        <div class="meta">${escapeHtml(t("insightsRiskLevel"))}</div>
        <strong>${escapeHtml(String(report.risk_level || "-"))}</strong>
      </div>
    `;

    summary.innerHTML = `
      <h4>${escapeHtml(report.summary_headline || t("insightsNoSummaryHeadline"))}</h4>
      <p>${escapeHtml(report.summary_body || t("insightsNoSummaryBody"))}</p>
      <p class="meta"><strong>${escapeHtml(t("businessImpact"))}:</strong> ${escapeHtml(report.business_impact || "-")}</p>
      <p class="meta">
        ${escapeHtml(t("insightsSentimentRiskSummary", {
          sentiment: report.overall_sentiment || "neutral",
          score: Number(report.risk_score || 0).toFixed(1),
          level: report.risk_level || "low",
        }))}
      </p>
      <p class="meta">
        ${escapeHtml(t("insightsExcludedReasons"))}: ${escapeHtml(
          Array.isArray(report.excluded_reasons) && report.excluded_reasons.length > 0
            ? report.excluded_reasons.join(", ")
            : t("insightsExcludedReasonsNone")
        )}
      </p>
    `;

    markdown.textContent = String(report.report_markdown || "");
    renderList(goods, report.praise_points, t("insightsNoGoods"));
    renderList(bads, report.criticism_points, t("insightsNoBads"));
    renderList(recommendations, report.user_recommendations, t("insightsNoRecommendations"));
    renderList(teamActions, buildTeamActions(report), t("insightsNoRecommendations"));
    renderList(methodology, buildMethodologyNotes(report), t("insightsNoSummaryBody"));
    renderHistoryList(historyItems);
  }

  async function loadHistory() {
    const projectId = selectedProjectId();
    if (!projectId) {
      historyItems = [];
      renderHistoryList(historyItems);
      return [];
    }
    const payload = await request(`/monitor-profiles/${projectId}/insights/history?limit=30`);
    const items = Array.isArray(payload.items) ? payload.items : [];
    historyItems = [...items];
    renderHistoryList(historyItems);
    return items;
  }

  async function loadCurrent() {
    const projectId = selectedProjectId();
    if (!projectId) {
      renderEmptyState(t("errorSelectProjectFirst"));
      return;
    }
    const payload = await request(`/monitor-profiles/${projectId}/insights/current`);
    const current = payload?.current || null;
    if (!current) {
      renderEmptyState(t("insightsNoReportYet"));
      return;
    }
    renderReport(current);
  }

  async function refreshInsights() {
    const projectId = selectedProjectId();
    if (!projectId) {
      throw new Error(t("errorSelectProjectFirst"));
    }
    const report = await request(`/monitor-profiles/${projectId}/insights/refresh`, {
      method: "POST",
    });
    await loadHistory();
    renderReport(report);
  }

  async function deleteHistoryItem(reportId) {
    const projectId = selectedProjectId();
    if (!projectId) {
      throw new Error(t("errorSelectProjectFirst"));
    }
    await request(`/monitor-profiles/${projectId}/insights/history/${reportId}`, {
      method: "DELETE",
    });
    historyItems = historyItems.filter((entry) => Number(entry.id) !== Number(reportId));
    if (Number(activeReportId) === Number(reportId)) {
      if (historyItems.length > 0) {
        renderReport(historyItems[0]);
        return;
      }
      activeReportId = null;
      renderHistoryList([]);
      renderEmptyState(t("insightsNoReportYet"));
      return;
    }
    renderHistoryList(historyItems);
  }

  async function clearHistory() {
    const projectId = selectedProjectId();
    if (!projectId) {
      throw new Error(t("errorSelectProjectFirst"));
    }
    await request(`/monitor-profiles/${projectId}/insights/history`, {
      method: "DELETE",
    });
    historyItems = [];
    activeReportId = null;
    renderHistoryList([]);
    renderEmptyState(t("insightsNoReportYet"));
  }

  async function openInsights() {
    if (!isProjectSelected()) {
      throw new Error(t("errorSelectProjectFirst"));
    }
    setActiveSection("insights");
    await loadHistory();
    await loadCurrent();
  }

  function bindInsightsControls() {
    const openInsightsButton = getElement("open-insights-btn");
    if (openInsightsButton) {
      openInsightsButton.addEventListener("click", () => {
        void runTask(async () => {
          await openInsights();
        });
      });
    }

    const refreshInsightsButton = getElement("refresh-insights-btn");
    if (refreshInsightsButton) {
      refreshInsightsButton.addEventListener("click", () => {
        if (isRefreshing || !isProjectSelected()) {
          return;
        }
        isRefreshing = true;
        syncRefreshButtonState();
        void runTask(async () => {
          await refreshInsights();
        }, t("insightsRefreshCompleted")).finally(() => {
          isRefreshing = false;
          syncRefreshButtonState();
        });
      });
    }

    const backButton = getElement("back-to-project-from-insights-btn");
    if (backButton) {
      backButton.addEventListener("click", () => {
        setActiveSection("queue");
      });
    }

    const clearHistoryButton = getElement("clear-insights-history-btn");
    if (clearHistoryButton) {
      clearHistoryButton.addEventListener("click", () => {
        if (!window.confirm(t("insightsConfirmDeleteAllHistory"))) {
          return;
        }
        void runTask(async () => {
          await clearHistory();
        }, t("insightsHistoryCleared"));
      });
    }

    const historyContainer = getElement("insights-history-list");
    if (historyContainer) {
      historyContainer.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
          return;
        }
        const deleteButton = target.closest("[data-delete-insights-report-id]");
        if (deleteButton instanceof HTMLElement) {
          const reportIdToDelete = Number(deleteButton.dataset.deleteInsightsReportId);
          if (Number.isNaN(reportIdToDelete)) {
            return;
          }
          if (!window.confirm(t("insightsConfirmDeleteHistoryItem"))) {
            return;
          }
          void runTask(async () => {
            await deleteHistoryItem(reportIdToDelete);
          }, t("insightsHistoryDeleted"));
          return;
        }
        const item = target.closest("[data-insights-report-id]");
        if (!(item instanceof HTMLElement)) {
          return;
        }
        const reportId = Number(item.dataset.insightsReportId);
        if (Number.isNaN(reportId)) {
          return;
        }
        const matched = historyItems.find((entry) => Number(entry.id) === reportId);
        if (!matched) {
          return;
        }
        renderReport(matched);
      });
    }
  }

  function handleSectionChange(sectionId) {
    if (sectionId !== "insights") {
      return;
    }
    syncProjectContext();
    syncRefreshButtonState();
    void runTask(async () => {
      await loadHistory();
      await loadCurrent();
    });
  }

  return {
    bindInsightsControls,
    handleSectionChange,
    loadCurrent,
    loadHistory,
    refreshInsights,
    syncEntryVisibility,
  };
}
