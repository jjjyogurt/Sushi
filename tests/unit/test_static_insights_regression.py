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
    assert "/static/styles.css?v=20260603-remove-action-recommendation" in template
    assert "/static/main.js?v=20260603-remove-action-recommendation" in template
    assert "./queue.js?v=20260527-video-row-strip" in main_source
    assert "./video-detail.js?v=20260603-remove-action-recommendation" in main_source
    assert "./i18n.js?v=20260603-remove-action-recommendation" in main_source


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


def test_video_reach_subscriber_label_is_concise():
    translations = (ROOT / "app/static/i18n.js").read_text()

    assert 'influencerSubscribers: "Subscribers"' in translations
    assert 'influencerSubscribers: "Influencer subscribers"' not in translations


def test_video_list_row_uses_essential_strip_metadata():
    source = (ROOT / "app/static/queue.js").read_text()
    styles = (ROOT / "app/static/styles.css").read_text()

    render_start = source.index("function renderVideoListItem")
    render_end = source.index("async function refreshVideos", render_start)
    render_source = source[render_start:render_end]

    meta_start = styles.index(".video-row-meta-line {")
    meta_end = styles.index(".video-row-meta-line span + span", meta_start)
    meta_source = styles[meta_start:meta_end]

    assert "sentimentBadge(video.sentiment_label)" not in render_source
    assert "analysisStatusLine" not in render_source
    assert "formatLanguageLabel(video.language)" not in render_source
    assert "${analysisStatusBadge(video)}" in render_source
    assert "formatVideoPublishedAt(video.published_at)" in render_source
    assert '`${escapeHtml(t("videoViews"))}: ${escapeHtml(formatVideoViews(video.view_count))}`' in render_source
    assert "font-size: 0.68rem;" in meta_source
    assert "color: var(--text-muted);" in meta_source


def test_discover_videos_requests_fifty_candidates():
    source = (ROOT / "app/static/queue.js").read_text()

    discover_start = source.index("async function discoverVideos")
    discover_end = source.index("function bindDiscoverVideoButton", discover_start)
    discover_source = source[discover_start:discover_end]

    assert "max_results: 50" in discover_source
    assert "max_results: 20" not in discover_source


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

    assert "align-self: flex-end;" in toggle_source
    assert "gap: 1px;" in toggle_source
    assert "padding: 2px;" in toggle_source
    assert "background: #f6f8f8;" in toggle_source
    assert "min-height: 22px;" in button_source
    assert "padding: 2px 6px;" in button_source
    assert "font-size: 0.64rem;" in button_source
    assert "background: transparent;" in button_source
    assert "background: #ffffff;" in active_source
    assert "box-shadow: 0 1px 2px rgb(45 52 53 / 10%);" in active_source


