from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.services.security import hash_password


DEFAULT_SUSHI_APP_USERS = tuple(f"Sushi_{index}" for index in range(1, 16))
DEFAULT_FRUIT_APP_USERS = (
    "Mango",
    "Lychee",
    "Papaya",
    "Guava",
    "Kiwi",
    "Fig",
    "Cherry",
    "Peach",
    "Plum",
    "Apricot",
    "Durian",
    "Rambutan",
    "Persimmon",
    "Blueberry",
    "Pineapple",
    "Coconut",
    "Tangerine",
    "Nectarine",
    "Mulberry",
    "Passionfruit",
)
DEFAULT_APP_USERS = DEFAULT_SUSHI_APP_USERS + DEFAULT_FRUIT_APP_USERS
LEGACY_OWNER_USER_ID = DEFAULT_APP_USERS[0]


def _sqlite_table_has_unique_index_on_columns(connection, *, table_name: str, column_names: list[str]) -> bool:
    index_rows = connection.execute(text(f"PRAGMA index_list('{table_name}')")).fetchall()
    for index_row in index_rows:
        index_name = str(index_row[1])
        is_unique = int(index_row[2] or 0) == 1
        if not is_unique:
            continue
        indexed_columns = [
            str(column_row[2])
            for column_row in connection.execute(text(f"PRAGMA index_info('{index_name}')")).fetchall()
        ]
        if indexed_columns == column_names:
            return True
    return False


def _sqlite_rebuild_video_candidates_without_global_youtube_unique(connection) -> None:
    existing_columns = inspect(connection).get_columns("video_candidates")
    column_names = [column["name"] for column in existing_columns]
    column_definitions = []
    for column in existing_columns:
        column_name = str(column["name"])
        column_type = str(column["type"] or "TEXT")
        parts = [f'"{column_name}"', column_type]
        if column.get("primary_key"):
            parts.append("PRIMARY KEY")
        elif not bool(column.get("nullable", True)):
            parts.append("NOT NULL")
        default_value = column.get("default")
        if default_value is not None:
            parts.append(f"DEFAULT {default_value}")
        column_definitions.append(" ".join(parts))

    if "monitor_profile_id" in column_names:
        column_definitions.append("FOREIGN KEY(monitor_profile_id) REFERENCES monitor_profiles(id)")

    selected_columns = ", ".join(f'"{column_name}"' for column_name in column_names)
    connection.execute(text("PRAGMA foreign_keys=OFF"))
    connection.execute(text("ALTER TABLE video_candidates RENAME TO video_candidates_old"))
    connection.execute(text(f"CREATE TABLE video_candidates ({', '.join(column_definitions)})"))
    connection.execute(
        text(
            f"INSERT INTO video_candidates ({selected_columns}) "
            f"SELECT {selected_columns} FROM video_candidates_old"
        )
    )
    connection.execute(text("DROP TABLE video_candidates_old"))
    connection.execute(text("PRAGMA foreign_keys=ON"))


def _sqlite_rebuild_video_comments_without_global_youtube_unique(connection) -> None:
    existing_columns = inspect(connection).get_columns("video_comments")
    column_names = [column["name"] for column in existing_columns]
    column_definitions = []
    for column in existing_columns:
        column_name = str(column["name"])
        column_type = str(column["type"] or "TEXT")
        parts = [f'"{column_name}"', column_type]
        if column.get("primary_key"):
            parts.append("PRIMARY KEY")
        elif not bool(column.get("nullable", True)):
            parts.append("NOT NULL")
        default_value = column.get("default")
        if default_value is not None:
            parts.append(f"DEFAULT {default_value}")
        column_definitions.append(" ".join(parts))

    table_names = set(inspect(connection).get_table_names())
    if "video_candidates" in table_names and "video_candidate_id" in column_names:
        column_definitions.append("FOREIGN KEY(video_candidate_id) REFERENCES video_candidates(id)")

    selected_columns = ", ".join(f'"{column_name}"' for column_name in column_names)
    connection.execute(text("PRAGMA foreign_keys=OFF"))
    connection.execute(text("ALTER TABLE video_comments RENAME TO video_comments_old"))
    connection.execute(text(f"CREATE TABLE video_comments ({', '.join(column_definitions)})"))
    connection.execute(
        text(
            f"INSERT INTO video_comments ({selected_columns}) "
            f"SELECT {selected_columns} FROM video_comments_old"
        )
    )
    connection.execute(text("DROP TABLE video_comments_old"))
    connection.execute(text("PRAGMA foreign_keys=ON"))


