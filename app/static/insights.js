import { escapeHtml, getElement } from "./ui-utils.js";
import { iconSvg } from "./icons.js";
import { t } from "./i18n.js";

const INSIGHT_JOB_POLL_INTERVAL_MS = 2500;
const INSIGHT_JOB_MAX_POLLS = 720;

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
  return [
    t("insightsTotalReachViews", { value: String(totalReach) }),
    t("insightsNegativeReachShare", { value: `${negativeShare}%` }),
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

function normalizeInsightsLanguage(language) {
  return language === "zh-Hans" ? "zh-Hans" : "en";
}

export function createInsightsController({
  getState,
  request,
  runTask,
  setActiveSection,
}) {
  let historyItems = [];
  let activeReportId = null;
  let selectedInsightsLanguage = "en";
  const refreshingProjectIds = new Set();
  const pollingJobs = new Map();
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

  function projectKey(projectId) {
    const parsed = Number(projectId);
    return Number.isNaN(parsed) ? null : parsed;
  }

  function selectedLanguage() {
    return normalizeInsightsLanguage(selectedInsightsLanguage);
  }

  function languageQuery(language = selectedLanguage()) {
    return `language=${encodeURIComponent(normalizeInsightsLanguage(language))}`;
  }

  function projectLanguageKey(projectId, language = selectedLanguage()) {
    const key = projectKey(projectId);
    return key === null ? null : `${key}:${normalizeInsightsLanguage(language)}`;
  }

  function isCurrentProject(projectId) {
    return projectKey(selectedProjectId()) === projectKey(projectId);
  }

  function isCurrentLanguage(language) {
    return selectedLanguage() === normalizeInsightsLanguage(language);
  }

  function sleep(ms) {
    return new Promise((resolve) => {
      window.setTimeout(resolve, ms);
    });
  }

  function normalizeJobStatus(job) {
    return String(job?.status || "").trim().toLowerCase();
  }

  function isActiveJob(job) {
    return ["queued", "running"].includes(normalizeJobStatus(job));
  }

  function setProjectRefreshing(projectId, refreshing, language = selectedLanguage()) {
    const key = projectLanguageKey(projectId, language);
    if (key === null) {
      return;
    }
    if (refreshing) {
      refreshingProjectIds.add(key);
    } else {
      refreshingProjectIds.delete(key);
    }
    if (isCurrentProject(projectId) && isCurrentLanguage(language)) {
      syncRefreshButtonState();
    }
  }

  function syncLanguageToggleState() {
    const enButton = getElement("insights-lang-en-btn");
    const zhButton = getElement("insights-lang-zh-btn");
    const language = selectedLanguage();
    if (enButton instanceof HTMLButtonElement) {
      const active = language === "en";
      enButton.classList.toggle("is-active", active);
      enButton.setAttribute("aria-pressed", active ? "true" : "false");
    }
    if (zhButton instanceof HTMLButtonElement) {
      const active = language === "zh-Hans";
      zhButton.classList.toggle("is-active", active);
      zhButton.setAttribute("aria-pressed", active ? "true" : "false");
    }
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
    const currentProjectKey = projectLanguageKey(selectedProjectId());
    const isRefreshing = currentProjectKey !== null && refreshingProjectIds.has(currentProjectKey);
    const shouldDisable = currentProjectKey === null || isRefreshing;
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
    syncLanguageToggleState();

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
    clearReportContent();
    activeReportId = null;
    emptyState.classList.remove("is-hidden");
    content.classList.add("is-hidden");
    emptyState.innerHTML = `<p class="meta">${escapeHtml(message)}</p>`;
  }

  function renderLoadingState(message = t("insightsLoadingReport")) {
    const emptyState = getElement("insights-empty-state");
    const content = getElement("insights-content");
    if (!(emptyState instanceof HTMLElement) || !(content instanceof HTMLElement)) {
      return;
    }
    clearReportContent();
    activeReportId = null;
    emptyState.classList.remove("is-hidden");
    content.classList.add("is-hidden");
    emptyState.innerHTML = `
      <div class="insights-loading-state" role="status" aria-live="polite">
        <span class="insights-loading-spinner" aria-hidden="true"></span>
        <span>${escapeHtml(message)}</span>
      </div>
    `;
  }

  function clearReportContent() {
    const targets = [
      "insights-meta",
      "insights-visual-summary",
      "insights-summary",
      "insights-goods-list",
      "insights-bads-list",
      "insights-recommendations-list",
      "insights-team-actions-list",
      "insights-top-negative-list",
    ];
    targets.forEach((id) => {
      const target = getElement(id);
      if (target instanceof HTMLElement) {
        target.innerHTML = "";
      }
    });
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
              ${iconSvg("delete")}
            </button>
          </div>
        `;
      })
      .join("");
  }

  function renderReport(report, expectedProjectId = selectedProjectId(), expectedLanguage = selectedLanguage()) {
    if (!isCurrentProject(expectedProjectId) || !isCurrentLanguage(expectedLanguage)) {
      return;
    }
    if (
      projectKey(report?.monitor_profile_id) !== projectKey(expectedProjectId) ||
      normalizeInsightsLanguage(report?.language) !== normalizeInsightsLanguage(expectedLanguage)
    ) {
      renderEmptyState(t("insightsNoReportYet"));
      return;
    }

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

  async function loadHistory(projectId = selectedProjectId(), language = selectedLanguage()) {
    if (!projectId) {
      historyItems = [];
      renderHistoryList(historyItems);
      return [];
    }
    const normalizedLanguage = normalizeInsightsLanguage(language);
    const payload = await request(`/monitor-profiles/${projectId}/insights/history?${languageQuery(normalizedLanguage)}&limit=30`);
    if (!isCurrentProject(projectId) || !isCurrentLanguage(normalizedLanguage)) {
      return [];
    }
    const items = Array.isArray(payload.items) ? payload.items : [];
    historyItems = [...items];
    renderHistoryList(historyItems);
    return items;
  }

  async function loadCurrent(projectId = selectedProjectId(), language = selectedLanguage()) {
    if (!projectId) {
      renderEmptyState(t("errorSelectProjectFirst"));
      return;
    }
    const normalizedLanguage = normalizeInsightsLanguage(language);
    const payload = await request(`/monitor-profiles/${projectId}/insights/current?${languageQuery(normalizedLanguage)}`);
    if (!isCurrentProject(projectId) || !isCurrentLanguage(normalizedLanguage)) {
      return;
    }
    const current = payload?.current || null;
    if (!current) {
      renderEmptyState(t("insightsNoReportYet"));
      return;
    }
    renderReport(current, projectId, normalizedLanguage);
  }

  async function loadActiveJob(projectId = selectedProjectId(), { language = selectedLanguage(), startPolling = true } = {}) {
    if (!projectId) {
      return null;
    }
    const normalizedLanguage = normalizeInsightsLanguage(language);
    const payload = await request(`/monitor-profiles/${projectId}/insights/jobs/active?${languageQuery(normalizedLanguage)}`);
    const job = payload?.active || null;
    setProjectRefreshing(projectId, isActiveJob(job), normalizedLanguage);
    if (job && isActiveJob(job) && startPolling) {
      void pollJobUntilDone(projectId, job.id, normalizedLanguage).catch(() => {
        if (isCurrentProject(projectId) && isCurrentLanguage(normalizedLanguage)) {
          syncRefreshButtonState();
        }
      });
    }
    return job;
  }

  async function finishCompletedJob(projectId, language) {
    const normalizedLanguage = normalizeInsightsLanguage(language);
    if (!isCurrentProject(projectId) || !isCurrentLanguage(normalizedLanguage)) {
      return;
    }
    await loadHistory(projectId, normalizedLanguage);
    if (!isCurrentProject(projectId) || !isCurrentLanguage(normalizedLanguage)) {
      return;
    }
    await loadCurrent(projectId, normalizedLanguage);
  }

  async function pollJobUntilDone(projectId, jobId, language = selectedLanguage()) {
    const key = projectKey(projectId);
    const parsedJobId = Number(jobId);
    if (key === null || Number.isNaN(parsedJobId)) {
      return null;
    }
    const normalizedLanguage = normalizeInsightsLanguage(language);
    const pollKey = `${key}:${normalizedLanguage}:${parsedJobId}`;
    if (pollingJobs.has(pollKey)) {
      return pollingJobs.get(pollKey);
    }

    const pollTask = (async () => {
      for (let attempt = 0; attempt < INSIGHT_JOB_MAX_POLLS; attempt += 1) {
        const job = await request(`/monitor-profiles/${projectId}/insights/jobs/${parsedJobId}?${languageQuery(normalizedLanguage)}`);
        if (isActiveJob(job)) {
          setProjectRefreshing(projectId, true, normalizedLanguage);
          await sleep(INSIGHT_JOB_POLL_INTERVAL_MS);
          continue;
        }

        setProjectRefreshing(projectId, false, normalizedLanguage);
        const status = normalizeJobStatus(job);
        if (status === "completed") {
          await finishCompletedJob(projectId, normalizedLanguage);
          return job;
        }
        if (status === "failed") {
          throw new Error(job.last_error || "Insights generation failed.");
        }
        if (status === "cancelled") {
          throw new Error("Insights generation was cancelled.");
        }
        return job;
      }

      await loadActiveJob(projectId, { language: normalizedLanguage, startPolling: false });
      throw new Error("Insights generation is still running.");
    })().finally(() => {
      pollingJobs.delete(pollKey);
    });

    pollingJobs.set(pollKey, pollTask);
    return pollTask;
  }

  async function refreshInsights(projectId = selectedProjectId(), language = selectedLanguage()) {
    if (!projectId) {
      throw new Error(t("errorSelectProjectFirst"));
    }
    const normalizedLanguage = normalizeInsightsLanguage(language);
    let job = null;
    try {
      job = await request(`/monitor-profiles/${projectId}/insights/refresh?${languageQuery(normalizedLanguage)}`, {
        method: "POST",
      });
    } catch (error) {
      setProjectRefreshing(projectId, false, normalizedLanguage);
      throw error;
    }

    setProjectRefreshing(projectId, isActiveJob(job), normalizedLanguage);
    const status = normalizeJobStatus(job);
    if (status === "completed") {
      await finishCompletedJob(projectId, normalizedLanguage);
      return;
    }
    if (status === "failed") {
      setProjectRefreshing(projectId, false, normalizedLanguage);
      throw new Error(job.last_error || "Insights generation failed.");
    }
    if (status === "cancelled") {
      setProjectRefreshing(projectId, false, normalizedLanguage);
      throw new Error("Insights generation was cancelled.");
    }
    await pollJobUntilDone(projectId, job.id, normalizedLanguage);
  }

  async function deleteHistoryItem(reportId) {
    const projectId = selectedProjectId();
    if (!projectId) {
      throw new Error(t("errorSelectProjectFirst"));
    }
    const language = selectedLanguage();
    await request(`/monitor-profiles/${projectId}/insights/history/${reportId}?${languageQuery(language)}`, {
      method: "DELETE",
    });
    historyItems = historyItems.filter((entry) => Number(entry.id) !== Number(reportId));
    if (Number(activeReportId) === Number(reportId)) {
      if (historyItems.length > 0) {
        renderReport(historyItems[0], projectId, language);
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
    await request(`/monitor-profiles/${projectId}/insights/history?${languageQuery()}`, {
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
    renderLoadingState();
    await loadActiveJob();
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
        const projectId = selectedProjectId();
        const language = selectedLanguage();
        const currentProjectKey = projectLanguageKey(projectId, language);
        if (currentProjectKey === null || refreshingProjectIds.has(currentProjectKey)) {
          return;
        }
        refreshingProjectIds.add(currentProjectKey);
        syncRefreshButtonState();
        void runTask(async () => {
          await refreshInsights(projectId, language);
        }, t("insightsRefreshCompleted")).finally(() => {
          syncRefreshButtonState();
        });
      });
    }

    const bindLanguageButton = (buttonId, language) => {
      const button = getElement(buttonId);
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      button.addEventListener("click", () => {
        const normalizedLanguage = normalizeInsightsLanguage(language);
        if (selectedLanguage() === normalizedLanguage) {
          return;
        }
        selectedInsightsLanguage = normalizedLanguage;
        syncLanguageToggleState();
        setHistoryDrawerOpen(false);
        renderLoadingState();
        void runTask(async () => {
          await loadActiveJob(selectedProjectId(), { language: normalizedLanguage });
          await loadHistory(selectedProjectId(), normalizedLanguage);
          await loadCurrent(selectedProjectId(), normalizedLanguage);
        });
      });
    };
    bindLanguageButton("insights-lang-en-btn", "en");
    bindLanguageButton("insights-lang-zh-btn", "zh-Hans");

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
        renderReport(matched, selectedProjectId(), selectedLanguage());
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
    syncLanguageToggleState();
    renderLoadingState();
    void runTask(async () => {
      await loadActiveJob();
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
