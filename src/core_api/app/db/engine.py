"""Database engine and session factory.

SQLite (WAL mode) for the hackathon: one file, zero setup. Everything goes
through SQLAlchemy, so switching to PostgreSQL only means changing
CRIMEFIR_DATABASE_URL.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _configure_sqlite(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")      # readers never block the writer
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=30000")
    cur.close()


def init_engine(url: str | None = None) -> Engine:
    """Create (or re-create, e.g. for tests) the engine and the tables."""
    global _engine, _session_factory
    from .models import Base

    url = url or get_settings().database_url
    kwargs = {}
    if url.startswith("sqlite"):
        db_file = url.split("///", 1)[-1]
        if db_file and db_file != ":memory:":
            Path(db_file).parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    engine = create_engine(url, future=True, **kwargs)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _configure_sqlite)
    Base.metadata.create_all(engine)
    if _engine is not None:
        _engine.dispose()
    _engine = engine
    _session_factory = sessionmaker(engine, expire_on_commit=False)
    return engine


def get_engine() -> Engine:
    if _engine is None:
        init_engine()
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on error."""
    if _session_factory is None:
        init_engine()
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as session:
        yield session