def ensure_monitor_profiles_owner_user_id(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "monitor_profiles" not in table_names:
        return
    columns = {column["name"] for column in inspector.get_columns("monitor_profiles")}
    indexes = {index["name"] for index in inspector.get_indexes("monitor_profiles")}

    with engine.begin() as connection:
        if "app_users" in table_names:
            existing_owner = connection.execute(
                text("SELECT id FROM app_users WHERE id = :id"),
                {"id": LEGACY_OWNER_USER_ID},
            ).fetchone()
            if existing_owner is None:
                connection.execute(
                    text(
                        """
                        INSERT INTO app_users (id, display_name, password_hash, must_change_password, is_active)
                        VALUES (:id, :display_name, :password_hash, :must_change_password, :is_active)
                        """
                    ),
                    {
                        "id": LEGACY_OWNER_USER_ID,
                        "display_name": LEGACY_OWNER_USER_ID,
                        "password_hash": hash_password("1234"),
                        "must_change_password": True,
                        "is_active": True,
                    },
                )

        if "owner_user_id" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE monitor_profiles "
                    f"ADD COLUMN owner_user_id VARCHAR(80) NOT NULL DEFAULT '{LEGACY_OWNER_USER_ID}'"
                )
            )
        else:
            connection.execute(
                text("UPDATE monitor_profiles SET owner_user_id = :owner WHERE owner_user_id IS NULL OR owner_user_id = ''"),
                {"owner": LEGACY_OWNER_USER_ID},
            )
        if "ix_monitor_profiles_owner_user_id" not in indexes:
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_monitor_profiles_owner_user_id ON monitor_profiles (owner_user_id)")
            )


def ensure_video_candidate_scoped_youtube_uniqueness(engine: Engine) -> None:
    inspector = inspect(engine)
    if "video_candidates" not in inspector.get_table_names():
        return
    indexes = {index["name"] for index in inspector.get_indexes("video_candidates")}

    with engine.begin() as connection:
        dialect_name = connection.dialect.name
        if dialect_name == "sqlite":
            if _sqlite_table_has_unique_index_on_columns(
                connection,
                table_name="video_candidates",
                column_names=["youtube_video_id"],
            ):
                _sqlite_rebuild_video_candidates_without_global_youtube_unique(connection)
                indexes = {index["name"] for index in inspect(connection).get_indexes("video_candidates")}
        else:
            connection.execute(text("ALTER TABLE video_candidates DROP CONSTRAINT IF EXISTS video_candidates_youtube_video_id_key"))
            connection.execute(text("DROP INDEX IF EXISTS ix_video_candidates_youtube_video_id"))

        if "ix_video_candidates_youtube_video_id" not in indexes:
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_video_candidates_youtube_video_id ON video_candidates (youtube_video_id)"))
        if "ix_video_candidates_monitor_profile_id" not in indexes:
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_video_candidates_monitor_profile_id ON video_candidates (monitor_profile_id)"))
        if "ix_video_candidates_profile_youtube_video_id" not in indexes:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_video_candidates_profile_youtube_video_id "
                    "ON video_candidates (monitor_profile_id, youtube_video_id)"
                )
            )


