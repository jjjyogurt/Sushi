from sqlalchemy import create_engine, inspect, text

from app.db_migrations import ensure_analysis_results_summary_columns, ensure_monitor_profiles_key_products_column


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