def test_video_detail_transcript_download_sits_beside_expand_and_uses_selected_language():
    source = (ROOT / "app/static/video-detail.js").read_text()
    styles = (ROOT / "app/static/styles.css").read_text()
    translations = (ROOT / "app/static/i18n.js").read_text()

    transcript_start = source.index("function transcriptMarkup")
    transcript_end = source.index("function evidenceText", transcript_start)
    transcript_source = source[transcript_start:transcript_end]

    bind_start = source.index("function bindDetailActions")
    bind_end = source.index("const analyzeButton", bind_start)
    bind_source = source[bind_start:bind_end]

    assert 'id="download-transcript-btn"' in transcript_source
    assert 'id="toggle-transcript-btn"' in transcript_source
    assert transcript_source.index('id="download-transcript-btn"') < transcript_source.index('id="toggle-transcript-btn"')
    assert 'class="transcript-wrapper ${transcriptExpanded ? "is-expanded" : ""}"' in transcript_source
    assert "function parseTimestampedTranscript(transcript)" in source
    assert "function transcriptBodyMarkup(bodyText)" in source
    assert 'class="transcript-body is-timestamped"' in source
    assert 'class="transcript-timestamp"' in source
    assert 'class="transcript-line-text"' in source
    assert 'const downloadDisabled = transcript ? "" : " disabled";' in transcript_source
    assert 'String(analysis?.transcript_status || "") === "unavailable"' in transcript_source
    assert "transcript-warning" in transcript_source
    assert "function transcriptDownloadContent(video, analysis, analysisLanguage)" in source
    assert 'const transcript = String(analysis?.transcript_text || "");' in source
    assert "`Language: ${normalizeAnalysisLanguage(analysisLanguage)}`" in source
    assert "transcript," in source
    assert "new Blob([transcriptDownloadContent(video, analysis, analysisLanguage)]" in source
    assert "sushi-transcript-${youtubeId}-${language}.txt" in source
    assert "analysisCache[analysisCacheKey(videoId, analysisLanguage)]" in bind_source
    assert ".transcript-toolbar-actions" in styles
    assert ".transcript-warning" in styles
    assert ".transcript-row" in styles
    assert "grid-template-columns: 52px minmax(0, 1fr);" in styles
    assert ".transcript-timestamp" in styles
    assert ".transcript-wrapper.is-expanded .transcript-body" in styles
    assert "max-height: min(70vh, 720px);" in styles
    assert 'downloadTranscript: "Download"' in translations
    assert 'transcriptTranslationWarning: "Analysis is complete. Transcript translation failed, so the transcript is unavailable for this language."' in translations
    assert 'downloadTranscript: "下载"' in translations


def test_video_detail_does_not_render_action_recommendation_card():
    source = (ROOT / "app/static/video-detail.js").read_text()
    styles = (ROOT / "app/static/styles.css").read_text()

    assert "function actionRecommendationMarkup" not in source
    assert "${actionRecommendationMarkup(analysis)}" not in source
    assert "recommendation-body" not in styles


def test_video_detail_analysis_layout_has_breathing_room():
    source = (ROOT / "app/static/video-detail.js").read_text()
    styles = (ROOT / "app/static/styles.css").read_text()

    detail_start = styles.index(".video-detail-body {")
    detail_end = styles.index(".video-detail-header", detail_start)
    detail_source = styles[detail_start:detail_end]

    queue_layout_start = styles.index(".queue-layout {")
    queue_layout_end = styles.index(".queue-list-pane,", queue_layout_start)
    queue_layout_source = styles[queue_layout_start:queue_layout_end]

    queue_pane_start = styles.index(".queue-list-pane,")
    queue_pane_end = styles.index(".queue-list-pane {", queue_pane_start)
    queue_pane_source = styles[queue_pane_start:queue_pane_end]

    embed_start = styles.index(".video-embed {")
    embed_end = styles.index(".mobile-nav", embed_start)
    embed_source = styles[embed_start:embed_end]

    scoped_block_start = styles.index(".video-detail-body .detail-block {")
    scoped_block_end = styles.index(".video-detail-body .detail-block h5", scoped_block_start)
    scoped_block_source = styles[scoped_block_start:scoped_block_end]

    assert 'class="video-detail-header"' in source
    assert 'class="inline-actions video-detail-actions"' in source
    assert 'class="video-chat-section"' in source
    assert 'class="chat-question-input"' in source
    assert "padding: 28px;" in detail_source
    assert "gap: 24px;" in detail_source
    assert "min-width: 0;" in detail_source
    assert "overflow: hidden;" in detail_source
    assert ".video-detail-body > *" in styles
    assert "min-width: 0;" in queue_layout_source
    assert "min-width: 0;" in queue_pane_source
    assert "max-width: 100%;" in queue_pane_source
    assert "aspect-ratio: 16 / 9;" in embed_source
    assert "max-width: 100%;" in embed_source
    assert "padding: 20px;" in scoped_block_source
    assert "border-radius: 8px;" in scoped_block_source
    assert ".summary-structured + .signal-grid" in styles


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
