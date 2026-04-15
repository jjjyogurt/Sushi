from sqlalchemy import create_engine, inspect, text

from app.db_migrations import (
    cleanup_orphan_video_data,
    ensure_analysis_results_summary_columns,
    ensure_monitor_profiles_key_products_column,
)


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
    assert "business_impact" in columns


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
