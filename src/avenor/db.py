from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from avenor.config import AppConfig, get_config


class Base(DeclarativeBase):
    pass


_ENGINE = None
_SESSION_FACTORY = None


def _engine_kwargs(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


def get_engine(config: AppConfig | None = None):
    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is None:
        cfg = config or get_config()
        _ENGINE = create_engine(cfg.database_url, future=True, **_engine_kwargs(cfg.database_url))
        _SESSION_FACTORY = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False, expire_on_commit=False)
    return _ENGINE


def init_db(config: AppConfig | None = None) -> None:
    import avenor.models  # noqa: F401

    engine = get_engine(config)
    Base.metadata.create_all(bind=engine)


def get_db_session(config: AppConfig | None = None) -> Generator[Session, None, None]:
    global _SESSION_FACTORY
    get_engine(config)
    session = _SESSION_FACTORY()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope(config: AppConfig | None = None):
    global _SESSION_FACTORY
    get_engine(config)
    session: Session = _SESSION_FACTORY()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_db_state() -> None:
    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is not None:
        _ENGINE.dispose()
    _ENGINE = None
    _SESSION_FACTORY = None
