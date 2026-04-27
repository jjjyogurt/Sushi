import time
import logging
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
_engine_kwargs = {}
if not settings.database_url.startswith("sqlite"):
    _engine_kwargs["pool_pre_ping"] = True

_engine = None


def get_db_engine(max_retries: int = 10, retry_delay: float = 3.0) -> Engine:
    """Get or create the database engine with retry logic for Cloud SQL connections."""
    global _engine
    if _engine is not None:
        return _engine

    last_error = None
    for attempt in range(max_retries):
        try:
            engine = create_engine(
                settings.database_url,
                connect_args=_connect_args,
                **_engine_kwargs
            )
            # Test the connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            _engine = engine
            logger.info(f"Database connection established after {attempt + 1} attempt(s)")
            return _engine
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning(f"Database connection attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Database connection failed after {max_retries} attempts: {e}")
                raise last_error

    raise last_error


def get_db_session() -> Generator[Session, None, None]:
    engine = get_db_engine()
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

