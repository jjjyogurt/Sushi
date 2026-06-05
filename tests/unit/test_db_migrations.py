from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.db_migrations import (
    DEFAULT_APP_USERS,
    ensure_analysis_results_agent_settings_hash_column_and_index,
    ensure_analysis_results_language_column_and_index,
    ensure_analysis_results_transcript_provenance_columns,
    cleanup_orphan_video_data,
    ensure_default_app_users,
    ensure_monitor_profiles_owner_user_id,
    ensure_analysis_results_summary_columns,
    ensure_project_insight_job_tables,
    ensure_video_candidate_scoped_youtube_uniqueness,
    ensure_video_comments_table,
    ensure_monitor_profiles_key_products_column,
    ensure_project_insight_reports_portfolio_columns,
    ensure_video_candidate_reach_columns,
    retire_legacy_business_impact_columns,
)
from app.services.security import verify_password


def test_ensure_monitor_profiles_key_products_column_adds_missing_column():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE monitor_profiles (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    brand_keywords TEXT NOT NULL,
                    markets TEXT NOT NULL,
                    languages TEXT NOT NULL,
                    alert_sensitivity TEXT,
                    is_active BOOLEAN
                )
                """
            )
        )

    ensure_monitor_profiles_key_products_column(engine)
    ensure_monitor_profiles_key_products_column(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("monitor_profiles")}
    assert "key_products" in columns


def test_ensure_analysis_results_summary_columns_adds_missing_columns():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE analysis_results (
                    id INTEGER PRIMARY KEY,
                    video_candidate_id INTEGER NOT NULL,
                    analysis_version TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    transcript_text TEXT NOT NULL DEFAULT '',
                    summary_text TEXT NOT NULL DEFAULT '',
                    translated_summary TEXT NOT NULL DEFAULT '',
                    sentiment TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    confidence_score TEXT NOT NULL DEFAULT '0.0',
                    evidence_json TEXT NOT NULL DEFAULT '[]',
                    insights_json TEXT NOT NULL DEFAULT '[]',
                    error_message TEXT NOT NULL DEFAULT ''
                )
                """
            )
        )

    ensure_analysis_results_summary_columns(engine)
    ensure_analysis_results_summary_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("analysis_results")}
    assert "summary_headline" in columns
    assert "summary_body" in columns


def test_ensure_analysis_results_transcript_provenance_columns_adds_missing_columns():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE analysis_results (
                    id INTEGER PRIMARY KEY,
                    video_candidate_id INTEGER NOT NULL,
                    analysis_version TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'en',
                    model_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    transcript_text TEXT NOT NULL DEFAULT ''
                )
                """
            )
        )

    ensure_analysis_results_transcript_provenance_columns(engine)
    ensure_analysis_results_transcript_provenance_columns(engine)

    columns = {column["name"]: column for column in inspect(engine).get_columns("analysis_results")}
    assert "transcript_language" in columns
    assert "transcript_source_language" in columns
    assert "transcript_is_translated" in columns
    assert "transcript_translation_model" in columns
    assert "transcript_status" in columns
    assert "transcript_error_message" in columns


def test_transcript_provenance_migration_does_not_compare_lowercase_completed_enum():
    source = Path("app/db_migrations.py").read_text()
    function_source = source[
        source.index("def ensure_analysis_results_transcript_provenance_columns") : source.index(
            "def ensure_video_comments_table"
        )
    ]

    assert "status = 'COMPLETED'" in function_source
    assert "status = 'completed'" not in function_source


def test_ensure_default_app_users_seeds_sushi_and_fruit_accounts_idempotently():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE app_users (
                    id VARCHAR(80) PRIMARY KEY,
                    display_name VARCHAR(120) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    must_change_password BOOLEAN NOT NULL DEFAULT 1,
                    is_active BOOLEAN NOT NULL DEFAULT 1
                )
                """
            )
        )

    ensure_default_app_users(engine)
    ensure_default_app_users(engine)

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, display_name, password_hash, must_change_password, is_active FROM app_users ORDER BY id")
        ).fetchall()

    users_by_id = {str(row[0]): row for row in rows}
    assert len(rows) == len(DEFAULT_APP_USERS) == 35
    assert "Sushi_1" in users_by_id
    assert "Passionfruit" in users_by_id
    assert "Mango" in users_by_id
    assert users_by_id["Mango"][1] == "Mango"
    assert users_by_id["Mango"][2] != "1234"
    assert verify_password("1234", users_by_id["Mango"][2])
    assert bool(users_by_id["Mango"][3]) is True
    assert bool(users_by_id["Mango"][4]) is True


