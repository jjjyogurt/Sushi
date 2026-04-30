from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.services.security import hash_password


DEFAULT_APP_USERS = tuple(f"Sushi_{index}" for index in range(1, 16))


def ensure_analysis_batch_tables(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "analysis_batches" not in table_names:
            connection.execute(
                text(
                    """
                    CREATE TABLE analysis_batches (
                        id INTEGER PRIMARY KEY,
                        monitor_profile_id INTEGER NULL,
                        created_by VARCHAR(80) NOT NULL DEFAULT 'system',
                        status VARCHAR(20) NOT NULL DEFAULT 'queued',
                        total_count INTEGER NOT NULL DEFAULT 0,
                        processed_count INTEGER NOT NULL DEFAULT 0,
                        success_count INTEGER NOT NULL DEFAULT 0,
                        failed_count INTEGER NOT NULL DEFAULT 0,
                        last_error TEXT NOT NULL DEFAULT '',
                        started_at DATETIME NULL,
                        finished_at DATETIME NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(monitor_profile_id) REFERENCES monitor_profiles(id)
                    )
                    """
                )
            )
            connection.execute(
                text("CREATE INDEX ix_analysis_batches_status_created ON analysis_batches (status, created_at)")
            )
            connection.execute(
                text("CREATE INDEX ix_analysis_batches_monitor_profile_id ON analysis_batches (monitor_profile_id)")
            )

        if "analysis_batch_items" not in table_names:
            connection.execute(
                text(
                    """
                    CREATE TABLE analysis_batch_items (
                        id INTEGER PRIMARY KEY,
                        batch_id INTEGER NOT NULL,
                        video_id INTEGER NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'queued',
                        attempt_count INTEGER NOT NULL DEFAULT 0,
                        error_message TEXT NOT NULL DEFAULT '',
                        started_at DATETIME NULL,
                        finished_at DATETIME NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(batch_id) REFERENCES analysis_batches(id),
                        FOREIGN KEY(video_id) REFERENCES video_candidates(id)
                    )
                    """
                )
            )
            connection.execute(text("CREATE INDEX ix_analysis_batch_items_batch_id ON analysis_batch_items (batch_id)"))
            connection.execute(text("CREATE INDEX ix_analysis_batch_items_video_id ON analysis_batch_items (video_id)"))
            connection.execute(
                text("CREATE INDEX ix_analysis_batch_items_batch_status ON analysis_batch_items (batch_id, status)")
            )

def ensure_monitor_profiles_key_products_column(engine: Engine) -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("monitor_profiles")}
    if "key_products" in columns:
        return

    with engine.begin() as connection:
        dialect_name = connection.dialect.name
        if dialect_name == "sqlite":
            connection.execute(
                text("ALTER TABLE monitor_profiles ADD COLUMN key_products TEXT NOT NULL DEFAULT '[]'")
            )
            return
        connection.execute(
            text("ALTER TABLE monitor_profiles ADD COLUMN key_products TEXT NOT NULL DEFAULT '[]'")
        )


