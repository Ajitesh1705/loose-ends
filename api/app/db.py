from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
# pool_recycle: serverless instances idle between requests and hosted Postgres drops
# idle connections — recycle before the far end does. pool_size stays small because
# each function instance keeps its own pool.
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_recycle=280,
    pool_size=2,
    max_overflow=3,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with SessionLocal() as session:
        yield session