def test_cleanup_orphan_video_data_removes_orphan_video_trees():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE monitor_profiles (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"))
        connection.execute(
            text(
                """
                CREATE TABLE video_candidates (
                    id INTEGER PRIMARY KEY,
                    monitor_profile_id INTEGER NOT NULL,
                    youtube_video_id TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(text("CREATE TABLE analysis_results (id INTEGER PRIMARY KEY, video_candidate_id INTEGER NOT NULL)"))
        connection.execute(text("CREATE TABLE chat_sessions (id INTEGER PRIMARY KEY, video_candidate_id INTEGER NOT NULL)"))
        connection.execute(text("CREATE TABLE chat_messages (id INTEGER PRIMARY KEY, chat_session_id INTEGER NOT NULL)"))
        connection.execute(text("CREATE TABLE incidents (id INTEGER PRIMARY KEY, video_candidate_id INTEGER NOT NULL)"))
        connection.execute(text("CREATE TABLE alerts (id INTEGER PRIMARY KEY, incident_id INTEGER NOT NULL)"))
        connection.execute(text("CREATE TABLE video_comments (id INTEGER PRIMARY KEY, video_candidate_id INTEGER NOT NULL)"))
        connection.execute(text("CREATE TABLE video_watchlist_entries (id INTEGER PRIMARY KEY, video_candidate_id INTEGER NOT NULL)"))

        connection.execute(text("INSERT INTO monitor_profiles (id, name) VALUES (1, 'active profile')"))
        connection.execute(
            text(
                """
                INSERT INTO video_candidates (id, monitor_profile_id, youtube_video_id)
                VALUES (1, 999, 'orphan-video'), (2, 1, 'active-video')
                """
            )
        )
        connection.execute(text("INSERT INTO analysis_results (id, video_candidate_id) VALUES (1, 1), (2, 2)"))
        connection.execute(text("INSERT INTO chat_sessions (id, video_candidate_id) VALUES (1, 1), (2, 2)"))
        connection.execute(text("INSERT INTO chat_messages (id, chat_session_id) VALUES (1, 1), (2, 2)"))
        connection.execute(text("INSERT INTO incidents (id, video_candidate_id) VALUES (1, 1), (2, 2)"))
        connection.execute(text("INSERT INTO alerts (id, incident_id) VALUES (1, 1), (2, 2)"))
        connection.execute(text("INSERT INTO video_comments (id, video_candidate_id) VALUES (1, 1), (2, 2)"))
        connection.execute(text("INSERT INTO video_watchlist_entries (id, video_candidate_id) VALUES (1, 1), (2, 2)"))

    cleanup_orphan_video_data(engine)

    with engine.connect() as connection:
        remaining_video_ids = [row[0] for row in connection.execute(text("SELECT id FROM video_candidates ORDER BY id"))]
        remaining_analysis_ids = [row[0] for row in connection.execute(text("SELECT video_candidate_id FROM analysis_results ORDER BY id"))]
        remaining_session_video_ids = [row[0] for row in connection.execute(text("SELECT video_candidate_id FROM chat_sessions ORDER BY id"))]
        remaining_incident_video_ids = [row[0] for row in connection.execute(text("SELECT video_candidate_id FROM incidents ORDER BY id"))]
        remaining_comment_video_ids = [row[0] for row in connection.execute(text("SELECT video_candidate_id FROM video_comments ORDER BY id"))]
        remaining_watchlist_video_ids = [row[0] for row in connection.execute(text("SELECT video_candidate_id FROM video_watchlist_entries ORDER BY id"))]

    assert remaining_video_ids == [2]
    assert remaining_analysis_ids == [2]
    assert remaining_session_video_ids == [2]
    assert remaining_incident_video_ids == [2]
    assert remaining_comment_video_ids == [2]
    assert remaining_watchlist_video_ids == [2]


def test_ensure_project_insight_reports_portfolio_columns_adds_missing_columns():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE project_insight_reports (
                    id INTEGER PRIMARY KEY,
                    monitor_profile_id INTEGER NOT NULL,
                    analyzed_video_count INTEGER NOT NULL DEFAULT 0,
                    total_video_count INTEGER NOT NULL DEFAULT 0,
                    excluded_video_count INTEGER NOT NULL DEFAULT 0,
                    coverage_pct FLOAT NOT NULL DEFAULT 0,
                    overall_sentiment TEXT NOT NULL DEFAULT 'neutral',
                    risk_level TEXT NOT NULL DEFAULT 'low',
                    risk_score FLOAT NOT NULL DEFAULT 0,
                    summary_headline TEXT NOT NULL DEFAULT '',
                    summary_body TEXT NOT NULL DEFAULT '',
                    praise_points_json TEXT NOT NULL DEFAULT '[]',
                    criticism_points_json TEXT NOT NULL DEFAULT '[]',
                    user_recommendations_json TEXT NOT NULL DEFAULT '[]',
                    excluded_reasons_json TEXT NOT NULL DEFAULT '[]',
                    report_markdown TEXT NOT NULL DEFAULT ''
                )
                """
            )
        )

    ensure_project_insight_reports_portfolio_columns(engine)
    ensure_project_insight_reports_portfolio_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("project_insight_reports")}
    indexes = {index["name"] for index in inspect(engine).get_indexes("project_insight_reports")}
    assert "language" in columns
    assert "sentiment_breakdown_json" in columns
    assert "risk_breakdown_json" in columns
    assert "reach_metrics_json" in columns
    assert "top_negative_videos_json" in columns
    assert "ix_project_insight_reports_language" in indexes