def ensure_analysis_results_summary_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("analysis_results")}

    statements = []
    if "summary_headline" not in columns:
        statements = [*statements, "ALTER TABLE analysis_results ADD COLUMN summary_headline TEXT NOT NULL DEFAULT ''"]
    if "summary_body" not in columns:
        statements = [*statements, "ALTER TABLE analysis_results ADD COLUMN summary_body TEXT NOT NULL DEFAULT ''"]
    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_analysis_results_language_column_and_index(engine: Engine) -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("analysis_results")}
    indexes = {index["name"] for index in inspector.get_indexes("analysis_results")}

    statements = []
    if "language" not in columns:
        statements = [*statements, "ALTER TABLE analysis_results ADD COLUMN language TEXT NOT NULL DEFAULT 'en'"]
    if "ix_analysis_video_version" in indexes:
        statements = [*statements, "DROP INDEX ix_analysis_video_version"]
    if "ix_analysis_video_version_language" not in indexes:
        statements = [
            *statements,
            "CREATE UNIQUE INDEX ix_analysis_video_version_language ON analysis_results (video_candidate_id, analysis_version, language)",
        ]
    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_analysis_results_comment_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("analysis_results")}

    statements = []
    if "comment_summary_text" not in columns:
        statements = [*statements, "ALTER TABLE analysis_results ADD COLUMN comment_summary_text TEXT NOT NULL DEFAULT ''"]
    if "comment_highlights_json" not in columns:
        statements = [*statements, "ALTER TABLE analysis_results ADD COLUMN comment_highlights_json TEXT NOT NULL DEFAULT '[]'"]
    if "comment_lowlights_json" not in columns:
        statements = [*statements, "ALTER TABLE analysis_results ADD COLUMN comment_lowlights_json TEXT NOT NULL DEFAULT '[]'"]
    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_video_comments_table(engine: Engine) -> None:
    inspector = inspect(engine)
    if "video_comments" in inspector.get_table_names():
        return

    with engine.begin() as connection:
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
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(video_candidate_id) REFERENCES video_candidates(id)
                )
                """
            )
        )
        connection.execute(text("CREATE INDEX ix_video_comments_video_candidate_id ON video_comments (video_candidate_id)"))
        connection.execute(text("CREATE INDEX ix_video_comments_published_at ON video_comments (published_at)"))
        connection.execute(text("CREATE INDEX ix_video_comments_parent_comment_id ON video_comments (parent_comment_id)"))


def ensure_video_candidate_assignment_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("video_candidates")}

    statements = []
    if "assigned_user_id" not in columns:
        statements = [*statements, "ALTER TABLE video_candidates ADD COLUMN assigned_user_id VARCHAR(80) NOT NULL DEFAULT ''"]
    if "assigned_by" not in columns:
        statements = [*statements, "ALTER TABLE video_candidates ADD COLUMN assigned_by VARCHAR(80) NOT NULL DEFAULT ''"]
    if "assigned_at" not in columns:
        statements = [*statements, "ALTER TABLE video_candidates ADD COLUMN assigned_at DATETIME NULL"]
    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_project_insight_reports_portfolio_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "project_insight_reports" not in table_names:
        return
    columns = {column["name"] for column in inspector.get_columns("project_insight_reports")}
    statements = []
    if "sentiment_breakdown_json" not in columns:
        statements = [*statements, "ALTER TABLE project_insight_reports ADD COLUMN sentiment_breakdown_json TEXT NOT NULL DEFAULT '{}'"]
    if "risk_breakdown_json" not in columns:
        statements = [*statements, "ALTER TABLE project_insight_reports ADD COLUMN risk_breakdown_json TEXT NOT NULL DEFAULT '{}'"]
    if "reach_metrics_json" not in columns:
        statements = [*statements, "ALTER TABLE project_insight_reports ADD COLUMN reach_metrics_json TEXT NOT NULL DEFAULT '{}'"]
    if "top_negative_videos_json" not in columns:
        statements = [*statements, "ALTER TABLE project_insight_reports ADD COLUMN top_negative_videos_json TEXT NOT NULL DEFAULT '[]'"]
    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def retire_legacy_business_impact_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    statements = []
    if "analysis_results" in table_names:
        analysis_columns = {column["name"] for column in inspector.get_columns("analysis_results")}
        if "business_impact" in analysis_columns:
            statements = [*statements, "ALTER TABLE analysis_results DROP COLUMN business_impact"]
    if "project_insight_reports" in table_names:
        insight_columns = {column["name"] for column in inspector.get_columns("project_insight_reports")}
        if "business_impact" in insight_columns:
            statements = [*statements, "ALTER TABLE project_insight_reports DROP COLUMN business_impact"]
    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def cleanup_orphan_video_data(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "video_candidates" not in table_names or "monitor_profiles" not in table_names:
        return

    video_candidate_columns = {column["name"] for column in inspector.get_columns("video_candidates")}
    monitor_profile_columns = {column["name"] for column in inspector.get_columns("monitor_profiles")}
    supports_stale_timestamp_check = "created_at" in video_candidate_columns and "created_at" in monitor_profile_columns

    with engine.begin() as connection:
        dialect_name = connection.dialect.name
        if supports_stale_timestamp_check:
            if dialect_name == "sqlite":
                stale_condition = " OR datetime(vc.created_at) < datetime(mp.created_at)"
            else:
                # PostgreSQL and other databases: direct timestamp comparison
                stale_condition = " OR vc.created_at < mp.created_at"
        else:
            stale_condition = ""

        stale_or_orphan_video_subquery = (
            "SELECT vc.id FROM video_candidates vc "
            "LEFT JOIN monitor_profiles mp ON mp.id = vc.monitor_profile_id "
            f"WHERE mp.id IS NULL{stale_condition}"
        )
        if "alerts" in table_names and "incidents" in table_names:
            connection.execute(
                text(
                    f"DELETE FROM alerts WHERE incident_id IN (SELECT id FROM incidents WHERE video_candidate_id IN ({stale_or_orphan_video_subquery}))"
                )
            )
            connection.execute(text("DELETE FROM alerts WHERE incident_id NOT IN (SELECT id FROM incidents)"))

        if "chat_messages" in table_names and "chat_sessions" in table_names:
            connection.execute(
                text(
                    f"DELETE FROM chat_messages WHERE chat_session_id IN (SELECT id FROM chat_sessions WHERE video_candidate_id IN ({stale_or_orphan_video_subquery}))"
                )
            )
            connection.execute(text("DELETE FROM chat_messages WHERE chat_session_id NOT IN (SELECT id FROM chat_sessions)"))

        if "video_watchlist_entries" in table_names:
            connection.execute(
                text(
                    f"DELETE FROM video_watchlist_entries WHERE video_candidate_id IN ({stale_or_orphan_video_subquery})"
                )
            )
            connection.execute(
                text("DELETE FROM video_watchlist_entries WHERE video_candidate_id NOT IN (SELECT id FROM video_candidates)")
            )

        if "video_comments" in table_names:
            connection.execute(
                text(
                    f"DELETE FROM video_comments WHERE video_candidate_id IN ({stale_or_orphan_video_subquery})"
                )
            )
            connection.execute(text("DELETE FROM video_comments WHERE video_candidate_id NOT IN (SELECT id FROM video_candidates)"))

        if "analysis_results" in table_names:
            connection.execute(
                text(
                    f"DELETE FROM analysis_results WHERE video_candidate_id IN ({stale_or_orphan_video_subquery})"
                )
            )
            connection.execute(text("DELETE FROM analysis_results WHERE video_candidate_id NOT IN (SELECT id FROM video_candidates)"))

        if "analysis_batch_items" in table_names:
            connection.execute(
                text(
                    f"DELETE FROM analysis_batch_items WHERE video_id IN ({stale_or_orphan_video_subquery})"
                )
            )
            connection.execute(text("DELETE FROM analysis_batch_items WHERE video_id NOT IN (SELECT id FROM video_candidates)"))

        if "analysis_batches" in table_names:
            connection.execute(
                text(
                    "DELETE FROM analysis_batches "
                    "WHERE monitor_profile_id IS NOT NULL AND monitor_profile_id NOT IN (SELECT id FROM monitor_profiles)"
                )
            )
            if "analysis_batch_items" in table_names:
                connection.execute(
                    text(
                        "DELETE FROM analysis_batches "
                        "WHERE id NOT IN (SELECT DISTINCT batch_id FROM analysis_batch_items)"
                    )
                )

        if "incidents" in table_names:
            connection.execute(
                text(
                    f"DELETE FROM incidents WHERE video_candidate_id IN ({stale_or_orphan_video_subquery})"
                )
            )
            connection.execute(text("DELETE FROM incidents WHERE video_candidate_id NOT IN (SELECT id FROM video_candidates)"))

        if "chat_sessions" in table_names:
            connection.execute(
                text(
                    f"DELETE FROM chat_sessions WHERE video_candidate_id IN ({stale_or_orphan_video_subquery})"
                )
            )
            connection.execute(text("DELETE FROM chat_sessions WHERE video_candidate_id NOT IN (SELECT id FROM video_candidates)"))

        if "project_insight_reports" in table_names:
            connection.execute(
                text(
                    "DELETE FROM project_insight_reports "
                    "WHERE monitor_profile_id NOT IN (SELECT id FROM monitor_profiles)"
                )
            )

        connection.execute(text(f"DELETE FROM video_candidates WHERE id IN ({stale_or_orphan_video_subquery})"))


def ensure_default_app_users(engine: Engine) -> None:
    inspector = inspect(engine)
    if "app_users" not in inspector.get_table_names():
        return

    with engine.begin() as connection:
        existing_rows = connection.execute(text("SELECT id FROM app_users")).fetchall()
        existing_ids = {str(row[0]) for row in existing_rows}
        for user_id in DEFAULT_APP_USERS:
            if user_id in existing_ids:
                continue
            connection.execute(
                text(
                    """
                    INSERT INTO app_users (id, display_name, password_hash, must_change_password, is_active)
                    VALUES (:id, :display_name, :password_hash, :must_change_password, :is_active)
                    """
                ),
                {
                    "id": user_id,
                    "display_name": user_id,
                    "password_hash": hash_password("1234"),
                    "must_change_password": True,
                    "is_active": True,
                },
            )
