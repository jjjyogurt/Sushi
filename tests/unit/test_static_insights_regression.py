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
    assert "renderReport(report, expectedProjectId = selectedProjectId(), expectedLanguage = selectedLanguage())" in source
    assert "projectKey(report?.monitor_profile_id) !== projectKey(expectedProjectId)" in source
    assert "if (!isCurrentProject(projectId) || !isCurrentLanguage(normalizedLanguage))" in source


def test_static_cache_busts_insights_isolation_assets():
    main_source = (ROOT / "app/static/main.js").read_text()
    template = (ROOT / "app/templates/index.html").read_text()

    assert "./insights.js?v=20260525-insights-language" in main_source
    assert "/static/styles.css?v=20260525-video-list-panel-shorter" in template
    assert "/static/main.js?v=20260525-video-list-bulk-sort" in template


def test_static_sushi_emoji_icon_is_used_for_favicon():
    template = (ROOT / "app/templates/index.html").read_text()
    sushi_icon = (ROOT / "app/static/sushi-icon.svg").read_text()

    assert '<link rel="icon" type="image/svg+xml" href="/static/sushi-icon.svg?v=20260525-sushi-emoji" />' in template
    assert "🍣" in sushi_icon


def test_insights_refresh_uses_project_scoped_job_polling():
    source = (ROOT / "app/static/insights.js").read_text()

    assert "const refreshingProjectIds = new Set();" in source
    assert "function isActiveJob(job)" in source
    assert "/insights/jobs/active" in source
    assert "/insights/jobs/${parsedJobId}" in source
    assert "setProjectRefreshing(projectId, isActiveJob(job), normalizedLanguage);" in source


def test_insights_controller_supports_language_toggle():
    source = (ROOT / "app/static/insights.js").read_text()
    template = (ROOT / "app/templates/index.html").read_text()
    styles = (ROOT / "app/static/styles.css").read_text()

    assert "let selectedInsightsLanguage = \"en\";" in source
    assert "function projectLanguageKey(projectId, language = selectedLanguage())" in source
    assert "bindLanguageButton(\"insights-lang-zh-btn\", \"zh-Hans\");" in source
    assert "language=${encodeURIComponent(normalizeInsightsLanguage(language))}" in source
    assert "id=\"insights-lang-en-btn\"" in template
    assert "id=\"insights-lang-zh-btn\"" in template
    assert ".insights-language-toggle" in styles


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
