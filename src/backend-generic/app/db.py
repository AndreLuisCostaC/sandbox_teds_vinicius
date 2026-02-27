from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _database_url() -> str:
    raw_url = os.getenv(
        "DATABASE_URL",
        "postgresql://prodgrade:prodgrade@localhost:5432/prodgrade",
    )
    return _normalize_database_url(raw_url)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


engine = create_engine(
    _database_url(),
    pool_pre_ping=True,
    pool_size=_int_env("DB_POOL_SIZE", 30),
    max_overflow=_int_env("DB_MAX_OVERFLOW", 40),
    pool_timeout=_int_env("DB_POOL_TIMEOUT", 60),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