def test_ensure_video_candidate_reach_columns_adds_missing_columns_and_index():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE video_candidates (
                    id INTEGER PRIMARY KEY,
                    monitor_profile_id INTEGER NOT NULL,
                    youtube_video_id TEXT NOT NULL
                )
                """
            )
        )

    ensure_video_candidate_reach_columns(engine)
    ensure_video_candidate_reach_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("video_candidates")}
    indexes = {index["name"] for index in inspect(engine).get_indexes("video_candidates")}
    assert "view_count" in columns
    assert "view_count_fetched_at" in columns
    assert "ix_video_candidates_view_count" in indexes


def test_ensure_project_insight_job_tables_adds_one_active_job_per_project_language_guard():
    engine = create_engine("sqlite:///:memory:")
    ensure_project_insight_job_tables(engine)
    ensure_project_insight_job_tables(engine)

    tables = set(inspect(engine).get_table_names())
    columns = {column["name"] for column in inspect(engine).get_columns("project_insight_jobs")}
    indexes = {index["name"] for index in inspect(engine).get_indexes("project_insight_jobs")}
    assert "project_insight_jobs" in tables
    assert {"monitor_profile_id", "language", "created_by", "status", "report_id", "last_error"}.issubset(columns)
    assert "ix_project_insight_jobs_profile_status_created" in indexes
    assert "ix_project_insight_jobs_profile_language_status_created" in indexes
    assert "ix_project_insight_jobs_status_created" in indexes
    assert "ux_project_insight_jobs_one_active_per_profile_language" in indexes

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO project_insight_jobs (monitor_profile_id, created_by, status)
                VALUES (1, 'Sushi_1', 'QUEUED')
                """
            )
        )

    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO project_insight_jobs (monitor_profile_id, created_by, status)
                    VALUES (1, 'Sushi_1', 'RUNNING')
                    """
                )
            )
    except IntegrityError:
        pass
    else:
        raise AssertionError("Expected a second active insight job for the same project to fail.")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO project_insight_jobs (monitor_profile_id, language, created_by, status)
                VALUES (1, 'zh-Hans', 'Sushi_1', 'QUEUED')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO project_insight_jobs (monitor_profile_id, created_by, status)
                VALUES (2, 'Sushi_1', 'QUEUED')
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE project_insight_jobs
                SET status = 'COMPLETED'
                WHERE monitor_profile_id = 1
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO project_insight_jobs (monitor_profile_id, created_by, status)
                VALUES (1, 'Sushi_1', 'QUEUED')
                """
            )
        )


