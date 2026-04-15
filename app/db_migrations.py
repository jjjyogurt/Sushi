from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.services.security import hash_password


DEFAULT_APP_USERS = tuple(f"Sushi_{index}" for index in range(1, 16))

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
    if "business_impact" not in columns:
        statements = [*statements, "ALTER TABLE analysis_results ADD COLUMN business_impact TEXT NOT NULL DEFAULT ''"]
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
