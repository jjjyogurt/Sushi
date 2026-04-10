from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


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