def test_retire_legacy_business_impact_columns_drops_legacy_columns():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE analysis_results (
                    id INTEGER PRIMARY KEY,
                    summary_headline TEXT NOT NULL DEFAULT '',
                    summary_body TEXT NOT NULL DEFAULT '',
                    business_impact TEXT NOT NULL DEFAULT ''
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE project_insight_reports (
                    id INTEGER PRIMARY KEY,
                    summary_headline TEXT NOT NULL DEFAULT '',
                    summary_body TEXT NOT NULL DEFAULT '',
                    business_impact TEXT NOT NULL DEFAULT ''
                )
                """
            )
        )

    retire_legacy_business_impact_columns(engine)
    retire_legacy_business_impact_columns(engine)

    analysis_columns = {column["name"] for column in inspect(engine).get_columns("analysis_results")}
    insights_columns = {column["name"] for column in inspect(engine).get_columns("project_insight_reports")}
    assert "business_impact" not in analysis_columns
    assert "business_impact" not in insights_columns


def test_account_isolation_migrations_upgrade_production_shaped_old_schema():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE app_users (
                    id VARCHAR(80) PRIMARY KEY,
                    display_name VARCHAR(120) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    must_change_password BOOLEAN NOT NULL DEFAULT 1,
                    is_active BOOLEAN NOT NULL DEFAULT 1
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE monitor_profiles (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    brand_keywords TEXT NOT NULL,
                    markets TEXT NOT NULL,
                    languages TEXT NOT NULL,
                    key_products TEXT NOT NULL DEFAULT '[]',
                    alert_sensitivity TEXT,
                    is_active BOOLEAN
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE video_candidates (
                    id INTEGER PRIMARY KEY,
                    monitor_profile_id INTEGER NOT NULL,
                    youtube_video_id TEXT NOT NULL UNIQUE
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE analysis_results (
                    id INTEGER PRIMARY KEY,
                    video_candidate_id INTEGER NOT NULL,
                    analysis_version TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'en',
                    model_name TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX ix_analysis_video_version_language "
                "ON analysis_results (video_candidate_id, analysis_version, language)"
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO monitor_profiles (id, name, brand_keywords, markets, languages, key_products, alert_sensitivity, is_active)
                VALUES (1, 'legacy', '[]', '[]', '[]', '[]', 'medium', 1)
                """
            )
        )
        connection.execute(
            text("INSERT INTO video_candidates (id, monitor_profile_id, youtube_video_id) VALUES (1, 1, 'same-video')")
        )
        connection.execute(
            text(
                "INSERT INTO analysis_results (id, video_candidate_id, analysis_version, language, model_name, status) "
                "VALUES (1, 1, 'v1', 'en', 'model', 'COMPLETED')"
            )
        )

    ensure_monitor_profiles_owner_user_id(engine)
    ensure_video_candidate_scoped_youtube_uniqueness(engine)
    ensure_analysis_results_agent_settings_hash_column_and_index(engine)
    ensure_analysis_results_agent_settings_hash_column_and_index(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("monitor_profiles")}
    analysis_columns = {column["name"] for column in inspect(engine).get_columns("analysis_results")}
    indexes = {index["name"] for index in inspect(engine).get_indexes("video_candidates")}
    analysis_indexes = {index["name"] for index in inspect(engine).get_indexes("analysis_results")}
    assert "owner_user_id" in columns
    assert "agent_settings_hash" in analysis_columns
    assert "ix_video_candidates_profile_youtube_video_id" in indexes
    assert "ix_analysis_video_version_language_settings" in analysis_indexes

    with engine.begin() as connection:
        owner = connection.execute(text("SELECT owner_user_id FROM monitor_profiles WHERE id = 1")).scalar_one()
        legacy_hash = connection.execute(text("SELECT agent_settings_hash FROM analysis_results WHERE id = 1")).scalar_one()
        assert owner == "Sushi_1"
        assert legacy_hash == "legacy"
        connection.execute(
            text(
                """
                INSERT INTO monitor_profiles (id, name, brand_keywords, markets, languages, key_products, alert_sensitivity, is_active, owner_user_id)
                VALUES (2, 'second', '[]', '[]', '[]', '[]', 'medium', 1, 'Sushi_1')
                """
            )
        )
        connection.execute(
            text("INSERT INTO video_candidates (id, monitor_profile_id, youtube_video_id) VALUES (2, 2, 'same-video')")
        )


