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
    assert "/static/styles.css?v=20260526-language-toggle" in template
    assert "/static/main.js?v=20260526-detail-status-labels" in template
    assert "./video-detail.js?v=20260526-detail-status-labels" in main_source
    assert "./i18n.js?v=20260526-remove-analysis-start-panel" in main_source


def test_sidebar_slogan_stays_on_one_line():
    styles = (ROOT / "app/static/styles.css").read_text()
    template = (ROOT / "app/templates/index.html").read_text()
    translations = (ROOT / "app/static/i18n.js").read_text()

    assert "Get the market’s view,&nbsp;early." in template
    assert 'appSubtitle: "Get the market’s view,\\u00a0early."' in translations
    assert ".brand-block p" in styles
    assert "white-space: nowrap;" in styles


def test_sidebar_brand_text_is_hidden_cleanly_when_compact():
    styles = (ROOT / "app/static/styles.css").read_text()

    assert ".brand-block {" in styles
    assert "transition: opacity 0.12s ease 0.1s;" in styles
    assert ".app-shell.sidebar-compact .brand-block {" in styles
    assert "visibility: hidden;" in styles
    assert "width: 0;" in styles
    assert "overflow: hidden;" in styles


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


def test_unanalyzed_video_detail_does_not_render_start_panel():
    source = (ROOT / "app/static/video-detail.js").read_text()
    styles = (ROOT / "app/static/styles.css").read_text()
    translations = (ROOT / "app/static/i18n.js").read_text()

    assert "function analysisStartPanelMarkup" not in source
    assert "analysisStartPanelMarkup" not in source
    assert "const embedMarkup = analysis && videoId" in source
    assert ".analysis-start-panel" not in styles
    assert "analysisNotStartedTitle" not in translations
    assert "analysisUnlocksLabel" not in translations


def test_video_detail_status_uses_metric_label_treatment():
    source = (ROOT / "app/static/video-detail.js").read_text()
    styles = (ROOT / "app/static/styles.css").read_text()

    assert "function videoAnalysisStatusMarkup(analysis, analysisLanguage)" in source
    assert '<span class="reach-label">${escapeHtml(t("analysisStatus"))}</span>' in source
    assert '<span class="reach-label">${escapeHtml(t("languageSettings"))}</span>' in source
    assert "${videoAnalysisStatusMarkup(analysis, analysisLanguage)}" in source
    assert ".analysis-status {" in styles
    assert "display: flex;" in styles
    assert "flex-wrap: wrap;" in styles


def test_analysis_language_toggle_uses_compact_segmented_control():
    styles = (ROOT / "app/static/styles.css").read_text()

    toggle_start = styles.index(".analysis-language-toggle {")
    toggle_end = styles.index(".analysis-language-toggle .btn", toggle_start)
    toggle_source = styles[toggle_start:toggle_end]

    button_start = styles.index(".analysis-language-toggle .btn {")
    button_end = styles.index(".analysis-language-toggle .btn:hover", button_start)
    button_source = styles[button_start:button_end]

    active_start = styles.index(".analysis-language-toggle .btn.is-active {")
    active_end = styles.index(".btn-danger", active_start)
    active_source = styles[active_start:active_end]

    assert "gap: 2px;" in toggle_source
    assert "padding: 3px;" in toggle_source
    assert "background: #f6f8f8;" in toggle_source
    assert "min-height: 28px;" in button_source
    assert "padding: 4px 8px;" in button_source
    assert "background: transparent;" in button_source
    assert "background: #ffffff;" in active_source
    assert "box-shadow: 0 1px 2px rgb(45 52 53 / 10%);" in active_source


def test_alerts_render_as_structured_triage_items():
    source = (ROOT / "app/static/main.js").read_text()
    styles = (ROOT / "app/static/styles.css").read_text()

    assert "alert-item alert-item-${escapeHtml(severity)}" in source
    assert "alert-meta-grid" in source
    assert "alert-date" in source
    assert ".alert-meta-grid" in styles
    assert "-webkit-line-clamp: 3;" in styles


def test_queue_add_video_controls_shrink_inside_container():
    styles = (ROOT / "app/static/styles.css").read_text()

    url_wrap_start = styles.index(".url-add-group-wrap {")
    url_wrap_end = styles.index(".url-add-group-wrap label", url_wrap_start)
    url_wrap_source = styles[url_wrap_start:url_wrap_end]

    textarea_start = styles.index(".url-add-group textarea {")
    textarea_end = styles.index(".url-add-group button", textarea_start)
    textarea_source = styles[textarea_start:textarea_end]

    assert "min-width: 0;" in url_wrap_source
    assert "min-width: 0;" in textarea_source
