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
