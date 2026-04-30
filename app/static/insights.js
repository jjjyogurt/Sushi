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

function asPieSegments(rows) {
  const total = rows.reduce((sum, row) => sum + Math.max(0, Number(row.count || 0)), 0);
  if (total <= 0) {
    return { background: "#e5e7eb", legend: rows.map((row) => ({ ...row, pct: 0 })) };
  }
  let start = 0;
  const parts = [];
  const legend = rows.map((row) => {
    const count = Math.max(0, Number(row.count || 0));
    const pct = (count / total) * 100;
    const end = start + pct;
    parts.push(`${row.color} ${start.toFixed(2)}% ${end.toFixed(2)}%`);
    start = end;
    return { ...row, pct };
  });
  return { background: `conic-gradient(${parts.join(", ")})`, legend };
}

function renderVisualSummary(report) {
  const visual = getElement("insights-visual-summary");
  if (!(visual instanceof HTMLElement)) {
    return;
  }

  const analyzed = Number(report.analyzed_video_count || 0);
  const sentimentRows = [
    { label: t("positive"), count: Number(report.sentiment_breakdown?.positive || 0), color: "#16a34a" },
    { label: t("neutral"), count: Number(report.sentiment_breakdown?.neutral || 0), color: "#64748b" },
    { label: t("negative"), count: Number(report.sentiment_breakdown?.negative || 0), color: "#dc2626" },
  ];
  const riskRows = [
    { label: t("insightsRiskLow"), count: Number(report.risk_breakdown?.low || 0), color: "#16a34a" },
    { label: t("insightsRiskMedium"), count: Number(report.risk_breakdown?.medium || 0), color: "#f59e0b" },
    { label: t("insightsRiskHigh"), count: Number(report.risk_breakdown?.high || 0), color: "#f97316" },
    { label: t("insightsRiskCritical"), count: Number(report.risk_breakdown?.critical || 0), color: "#ef4444" },
  ];
  const sentimentPie = asPieSegments(sentimentRows);
  const riskPie = asPieSegments(riskRows);
  const reachRows = buildReachImpactNotes(report);

  const renderLegend = (rows) =>
    rows
      .map(
        (row) =>
          `<li>
            <span class="insights-legend-main">
              <span class="insights-dot" style="background:${escapeHtml(row.color)}"></span>
              <span class="insights-legend-label">${escapeHtml(row.label)}</span>
            </span>
            <span class="insights-legend-value">${escapeHtml(`${row.count} (${row.pct.toFixed(1)}%)`)}</span>
          </li>`
      )
      .join("");

  const renderReachRows = reachRows
    .map((item) => {
      const raw = String(item || "");
      const separator = raw.includes("：") ? "：" : ":";
      const [left, ...rest] = raw.split(separator);
      const right = rest.join(separator).trim();
      return `<li>
        <span class="insights-reach-label">${escapeHtml(left.trim())}</span>
        <span class="insights-reach-value">${escapeHtml(right || "-")}</span>
      </li>`;
    })
    .join("");

  visual.innerHTML = `
    <section class="insights-chart-card">
      <h4 class="insights-chart-title">${escapeHtml(t("insightsSentimentDistribution"))}</h4>
      <div class="insights-chart-body">
        <div class="insights-pie-chart" style="background:${escapeHtml(sentimentPie.background)}" aria-label="${escapeHtml(t("insightsSentimentDistribution"))}"></div>
        <ul class="insights-chart-legend">${renderLegend(sentimentPie.legend)}</ul>
      </div>
      <div class="meta">${escapeHtml(t("insightsAnalyzedVideos"))}: ${escapeHtml(String(analyzed))}</div>
    </section>
    <section class="insights-chart-card">
      <h4 class="insights-chart-title">${escapeHtml(t("insightsRiskDistribution"))}</h4>
      <div class="insights-chart-body">
        <div class="insights-pie-chart" style="background:${escapeHtml(riskPie.background)}" aria-label="${escapeHtml(t("insightsRiskDistribution"))}"></div>
        <ul class="insights-chart-legend">${renderLegend(riskPie.legend)}</ul>
      </div>
      <div class="meta">${escapeHtml(t("insightsRiskLevel"))}: ${escapeHtml(String(report.risk_level || "-").charAt(0).toUpperCase() + String(report.risk_level || "-").slice(1))}</div>
    </section>
    <section class="insights-chart-card">
      <h4 class="insights-chart-title">${escapeHtml(t("insightsReachImpact"))}</h4>
      <ul class="insights-chart-legend insights-reach-list">${renderReachRows}</ul>
    </section>
  `;
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

function buildReachImpactNotes(report) {
  const metrics = report.reach_metrics || {};
  const totalReach = Number(metrics.total_reach_views || 0);
  const negativeReach = Number(metrics.negative_reach_views || 0);
  const negativeShare = Number(metrics.negative_reach_share_pct || 0).toFixed(1);
  const criticalReach = Number(metrics.critical_risk_reach || 0);
  return [
    t("insightsTotalReachViews", { value: String(totalReach) }),
    t("insightsNegativeReachShare", { value: `${negativeShare}%` }),
    t("insightsCriticalRiskReach", { value: String(criticalReach) }),
    t("insightsNegativeReachViews", { value: String(negativeReach) }),
  ];
}

function buildTopNegativeByReach(report) {
  const rows = Array.isArray(report.top_negative_videos) ? report.top_negative_videos : [];
  if (rows.length === 0) {
    return [];
  }
  return rows.map((item, index) => {
    const title = String(item.title || "-");
    const channel = String(item.channel_name || "-");
    const views = Number(item.view_count || 0);
    const risk = String(item.risk_level || "-");
    return `${index + 1}. ${title} (${channel}) - ${views} views, risk ${risk}`;
  });
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
  let isHistoryDrawerOpen = false;

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

  function setHistoryDrawerOpen(open) {
    isHistoryDrawerOpen = Boolean(open);
    const drawer = getElement("insights-history-drawer");
    const backdrop = getElement("insights-history-drawer-backdrop");
    if (drawer instanceof HTMLElement) {
      drawer.classList.toggle("is-open", isHistoryDrawerOpen);
      drawer.setAttribute("aria-hidden", isHistoryDrawerOpen ? "false" : "true");
    }
    if (backdrop instanceof HTMLElement) {
      backdrop.classList.toggle("is-open", isHistoryDrawerOpen);
    }
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
    if (!projectSelected) {
      setHistoryDrawerOpen(false);
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
    const visualSummary = getElement("insights-visual-summary");
    const summary = getElement("insights-summary");
    const goods = getElement("insights-goods-list");
    const bads = getElement("insights-bads-list");
    const recommendations = getElement("insights-recommendations-list");
    const teamActions = getElement("insights-team-actions-list");
    const topNegative = getElement("insights-top-negative-list");

    if (
      !(emptyState instanceof HTMLElement) ||
      !(content instanceof HTMLElement) ||
      !(meta instanceof HTMLElement) ||
      !(visualSummary instanceof HTMLElement) ||
      !(summary instanceof HTMLElement)
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
        <strong>${escapeHtml(String(report.risk_level || "-").charAt(0).toUpperCase() + String(report.risk_level || "-").slice(1))}</strong>
      </div>
    `;
    renderVisualSummary(report);

    summary.innerHTML = `
      <h4>${escapeHtml(report.summary_headline || t("insightsNoSummaryHeadline"))}</h4>
      <p>${escapeHtml(report.summary_body || t("insightsNoSummaryBody"))}</p>
      <p class="meta"><strong>${escapeHtml(t("insightsTopRiskTrigger"))}:</strong> ${escapeHtml(report.top_risk_trigger || "-")}</p>
    `;

    renderList(goods, report.praise_points, t("insightsNoGoods"));
    renderList(bads, report.criticism_points, t("insightsNoBads"));
    renderList(recommendations, report.user_recommendations, t("insightsNoRecommendations"));
    renderList(teamActions, buildTeamActions(report), t("insightsNoRecommendations"));
    renderList(topNegative, buildTopNegativeByReach(report), t("insightsNoBads"));
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
    setHistoryDrawerOpen(false);
    await loadHistory();
    await loadCurrent();
  }

  function bindInsightsControls() {
    setHistoryDrawerOpen(false);

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

    const openHistoryButton = getElement("open-insights-history-btn");
    if (openHistoryButton) {
      openHistoryButton.addEventListener("click", () => {
        void runTask(async () => {
          await loadHistory();
          setHistoryDrawerOpen(true);
        });
      });
    }

    const closeHistoryButton = getElement("close-insights-history-btn");
    if (closeHistoryButton) {
      closeHistoryButton.addEventListener("click", () => {
        setHistoryDrawerOpen(false);
      });
    }

    const historyBackdrop = getElement("insights-history-drawer-backdrop");
    if (historyBackdrop) {
      historyBackdrop.addEventListener("click", () => {
        setHistoryDrawerOpen(false);
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
        setHistoryDrawerOpen(false);
      });
    }
  }

  function handleSectionChange(sectionId) {
    if (sectionId !== "insights") {
      setHistoryDrawerOpen(false);
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
