"""Database engine, session factory and declarative base (ARCHITECTURE.md sections 2 and 3).

Always obtain sessions through ``SessionLocal`` (or the ``get_db`` dependency) rather than the
module-level ``engine``: tests re-bind ``SessionLocal`` to an in-memory database.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Dialect, Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import get_settings

# Age in seconds after which a pooled PostgreSQL connection is replaced. Matches Neon's 5-minute
# scale-to-zero delay; pool_pre_ping catches connections dropped in between.
POSTGRES_POOL_RECYCLE_S = 300


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware UTC timestamp on every backend.

    SQLite has no time zone support and returns naive values; this type stores UTC and always
    hands back aware datetimes so comparisons and JSON output behave the same everywhere.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not allowed; use app.db.utcnow()")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    """Declarative base shared by every model."""

    type_annotation_map = {datetime: UTCDateTime}


def check_one_of(column: str, values: Iterable[str]) -> str:
    """SQL CHECK expression restricting ``column`` to a fixed set of literal values.

    Only used with the ``Literal`` aliases of ``app.schemas`` (never with user input).
    """
    allowed = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({allowed})"


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    # SQLite ignores foreign keys (and ON DELETE CASCADE) unless asked per connection.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(database_url: str, **engine_kwargs: Any) -> Engine:
    """Create an engine with the right options for SQLite (dev/tests) or PostgreSQL (prod)."""
    is_sqlite = database_url.startswith("sqlite")
    if is_sqlite:
        # FastAPI runs sync endpoints in a thread pool, so connections cross threads.
        engine_kwargs.setdefault("connect_args", {"check_same_thread": False})
    else:
        # Serverless Postgres (Neon) suspends its compute after 5 idle minutes and drops open
        # connections: test each connection before use and retire old ones.
        engine_kwargs.setdefault("pool_pre_ping", True)
        engine_kwargs.setdefault("pool_recycle", POSTGRES_POOL_RECYCLE_S)
    db_engine = create_engine(database_url, **engine_kwargs)
    if is_sqlite:
        event.listen(db_engine, "connect", _enable_sqlite_foreign_keys)
    return db_engine


engine: Engine = create_db_engine(get_settings().database_url)

# expire_on_commit=False lets routers return ORM objects right after committing them.
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False
)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
