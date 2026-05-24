from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()


def _engine_kwargs(url: str) -> dict:
    """Pool config that won't be rejected by SQLite's single-threaded pool."""
    if url.startswith("sqlite"):
        return {"future": True}
    return {
        "future": True,
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    }


engine = create_engine(_settings.database_url, **_engine_kwargs(_settings.database_url))

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    from . import models  # noqa: F401 — ensure models are registered

    Base.metadata.create_all(bind=engine)
