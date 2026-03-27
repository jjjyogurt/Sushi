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
