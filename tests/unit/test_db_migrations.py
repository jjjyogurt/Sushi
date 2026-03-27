from sqlalchemy import create_engine, inspect, text

from app.db_migrations import ensure_monitor_profiles_key_products_column


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
