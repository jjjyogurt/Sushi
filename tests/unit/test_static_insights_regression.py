from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_hidden_class_overrides_insights_layout_display():
    styles = (ROOT / "app/static/styles.css").read_text()

    assert ".is-hidden" in styles
    assert "display: none !important;" in styles


def test_insights_controller_guards_project_scoped_async_rendering():
    source = (ROOT / "app/static/insights.js").read_text()

    assert "function isCurrentProject(projectId)" in source
    assert "function clearReportContent()" in source
    assert "renderReport(report, expectedProjectId = selectedProjectId())" in source
    assert "projectKey(report?.monitor_profile_id) !== projectKey(expectedProjectId)" in source
    assert "if (!isCurrentProject(projectId))" in source


def test_static_cache_busts_insights_isolation_assets():
    main_source = (ROOT / "app/static/main.js").read_text()
    template = (ROOT / "app/templates/index.html").read_text()

    assert "./insights.js?v=20260523-insights-loading" in main_source
    assert "/static/styles.css?v=20260523-insights-loading" in template
    assert "/static/main.js?v=20260523-insights-loading" in template


def test_insights_refresh_uses_project_scoped_job_polling():
    source = (ROOT / "app/static/insights.js").read_text()

    assert "const refreshingProjectIds = new Set();" in source
    assert "function isActiveJob(job)" in source
    assert "/insights/jobs/active" in source
    assert "/insights/jobs/${parsedJobId}" in source
    assert "setProjectRefreshing(projectId, isActiveJob(job));" in source


def test_insights_open_renders_loading_before_empty_state():
    source = (ROOT / "app/static/insights.js").read_text()
    styles = (ROOT / "app/static/styles.css").read_text()
    translations = (ROOT / "app/static/i18n.js").read_text()

    assert "function renderLoadingState(message = t(\"insightsLoadingReport\"))" in source
    assert "insights-loading-spinner" in source
    assert "renderLoadingState();" in source
    assert "insightsLoadingReport: \"Loading report...\"" in translations
    assert ".insights-loading-spinner" in styles
    assert "@keyframes insights-loading-spin" in styles


def test_insights_empty_state_clears_stale_report_content():
    source = (ROOT / "app/static/insights.js").read_text()

    render_empty_start = source.index("function renderEmptyState(message)")
    render_empty_end = source.index("function renderLoadingState", render_empty_start)
    render_empty_source = source[render_empty_start:render_empty_end]

    assert "clearReportContent();" in render_empty_source
    assert "activeReportId = null;" in render_empty_source
    assert "emptyState.classList.remove(\"is-hidden\");" in render_empty_source
    assert "content.classList.add(\"is-hidden\");" in render_empty_source