def ensure_agent_settings_table(engine: Engine) -> None:
    inspector = inspect(engine)
    if "agent_settings" in inspector.get_table_names():
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE agent_settings (
                    user_id VARCHAR(80) PRIMARY KEY,
                    content TEXT NOT NULL,
                    settings_hash VARCHAR(64) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES app_users(id)
                )
                """
            )
        )
        connection.execute(text("CREATE INDEX ix_agent_settings_settings_hash ON agent_settings (settings_hash)"))


def ensure_analysis_results_agent_settings_hash_column_and_index(engine: Engine) -> None:
    inspector = inspect(engine)
    if "analysis_results" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("analysis_results")}
    indexes = {index["name"] for index in inspector.get_indexes("analysis_results")}

    statements = []
    if "agent_settings_hash" not in columns:
        statements.append("ALTER TABLE analysis_results ADD COLUMN agent_settings_hash VARCHAR(64) NOT NULL DEFAULT 'legacy'")
    if "ix_analysis_video_version_language" in indexes:
        statements.append("DROP INDEX ix_analysis_video_version_language")
    if "ix_analysis_video_version_language_settings" not in indexes:
        statements.append(
            "CREATE UNIQUE INDEX ix_analysis_video_version_language_settings "
            "ON analysis_results (video_candidate_id, analysis_version, language, agent_settings_hash)"
        )
    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


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


def ensure_project_insight_job_tables(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as connection:
        dialect_name = connection.dialect.name
        timestamp_type = "DATETIME" if dialect_name == "sqlite" else "TIMESTAMP WITH TIME ZONE"
        id_definition = "INTEGER PRIMARY KEY" if dialect_name == "sqlite" else "SERIAL PRIMARY KEY"
        if "project_insight_jobs" not in table_names:
            connection.execute(
                text(
                    f"""
                    CREATE TABLE project_insight_jobs (
                        id {id_definition},
                        monitor_profile_id INTEGER NOT NULL,
                        language VARCHAR(20) NOT NULL DEFAULT 'en',
                        created_by VARCHAR(80) NOT NULL DEFAULT 'system',
                        status VARCHAR(20) NOT NULL DEFAULT 'QUEUED',
                        report_id INTEGER NULL,
                        last_error TEXT NOT NULL DEFAULT '',
                        started_at {timestamp_type} NULL,
                        finished_at {timestamp_type} NULL,
                        created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                        updated_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(monitor_profile_id) REFERENCES monitor_profiles(id),
                        FOREIGN KEY(report_id) REFERENCES project_insight_reports(id)
                    )
                    """
                )
            )

        columns = {column["name"] for column in inspect(connection).get_columns("project_insight_jobs")}
        if "language" not in columns:
            connection.execute(
                text("ALTER TABLE project_insight_jobs ADD COLUMN language VARCHAR(20) NOT NULL DEFAULT 'en'")
            )

        indexes = {index["name"] for index in inspect(connection).get_indexes("project_insight_jobs")}
        connection.execute(text("DROP INDEX IF EXISTS ux_project_insight_jobs_one_active_per_profile"))
        if "ix_project_insight_jobs_monitor_profile_id" not in indexes:
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_project_insight_jobs_monitor_profile_id ON project_insight_jobs (monitor_profile_id)")
            )
        if "ix_project_insight_jobs_language" not in indexes:
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_project_insight_jobs_language ON project_insight_jobs (language)")
            )
        if "ix_project_insight_jobs_report_id" not in indexes:
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_project_insight_jobs_report_id ON project_insight_jobs (report_id)")
            )
        if "ix_project_insight_jobs_profile_status_created" not in indexes:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_project_insight_jobs_profile_status_created "
                    "ON project_insight_jobs (monitor_profile_id, status, created_at)"
                )
            )
        if "ix_project_insight_jobs_profile_language_status_created" not in indexes:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_project_insight_jobs_profile_language_status_created "
                    "ON project_insight_jobs (monitor_profile_id, language, status, created_at)"
                )
            )
        if "ix_project_insight_jobs_status_created" not in indexes:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_project_insight_jobs_status_created "
                    "ON project_insight_jobs (status, created_at)"
                )
            )
        if "ux_project_insight_jobs_one_active_per_profile_language" not in indexes:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_project_insight_jobs_one_active_per_profile_language "
                    "ON project_insight_jobs (monitor_profile_id, language) "
                    "WHERE status IN ('QUEUED', 'RUNNING')"
                )
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


def ensure_analysis_results_transcript_provenance_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "analysis_results" not in table_names:
        return
    columns = {column["name"] for column in inspector.get_columns("analysis_results")}

    statements = []
    if "transcript_language" not in columns:
        statements = [*statements, "ALTER TABLE analysis_results ADD COLUMN transcript_language VARCHAR(16) NOT NULL DEFAULT ''"]
    if "transcript_source_language" not in columns:
        statements = [*statements, "ALTER TABLE analysis_results ADD COLUMN transcript_source_language VARCHAR(16) NOT NULL DEFAULT ''"]
    if "transcript_is_translated" not in columns:
        boolean_default = "0" if engine.dialect.name == "sqlite" else "false"
        statements = [
            *statements,
            f"ALTER TABLE analysis_results ADD COLUMN transcript_is_translated BOOLEAN NOT NULL DEFAULT {boolean_default}",
        ]
    if "transcript_translation_model" not in columns:
        statements = [*statements, "ALTER TABLE analysis_results ADD COLUMN transcript_translation_model VARCHAR(60) NOT NULL DEFAULT ''"]
    if "transcript_status" not in columns:
        statements = [*statements, "ALTER TABLE analysis_results ADD COLUMN transcript_status VARCHAR(24) NOT NULL DEFAULT ''"]
    if "transcript_error_message" not in columns:
        statements = [*statements, "ALTER TABLE analysis_results ADD COLUMN transcript_error_message TEXT NOT NULL DEFAULT ''"]
    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.execute(
            text(
                """
                UPDATE analysis_results
                SET transcript_status = CASE
                    WHEN transcript_text IS NOT NULL AND transcript_text <> '' THEN 'available'
                    WHEN status = 'COMPLETED' OR status = 'completed' THEN 'unavailable'
                    ELSE ''
                END
                WHERE transcript_status = ''
                """
            )
        )


def ensure_video_comments_table(engine: Engine) -> None:
    inspector = inspect(engine)
    if "video_comments" not in inspector.get_table_names():
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE video_comments (
                        id INTEGER PRIMARY KEY,
                        video_candidate_id INTEGER NOT NULL,
                        youtube_comment_id VARCHAR(128) NOT NULL,
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
            connection.execute(text("CREATE INDEX ix_video_comments_youtube_comment_id ON video_comments (youtube_comment_id)"))
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX ix_video_comments_video_youtube_comment_id "
                    "ON video_comments (video_candidate_id, youtube_comment_id)"
                )
            )
            connection.execute(text("CREATE INDEX ix_video_comments_published_at ON video_comments (published_at)"))
            connection.execute(text("CREATE INDEX ix_video_comments_parent_comment_id ON video_comments (parent_comment_id)"))
        return

    with engine.begin() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("video_comments")}
        if not {"video_candidate_id", "youtube_comment_id"}.issubset(columns):
            return

        indexes = {index["name"] for index in inspect(connection).get_indexes("video_comments")}
        dialect_name = connection.dialect.name
        if dialect_name == "sqlite":
            if _sqlite_table_has_unique_index_on_columns(
                connection,
                table_name="video_comments",
                column_names=["youtube_comment_id"],
            ):
                _sqlite_rebuild_video_comments_without_global_youtube_unique(connection)
                indexes = {index["name"] for index in inspect(connection).get_indexes("video_comments")}
        else:
            connection.execute(text("ALTER TABLE video_comments DROP CONSTRAINT IF EXISTS ix_video_comments_youtube_comment_id"))
            connection.execute(text("ALTER TABLE video_comments DROP CONSTRAINT IF EXISTS video_comments_youtube_comment_id_key"))
            connection.execute(text("DROP INDEX IF EXISTS ix_video_comments_youtube_comment_id"))
            indexes.discard("ix_video_comments_youtube_comment_id")

        if "ix_video_comments_video_candidate_id" not in indexes:
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_video_comments_video_candidate_id ON video_comments (video_candidate_id)"))
        if "ix_video_comments_youtube_comment_id" not in indexes:
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_video_comments_youtube_comment_id ON video_comments (youtube_comment_id)"))
        if "ix_video_comments_video_youtube_comment_id" not in indexes:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_video_comments_video_youtube_comment_id "
                    "ON video_comments (video_candidate_id, youtube_comment_id)"
                )
            )
        if "ix_video_comments_published_at" not in indexes and "published_at" in columns:
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_video_comments_published_at ON video_comments (published_at)"))
        if "ix_video_comments_parent_comment_id" not in indexes and "parent_comment_id" in columns:
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_video_comments_parent_comment_id ON video_comments (parent_comment_id)"))


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


def ensure_video_candidate_reach_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "video_candidates" not in table_names:
        return
    columns = {column["name"] for column in inspector.get_columns("video_candidates")}
    statements = []
    if "view_count" not in columns:
        statements = [*statements, "ALTER TABLE video_candidates ADD COLUMN view_count INTEGER NULL"]
    if "view_count_fetched_at" not in columns:
        timestamp_type = "DATETIME" if engine.dialect.name == "sqlite" else "TIMESTAMP WITH TIME ZONE"
        statements = [*statements, f"ALTER TABLE video_candidates ADD COLUMN view_count_fetched_at {timestamp_type} NULL"]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        indexes = {index["name"] for index in inspect(connection).get_indexes("video_candidates")}
        if "ix_video_candidates_view_count" not in indexes:
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_video_candidates_view_count ON video_candidates (view_count)")
            )


def ensure_project_insight_reports_portfolio_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "project_insight_reports" not in table_names:
        return
    columns = {column["name"] for column in inspector.get_columns("project_insight_reports")}
    statements = []
    if "language" not in columns:
        statements = [*statements, "ALTER TABLE project_insight_reports ADD COLUMN language VARCHAR(20) NOT NULL DEFAULT 'en'"]
    if "sentiment_breakdown_json" not in columns:
        statements = [*statements, "ALTER TABLE project_insight_reports ADD COLUMN sentiment_breakdown_json TEXT NOT NULL DEFAULT '{}'"]
    if "risk_breakdown_json" not in columns:
        statements = [*statements, "ALTER TABLE project_insight_reports ADD COLUMN risk_breakdown_json TEXT NOT NULL DEFAULT '{}'"]
    if "reach_metrics_json" not in columns:
        statements = [*statements, "ALTER TABLE project_insight_reports ADD COLUMN reach_metrics_json TEXT NOT NULL DEFAULT '{}'"]
    if "top_negative_videos_json" not in columns:
        statements = [*statements, "ALTER TABLE project_insight_reports ADD COLUMN top_negative_videos_json TEXT NOT NULL DEFAULT '[]'"]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        indexes = {index["name"] for index in inspect(connection).get_indexes("project_insight_reports")}
        if "ix_project_insight_reports_language" not in indexes:
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_project_insight_reports_language ON project_insight_reports (language)")
            )


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

        if "project_insight_jobs" in table_names:
            connection.execute(
                text(
                    "DELETE FROM project_insight_jobs "
                    "WHERE monitor_profile_id NOT IN (SELECT id FROM monitor_profiles)"
                )
            )
            if "project_insight_reports" in table_names:
                connection.execute(
                    text(
                        "UPDATE project_insight_jobs SET report_id = NULL "
                        "WHERE report_id IS NOT NULL AND report_id NOT IN (SELECT id FROM project_insight_reports)"
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