def test_language_migration_does_not_create_legacy_unique_index():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE analysis_results (
                    id INTEGER PRIMARY KEY,
                    video_candidate_id INTEGER NOT NULL,
                    analysis_version TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'en',
                    model_name TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
        )

    ensure_analysis_results_language_column_and_index(engine)

    indexes = {index["name"] for index in inspect(engine).get_indexes("analysis_results")}
    assert "ix_analysis_video_version_language" not in indexes


def test_analysis_result_migrations_support_duplicate_legacy_key_with_distinct_agent_hashes():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE analysis_results (
                    id INTEGER PRIMARY KEY,
                    video_candidate_id INTEGER NOT NULL,
                    analysis_version TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'en',
                    agent_settings_hash VARCHAR(64) NOT NULL DEFAULT 'legacy',
                    model_name TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO analysis_results
                    (id, video_candidate_id, analysis_version, language, agent_settings_hash, model_name, status)
                VALUES
                    (1, 1, 'v1', 'en', 'hash-a', 'model', 'COMPLETED'),
                    (2, 1, 'v1', 'en', 'hash-b', 'model', 'COMPLETED')
                """
            )
        )

    ensure_analysis_results_language_column_and_index(engine)
    ensure_analysis_results_agent_settings_hash_column_and_index(engine)

    indexes = {index["name"] for index in inspect(engine).get_indexes("analysis_results")}
    assert "ix_analysis_video_version_language" not in indexes
    assert "ix_analysis_video_version_language_settings" in indexes


def test_ensure_video_comments_table_replaces_global_comment_uniqueness_with_video_scoped_uniqueness():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE video_candidates (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO video_candidates (id) VALUES (1), (2)"))
        connection.execute(
            text(
                """
                CREATE TABLE video_comments (
                    id INTEGER PRIMARY KEY,
                    video_candidate_id INTEGER NOT NULL,
                    youtube_comment_id VARCHAR(128) NOT NULL UNIQUE,
                    parent_comment_id VARCHAR(128) NOT NULL DEFAULT '',
                    author_name VARCHAR(255) NOT NULL DEFAULT '',
                    text TEXT NOT NULL DEFAULT '',
                    like_count INTEGER NOT NULL DEFAULT 0,
                    published_at DATETIME NOT NULL,
                    updated_at_remote DATETIME NOT NULL,
                    is_reply BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    ensure_video_comments_table(engine)
    ensure_video_comments_table(engine)

    indexes = {index["name"] for index in inspect(engine).get_indexes("video_comments")}
    assert "ix_video_comments_youtube_comment_id" in indexes
    assert "ix_video_comments_video_youtube_comment_id" in indexes

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO video_comments (
                    id, video_candidate_id, youtube_comment_id, text, published_at, updated_at_remote
                )
                VALUES (1, 1, 'same-comment', 'first', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO video_comments (
                    id, video_candidate_id, youtube_comment_id, text, published_at, updated_at_remote
                )
                VALUES (2, 2, 'same-comment', 'second', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            )
        )

    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO video_comments (
                        id, video_candidate_id, youtube_comment_id, text, published_at, updated_at_remote
                    )
                    VALUES (3, 1, 'same-comment', 'duplicate', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                )
            )
    except IntegrityError:
        pass
    else:
        raise AssertionError("Expected duplicate comment id for the same video candidate to fail.")
